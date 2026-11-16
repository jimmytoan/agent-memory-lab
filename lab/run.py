"""Run contestants over a question sample. One question at a time, one contestant at a time.

  uv run python -m lab.run --tag pilot --contestants full-context,pgvector-rag --per 4,4,4,3,2,3 --haystack 10
Rows go to results/runs.jsonl (resumable: finished (tag, contestant, qid) rows are skipped).
"""
import argparse, datetime, json, time, traceback
from pathlib import Path
from lab import dataset, llm, scoring

OUT = Path("results/runs.jsonl")


def registry():
    from lab.contestants.full_context import FullContext
    from lab.contestants.pgvector_rag import PgvectorRAG
    from lab.contestants.mem0_c import Mem0
    from lab.contestants.graphiti_c import GraphitiC
    from lab.contestants.letta_c import LettaC
    return {c.name: c for c in (FullContext, PgvectorRAG, Mem0, GraphitiC, LettaC)}


def quiet_window(spec):
    """Sleep through a daily local-time window 'HH:MM-HH:MM' (another lab's timed run uses Docker then)."""
    if not spec:
        return
    a, b = (datetime.time(*map(int, x.split(":"))) for x in spec.split("-"))
    now = datetime.datetime.now()
    if a <= now.time() < b:
        until = datetime.datetime.combine(now.date(), b)
        print(f"QUIET WINDOW: sleeping until {until:%H:%M}", flush=True)
        time.sleep((until - now).total_seconds())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--contestants", required=True)
    ap.add_argument("--per", default="4,4,4,3,2,3", help="questions per stratum, order: " + ",".join(dataset.STRATA))
    ap.add_argument("--haystack", type=int, default=10)
    ap.add_argument("--seed", type=int, default=20261116)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--budget", type=float, default=3.0, help="stop when this tag's spend reaches this many dollars")
    ap.add_argument("--answers", type=int, default=1, help="answers per ingested memory (ingest once, answer N times)")
    ap.add_argument("--attempts", type=int, default=3, help="tries per question when ingestion or answering raises")
    ap.add_argument("--quiet", default="", help="daily local window HH:MM-HH:MM in which no question is started")
    a = ap.parse_args()
    per = dict(zip(dataset.STRATA, map(int, a.per.split(","))))
    qs = dataset.sample(per, a.haystack, a.seed)
    if a.limit:
        qs = qs[:a.limit]
    done = set()
    if OUT.exists():
        done = {(r["tag"], r["contestant"], r["qid"]) for r in map(json.loads, OUT.open()) if not r.get("error")}
    reg = registry()
    for name in a.contestants.split(","):
        c = reg[name]()
        c.setup()
        for q in qs:
            if (a.tag, name, q.qid) in done:
                continue
            spent = llm.usage(a.tag)["usd"]
            if spent >= a.budget:
                print(f"BUDGET STOP: ${spent:.2f} spent on tag {a.tag}"); return
            base = f"{a.tag}|{name}|{q.qid}"
            row = dict(tag=a.tag, contestant=name, qid=q.qid, qtype=q.qtype, stratum=q.stratum, question=q.question,
                       gold=q.answer, n_sessions=len(q.sessions), haystack_chars=sum(len(s.text()) for s in q.sessions),
                       answer_model=llm.ANSWER_MODEL, config=c.config)
            for attempt in range(1, a.attempts + 1):
                quiet_window(a.quiet)
                row.pop("error", None); row["attempts"] = attempt
                try:
                    llm.tag(base + "|ingest"); t0 = time.time()
                    c.ingest(q)
                    row["ingest_secs"] = round(time.time() - t0, 2)
                    llm.tag(base + "|query")
                    resps, secs, ctx = [], [], ""
                    for _ in range(a.answers):
                        t0 = time.time()
                        resp, ctx = c.answer(q)
                        secs.append(round(time.time() - t0, 2)); resps.append(resp)
                    oks = [scoring.score(q.answer, r, q.qtype, q.abstain) for r in resps]
                    row.update(responses=resps, corrects=oks, query_secs_all=secs, n_answers=len(resps),
                               query_secs=secs[0], response=resps[0], answer_line=scoring.extract(resps[0]),
                               context_chars=len(ctx), context=ctx[:6000], correct=oks[0])
                except Exception as e:
                    row["error"] = f"{type(e).__name__}: {e}"[:500]
                    traceback.print_exc()
                finally:
                    llm.tag("idle")
                    try: c.cleanup(q)
                    except Exception: traceback.print_exc()
                if not row.get("error"):
                    break
                if attempt < a.attempts:
                    time.sleep(60)
            row["ingest"] = llm.usage(base + "|ingest"); row["query"] = llm.usage(base + "|query")
            with OUT.open("a") as f:
                f.write(json.dumps(row) + "\n")
            print(f"{name:13s} {q.stratum:24s} {q.qid:18s} {'ERR' if row.get('error') else str(sum(row['corrects'])) + '/' + str(len(row['corrects']))}"
                  f" ingest {row.get('ingest_secs', 0):7.1f}s ${row['ingest']['usd']:.4f} | query {row.get('query_secs', 0):5.1f}s ${row['query']['usd']:.4f}"
                  f" | gold={q.answer[:30]!r} got={row.get('answer_line', '')[:40]!r}", flush=True)


if __name__ == "__main__":
    main()
