# Agent memory lab: plan for the full run

**Update 2026-11-17: the recommended run (60 x 24, 3 answers each) was approved and completed as tag `run1` for $34.87; see `results/run1-report.md` and `post/`. Graphiti cost $19.52 against the $13 estimated below.**

Status on 2026-11-16: harness built, self-test passes (23 tests, no model calls), pilot run.
Total API spend so far: **$2.16** (smoke $0.14, pilot $2.02), under the $3 cap.
Nothing is committed, there is no remote, and no full run has been started.

## 1. Contestants and exact configuration

Every contestant gets the same sessions, the same question, the same answer prompt
(`lab/llm.py`, `ANSWER_SYSTEM`) and the same answering model. All LLM and embedding calls go
through one local metering proxy (`lab/proxy.py`), so tokens and dollars are counted the same
way for all five. Concurrency is 1.

Shared: memory LLM `claude-haiku-5-5`, embeddings OpenAI `text-embedding-3-small` (1536-d),
answering model `claude-haiku-5-5`.

| Contestant | Version | Storage | Configuration |
|---|---|---|---|
| full-context | – | none | Every session, chronological, with date headers, in the prompt |
| pgvector-rag | pgvector 0.8.1 / pg17 | Postgres | Chunk = one user turn + the reply, date-prefixed; exact cosine, top 10 |
| mem0 | `mem0ai[nlp]` 2.2.1 (OSS) | pgvector | One `add()` per session, session date prefixed to the first message; `search(top_k=20, threshold=0.1, rerank=False)` (library defaults) |
| graphiti (Zep's open-source engine) | `graphiti-core` 0.31.2 | Neo4j 5.26 community | One episode per session, `reference_time` = session date; `COMBINED_HYBRID_SEARCH_RRF`, limit 20; facts rendered with valid-from/until |
| letta | `letta/letta:0.15.1` server, `letta-client` 1.12.1 | bundled Postgres | One agent per question, default memory blocks and base tools, 32k context window; sessions sent as dated messages; the agent answers the question itself |

Can each run without a vendor account? Yes, all three, but not in the form the vendors benchmark:

- **Mem0**: the open-source library has no graph memory and rejects `timestamp` / `reference_date`
  (Platform-only). Mem0's published scores are Platform numbers.
- **Zep**: Community Edition was discontinued in April 2025. Graphiti is the self-hosted route and
  is not the same as Zep Cloud.
- **Letta**: the self-hosted Python server (the MemGPT architecture) is retired. Docker images from
  0.31 contain "Letta Code" instead, which has no Python SDK and a file-based memory. The lab pins
  0.15.1, the last image of the old server. **This needs your decision** (section 6).

## 2. Dataset and sample

LongMemEval-S, cleaned release (MIT, Hugging Face `xiaowu0162/longmemeval-cleaned`,
SHA-256 `d6f21ea9…c3a442`). 500 questions, each with its own haystack of about 48 sessions
(~115k tokens). LoCoMo was rejected: non-commercial licence, only 10 conversations that fit in
context, known wrong gold answers, no updated-fact questions.

- **Scoring is deterministic**, on a forced final `ANSWER:` line. Only questions with a short gold
  answer (4 words or fewer) or abstention questions are eligible: 349 of 500. Preference
  questions (30) are excluded because they need a judge.
- **Strata**: knowledge-update (the updated/contradicted-fact questions), temporal-reasoning,
  multi-session, single-session-user, single-session-assistant, abstention.
- **Sampling**: `random.Random("20261116:<stratum>").sample` over the eligible pool sorted by
  question id. Haystack reduction keeps every evidence session and samples distractors from the
  question's own haystack with `random.Random("20261116:<question_id>")`.

## 3. What the pilot showed

20 questions per contestant, 8 sessions per question, Haiku 5.5.

| Contestant | n | Correct | Ingest s/question | Ingest $/question | Query $/question | Context chars |
|---|---|---|---|---|---|---|
| full-context | 20 | 19 | 0 | 0 | 0.0032 | 88,285 |
| pgvector-rag | 20 | 17 | 0.6 | 0.0004 | 0.0010 | 24,044 |
| mem0 | 20 | 17 | 89 | 0.023 | 0.0003 | 4,481 |
| letta | 20 | 15 | 75 | 0.045 | 0.0054 | 1,041 |
| graphiti | 6 | 5 | 270 | 0.073 | 0.0004 | 7,856 |

- **Graphiti is incomplete**: 6 of 20. Four questions hit Anthropic 500 errors, and ten failed
  because Docker Desktop stopped at about 09:39 (I did not stop it and have not restarted it).
- **The 8-session test is too easy to separate the approaches.** Everything fits in context, and
  the differences are within noise at n=20. The full run needs larger haystacks.
- **Scorer check**: I read all 13 wrong rows. 12 are real misses. One is a false negative: Letta
  answered "Ford F-150 pickup (1/25 scale)" for gold "Ford F-150 pickup truck". For the full run
  I will read every row scored wrong and report any overrides separately.
- **Per-session ingestion**: Mem0 11 s / $0.0029, Letta 9 s / $0.0057, Graphiti 34 s / $0.0091.

## 4. Proposed run matrix

Ingest once per contestant and question, then answer **3 times** from the stored memory
(answers are cheap, ingestion is not), so answer noise is measured. This needs a small harness
change (repeat the query before cleanup) and a retry on API 500s.

**Recommended: 60 questions (10 per stratum), 24 sessions per question (~57k tokens).**

| Contestant | Ingest time | Ingest $ | Query $ (3 answers) | Total $ |
|---|---|---|---|---|
| full-context | 0 | 0 | 1.1 | 1.1 |
| pgvector-rag | 2 min | 0.1 | 0.2 | 0.3 |
| mem0 | 4.5 h | 4.2 | 0.1 | 4.3 |
| letta | 3.8 h | 8.2 | 1.0 | 9.2 |
| graphiti | 13.5 h | 13.1 | 0.1 | 13.2 |
| **Total** | **≈22 h** | **25.6** | **2.5** | **≈28** |

Ingestion is about 90% of the cost and nearly all of the time. I would set a hard budget stop
at **$35** to cover retries. The run is resumable and would be split to stay clear of 4pm.

Alternatives:

| Option | Questions × sessions | Laptop time | Cost | Trade-off |
|---|---|---|---|---|
| Smaller | 36 × 24 | ≈13 h | ≈$17 | n=6 per stratum; only large gaps are visible |
| Recommended | 60 × 24 | ≈22 h | ≈$28 | ±12 points at n=60 |
| Full haystack | 60 × 48 (as published) | ≈44 h | ≈$58 | The real benchmark; full-context moves to Haiku's >100k price tier |

Optional add-on: re-answer with `claude-sonnet-5-5` from the same stored memories, about $8 more
(almost all of it the full-context baseline), to see whether a stronger answering model changes the ranking.

Estimates extrapolate linearly from the pilot. Graphiti's per-session time may grow as the graph
grows, so its row is the least certain.

## 5. What will be reported

Per contestant and per stratum: n, correct, accuracy, cost per correct answer, ingestion time /
tokens / dollars (separately), query latency, query tokens and dollars, retrieved context size.

## 6. Known fairness limits

1. **Letta version.** 0.15.1 is a retired server (November 2025). Current Letta is a different
   product. The alternative is to drop Letta or to say clearly that it is the legacy architecture.
2. **Letta answers with its own agent loop**, not from a retrieved context handed to the shared
   answerer. Same model and same answer instructions, but more model calls per question.
3. **Mem0 OSS ≠ Mem0 Platform**, and **Graphiti ≠ Zep Cloud**. Vendor-published numbers do not apply.
4. **Graphiti runs without its default cross-encoder reranker**, because the OpenAI key cannot call
   Chat Completions. RRF is a documented search recipe, but not the default.
5. **All memory LLM work uses Haiku 5.5**, not the OpenAI models the frameworks default to and
   tune their prompts for. The proxy strips `temperature`, which Haiku 5.5 rejects, and the
   Anthropic SDK is pinned below 1.0 because the frameworks still pass it.
6. **Reduced haystacks** (24 of ~48 sessions) make the test easier than the published benchmark.
7. **Deterministic scoring covers 349 of 500 questions** and excludes preference questions.
8. **One ingestion per question.** Extraction is not repeated, so ingestion variance is not measured.
9. **Embedding price** ($0.02 per million tokens) is from memory, not checked against a price page.
   It is under 1% of the cost.
10. A widely repeated claim that an independent re-run of Mem0 scored 29% against a published 92%
    could not be traced to a source and will not be cited.

## 7. Decisions needed

1. Run size: smaller, recommended or full haystack, and whether to add the Sonnet answers.
2. Letta: keep the legacy 0.15.1 server (labelled as such) or drop it.
3. Docker Desktop is not running; it has to be started before any run.
4. Where to push the repo (there is no remote), and whether to commit.
