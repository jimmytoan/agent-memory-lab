"""Local metering proxy. Every contestant's LLM and embedding calls go through it, so tokens,
dollars and call latency are counted the same way for all of them (including Letta's server).

  /anthropic/* -> https://api.anthropic.com/*      /openai/* -> https://api.openai.com/*
  POST /_tag {"tag": "..."}   set the label attached to subsequent calls (concurrency is 1)
  GET  /_usage?tag=prefix     totals for calls whose tag starts with prefix

It also removes sampling parameters (temperature, top_p, top_k) from Anthropic requests:
current Claude models reject them, and Mem0 / Graphiti / Letta still send them.
Run: uv run uvicorn lab.proxy:app --port 8177
"""
import json, os, time
from pathlib import Path
import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route
from lab.pricing import cost

UPSTREAM = {"anthropic": "https://api.anthropic.com", "openai": "https://api.openai.com"}
LOG = Path(os.environ.get("PROXY_LOG", "results/proxy_calls.jsonl"))
LOG.parent.mkdir(parents=True, exist_ok=True)
STATE = {"tag": "untagged"}
client = httpx.AsyncClient(timeout=httpx.Timeout(600, connect=20))
HOP = {"host", "content-length", "accept-encoding", "connection", "transfer-encoding"}


def record(provider, path, model, usage, dt, status, tag):
    inp = usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0
    out = usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
    cr = usage.get("cache_read_input_tokens", 0) or 0
    cw = usage.get("cache_creation_input_tokens", 0) or 0
    row = dict(ts=time.time(), tag=tag, provider=provider, path=path, model=model, status=status,
               input=inp, output=out, cache_read=cr, cache_write=cw, secs=round(dt, 3),
               usd=cost(model or "", inp, out, cr, cw) if status == 200 else 0.0)
    with LOG.open("a") as f:
        f.write(json.dumps(row) + "\n")


def sse_usage(buf: bytes) -> dict:
    u = {}
    for line in buf.split(b"\n"):
        if not line.startswith(b"data:"):
            continue
        try:
            ev = json.loads(line[5:])
        except Exception:
            continue
        for src in (ev.get("usage"), (ev.get("message") or {}).get("usage"), (ev.get("response") or {}).get("usage")):
            if isinstance(src, dict):
                u.update({k: v for k, v in src.items() if isinstance(v, int)})
    return u


async def forward(request: Request):
    provider, path = request.path_params["provider"], request.path_params["path"]
    if provider not in UPSTREAM:
        return JSONResponse({"error": "unknown provider"}, 404)
    body = await request.body()
    model, stream = None, False
    if body and request.headers.get("content-type", "").startswith("application/json"):
        try:
            j = json.loads(body)
            model, stream = j.get("model"), bool(j.get("stream"))
            if provider == "anthropic" and any(k in j for k in ("temperature", "top_p", "top_k")):
                for k in ("temperature", "top_p", "top_k"):
                    j.pop(k, None)
                body = json.dumps(j).encode()
        except Exception:
            pass
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP}
    headers["accept-encoding"] = "identity"
    url = f"{UPSTREAM[provider]}/{path}"
    tag, t0 = STATE["tag"], time.time()
    req = client.build_request(request.method, url, params=request.query_params, content=body, headers=headers)
    up = await client.send(req, stream=True)
    rh = {k: v for k, v in up.headers.items() if k.lower() not in HOP | {"content-encoding"}}
    if stream and up.status_code == 200:
        async def gen():
            buf = b""
            async for chunk in up.aiter_bytes():
                buf += chunk
                yield chunk
            await up.aclose()
            record(provider, path, model, sse_usage(buf), time.time() - t0, 200, tag)
        return StreamingResponse(gen(), status_code=200, headers=rh)
    data = await up.aread()
    await up.aclose()
    usage = {}
    try:
        usage = json.loads(data).get("usage") or {}
    except Exception:
        pass
    if request.method == "POST":
        record(provider, path, model, usage, time.time() - t0, up.status_code, tag)
    return Response(data, status_code=up.status_code, headers=rh)


async def set_tag(request: Request):
    STATE["tag"] = (await request.json())["tag"]
    return JSONResponse(STATE)


async def usage(request: Request):
    prefix = request.query_params.get("tag", "")
    tot = dict(calls=0, input=0, output=0, cache_read=0, cache_write=0, usd=0.0, secs=0.0, errors=0, embed_tokens=0)
    if LOG.exists():
        for line in LOG.read_text().splitlines():
            r = json.loads(line)
            if not r["tag"].startswith(prefix):
                continue
            tot["calls"] += 1
            if r["status"] != 200:
                tot["errors"] += 1
                continue
            if "embedding" in (r["model"] or ""):
                tot["embed_tokens"] += r["input"]
            else:
                for k in ("input", "output", "cache_read", "cache_write"):
                    tot[k] += r[k]
            tot["usd"] += r["usd"]; tot["secs"] += r["secs"]
    return JSONResponse(tot)


app = Starlette(routes=[Route("/_tag", set_tag, methods=["POST"]), Route("/_usage", usage),
                        Route("/{provider}/{path:path}", forward, methods=["GET", "POST", "DELETE", "PUT", "PATCH"])])
