"""uv run python -m lab.report --tag pilot   -> per-contestant table + per-stratum accuracy."""
import argparse, collections, json, statistics
from pathlib import Path
from lab import scoring


OV = Path("results/overrides.json")
OVERRIDES = {(o["tag"], o["contestant"], o["qid"]): o["answers"] for o in json.loads(OV.read_text())} if OV.exists() else {}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--tag", required=True); a = ap.parse_args()
    rows = [r for r in map(json.loads, Path("results/runs.jsonl").open()) if r["tag"] == a.tag]
    for r in rows:   # always re-score from the stored response with the current scorer
        if not r.get("error"):
            resps = r.get("responses") or [r["response"]]
            r["corrects"] = [scoring.score(r["gold"], x, r["qtype"], r["qid"].endswith("_abs")) for x in resps]
            for i in OVERRIDES.get((r["tag"], r["contestant"], r["qid"]), []):
                r["corrects"][i] = True                      # manual review, listed in results/overrides.json
            r["correct"] = sum(r["corrects"]) / len(resps)   # fraction of this question's answers that are right
            r["query"]["usd"] /= len(resps)                  # per answer
            r["query_secs"] = statistics.median(r.get("query_secs_all") or [r["query_secs"]])
    by = collections.defaultdict(list)
    for r in rows:
        by[r["contestant"]].append(r)
    strata = sorted({r["stratum"] for r in rows})
    if not rows:
        print(f"tag={a.tag}: no rows")
        return
    print(f"tag={a.tag}  answer model={rows[0]['answer_model']}  sessions/question={statistics.mean(r['n_sessions'] for r in rows):.1f}\n")
    print("| contestant | n | errors | correct | accuracy | ingest s/q | ingest $/q | ingest tok/q | query s (median) | query $/q | context chars | $ per correct |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for c, rs in by.items():
        ok = [r for r in rs if not r.get("error")]
        n, k = len(ok), sum(r["correct"] for r in ok)
        ing = sum(r["ingest"]["usd"] for r in ok); qry = sum(r["query"]["usd"] for r in ok)
        tok = sum(r["ingest"]["input"] + r["ingest"]["output"] + r["ingest"]["cache_read"] + r["ingest"]["cache_write"] + r["ingest"]["embed_tokens"] for r in ok)
        print(f"| {c} | {n} | {len(rs) - n} | {k:.1f} | {k / n:.0%} | {statistics.mean(r['ingest_secs'] for r in ok):.1f} | {ing / n:.4f} | {tok / n:,.0f} |"
              f" {statistics.median(r['query_secs'] for r in ok):.1f} | {qry / n:.4f} | {statistics.mean(r['context_chars'] for r in ok):,.0f} | {(ing + qry) / k if k else float('nan'):.4f} |")
    print("\n| contestant | " + " | ".join(strata) + " |\n|---|" + "---|" * len(strata))
    for c, rs in by.items():
        cells = []
        for s in strata:
            x = [r for r in rs if r["stratum"] == s and not r.get("error")]
            cells.append(f"{sum(r['correct'] for r in x):.1f}/{len(x)}")
        print(f"| {c} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
