"""Shared clients (all through the metering proxy) and the single answer prompt."""
import os, time
import anthropic, httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

PROXY = os.environ.get("LAB_PROXY", "http://127.0.0.1:8177")
ANSWER_MODEL = os.environ.get("ANSWER_MODEL", "claude-haiku-5-5")
EMBED_MODEL = "text-embedding-3-small"

ANSWER_SYSTEM = """You are answering a question from a user about their own past conversations with an assistant.
Use only the MEMORY provided. Memory items carry dates; when facts conflict, the most recent one is the current truth.
The current date and time is {now}. Work out relative dates ("two weeks ago", "how many days") from the dates in memory.
Reason briefly, then finish with exactly one final line in this form:
ANSWER: <the shortest complete answer: a name, number, date or short phrase>
If the memory does not contain the information needed to answer, the final line must be exactly:
ANSWER: NOT_ENOUGH_INFO"""

ANSWER_USER = "MEMORY:\n{context}\n\nQUESTION: {question}"

_c = {}


def _a():
    if "a" not in _c:
        _c["a"] = anthropic.Anthropic(base_url=f"{PROXY}/anthropic", max_retries=4, timeout=600)
    return _c["a"]


def _o():
    if "o" not in _c:
        _c["o"] = OpenAI(base_url=f"{PROXY}/openai/v1", max_retries=4)
    return _c["o"]


def tag(t: str):
    httpx.post(f"{PROXY}/_tag", json={"tag": t}, timeout=10)


def usage(prefix: str) -> dict:
    return httpx.get(f"{PROXY}/_usage", params={"tag": prefix}, timeout=30).json()


def answer_instructions(now) -> str:
    return ANSWER_SYSTEM.format(now=now.strftime("%Y-%m-%d (%A) %H:%M"))


def answer(question: str, context: str, now) -> str:
    r = _a().messages.create(model=ANSWER_MODEL, max_tokens=4000, system=answer_instructions(now),
                           messages=[{"role": "user", "content": ANSWER_USER.format(context=context, question=question)}])
    return "".join(b.text for b in r.content if b.type == "text")


def embed(texts: list) -> list:
    out = []
    for i in range(0, len(texts), 64):
        r = _o().embeddings.create(model=EMBED_MODEL, input=[t[:24000] for t in texts[i:i + 64]])
        out += [d.embedding for d in r.data]
    return out
