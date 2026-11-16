# agent-memory-lab

One matched test of long-term agent memory: Mem0 (open source), Graphiti (the open-source engine behind Zep),
Letta (self-hosted server), a plain pgvector retrieval baseline and a full-history-in-context baseline.
Same questions, same answering model, same answer prompt; only memory and retrieval differ.

- `lab/dataset.py` LongMemEval-S (cleaned) loader, seeded stratified sample, reduced haystacks
- `lab/scoring.py` deterministic scoring of the final `ANSWER:` line (no LLM judge)
- `lab/proxy.py` local metering proxy: every contestant's LLM and embedding call is counted the same way
- `lab/contestants/` one adapter per contestant (`ingest`, `retrieve` / `answer`)
- `lab/run.py`, `lab/report.py` runner (resumable, budget-capped) and tables
- `PLAN.md` contestants, configs, sample, run matrix, cost estimate, fairness limits

## Run
```bash
docker compose -p agentmemlab up -d                      # this lab's own pgvector, Neo4j, Letta
set -a; . ./.env; set +a; uv run uvicorn lab.proxy:app --port 8177 --host 0.0.0.0 &
uv run pytest -q                                         # scorer + sampling self-test, no model calls
uv run python -m lab.run --tag pilot --contestants full-context,pgvector-rag,mem0,letta,graphiti --per 4,4,4,3,2,3 --haystack 8 --budget 2.7
uv run python -m lab.report --tag pilot
```
Data: `data/longmemeval/longmemeval_s_cleaned.json` from
https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned (MIT), sha256 in `lab/dataset.py`. Not committed.

## Results

Full run `run1` (2026-11-16/17): 60 questions x 24 sessions, 3 answers per loaded history, `claude-haiku-5-5`.
Table: `results/run1-report.md` (regenerate with `uv run python -m lab.report --tag run1`).
Every answer: `results/runs.jsonl`. Every model call with tokens and cost: `results/proxy_calls.jsonl`.
Manual scoring overrides: `results/overrides.json`. Plan and fairness limits: `PLAN.md`. Post draft: `post/`.
