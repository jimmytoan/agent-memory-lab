# **I Gave Five Agent Memory Setups the Same 60 Questions. The Two Simplest Ones Won**

*Draft. Numbers are from run `run1` in [jimmytoan/agent-memory-lab](https://github.com/jimmytoan/agent-memory-lab), 16–17 November 2026.*

Every agent memory vendor has a benchmark chart, and on every chart the vendor wins. Mem0 publishes numbers that beat Zep. Zep published a post arguing those numbers were wrong and re-scored itself higher. Letta showed that an agent with nothing but a filesystem beats both. The charts use different models, different prompts and different judges, and most of them measure a hosted product you cannot run yourself.

I wanted one number I could trust: with the **same conversations, the same questions, the same answering model and the same answer prompt**, which approach recalls the right fact, and what does it cost?

So I ran five setups on one matched test. Three are the open-source, self-hosted versions of the well-known frameworks. Two are baselines that take an afternoon to build.

The short version:

- **Putting the whole history in the prompt scored highest: 89%.** Plain vector retrieval on Postgres scored 86%, Mem0 83%. Those three are statistically tied on 60 questions.
- **Letta (70%) and Graphiti (69%) were clearly behind**, and the gap to the baselines is larger than chance.
- **The frameworks cost 60 to 300 times more to load than plain retrieval.** Graphiti read 3 million tokens to store an 85,000-token history.
- **None of the three frameworks can still be self-hosted in the form its vendor benchmarks.** That shaped the whole test, and it limits what these results say about the paid products.

## **The Test**

The questions come from [LongMemEval](https://github.com/xiaowu0162/LongMemEval) (the cleaned "S" release, MIT licence). Each question comes with its own chat history between one user and an assistant, and the answer is buried in one or more of those sessions. I picked it over LoCoMo, the benchmark most of the vendor fights are about, because LoCoMo's conversations fit in a context window, it has known wrong answers, it has no questions about facts that change, and its licence is non-commercial.

I sampled **60 questions, 10 from each of six types**, with a fixed seed:

| Type | What it asks |
| :---- | :---- |
| Single-session, user | A fact the user stated once |
| Single-session, assistant | Something the assistant said once ("what was the 7th job on that list?") |
| Multi-session | Counting or adding across several sessions |
| Temporal reasoning | "Which did I do first?", "how many weeks between…?" |
| Knowledge update | A fact that changed; the latest value is the right one |
| Abstention | The answer was never given; the right reply is "not enough information" |

Each question got a history of **24 sessions, about 85,000 tokens as Claude counts them**: every session that holds evidence, plus distractor sessions drawn from that question's own history. The published benchmark uses about 48 sessions; I halved it to keep the run to one night on a laptop. That makes this test easier than the published one.

**Scoring is deterministic.** Every setup must end its reply with a line `ANSWER: …`, or `ANSWER: NOT_ENOUGH_INFO`. A script compares that line with the gold answer. No judge model. To make that possible I only sampled questions whose gold answer is four words or fewer (349 of the 500), and left out the 30 "preference" questions, which need a judge. Before spending anything I checked the scorer with scripted answerers: a perfect one scores 100%, two wrong ones score 0%.

Each setup loaded a history once and then answered the question **three times**, so I could see how stable the answers are. That is 300 loads and 900 answers.

## **The Five Setups**

Everything used `claude-haiku-5-5` for both the memory work and the final answer, and OpenAI `text-embedding-3-small` for embeddings. Every model call went through one local proxy that counted tokens and dollars the same way for all five.

| Setup | What it does |
| :---- | :---- |
| **Full context** | No memory system. All 24 sessions go in the prompt, in date order. |
| **pgvector retrieval** | Each user turn plus the reply is one chunk in Postgres with pgvector. The 10 closest chunks go in the prompt. About 50 lines of code. |
| **Mem0** (open source 2.2.1) | An LLM extracts short "memories" from each session into pgvector. The top 20 go in the prompt. Library defaults. |
| **Graphiti** (0.31.2) | Zep's open-source engine. An LLM builds a knowledge graph in Neo4j with facts that carry valid-from and valid-until dates. Hybrid search returns 20 facts and entities. |
| **Letta** (server 0.15.1) | The MemGPT design: an agent that edits its own core memory, files details in an archive and searches them with tools. It reads each session as a message, then answers the question itself. |

### **What "self-hosted" turned out to mean**

This was the first finding, before any question was asked:

- **Mem0:** the open-source library no longer has graph memory, and it rejects timestamps on memories; both are now Platform-only. Mem0's published scores are for the Platform.
- **Zep:** the self-hosted Community Edition was discontinued in April 2025. Graphiti, the graph engine underneath, is what you can run. It is not Zep Cloud.
- **Letta:** the self-hosted Python server is retired. Current Docker images contain a different product, Letta Code, with file-based memory and no Python SDK. I used the last image of the old server, from November 2025.

So this is a test of what you can run on your own machine today without an account. It is not a test of the three paid products.

## **The Results**

| Setup | Correct (of 60) | Accuracy | Load time per history | Load cost per history | Cost per answer | Cost per correct answer |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| Full context | 53.3 | **89%** | 0 | $0 | $0.0100 | $0.011 |
| pgvector retrieval | 51.7 | **86%** | 1.4 s | $0.0011 | $0.0009 | **$0.0024** |
| Mem0 | 49.7 | **83%** | 6.9 min | $0.067 | $0.0003 | $0.081 |
| Letta | 42.0 | **70%** | 3.1 min | $0.138 | $0.0047 | $0.20 |
| Graphiti | 41.3 | **69%** | 4.4 min | $0.325 | $0.0005 | $0.47 |

"Correct" is the average over the three answers, which is why it has decimals. Cost per correct answer counts the load once and one answer.

Answer latency was similar for all five: a median of 1.9 to 3.3 seconds including retrieval. Letta was slowest at the tail (6.9 seconds at the 90th percentile) because it makes its own tool calls before answering.

### **How sure is the ranking?**

Sixty questions is not many. Comparing setups question by question (a sign test on the questions where two setups disagree):

- **Full context, pgvector and Mem0 are tied.** They disagreed on only 4 to 8 questions, and the split is well within chance.
- **Graphiti is behind full context (p = 0.004) and pgvector (p = 0.03).**
- **Letta is behind full context (p = 0.01).** Against pgvector it lost 11 questions and won 4, which is suggestive but not conclusive (p = 0.12).
- **Mem0 against Letta or Graphiti is not settled** at this sample size.

### **By question type**

| Setup | User fact | Assistant fact | Multi-session | Temporal | Knowledge update | Abstention |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| Full context | 10 | 10 | 6.7 | 8.7 | 10 | 8 |
| pgvector retrieval | 10 | 10 | 6 | 8.7 | 9 | 8 |
| Mem0 | 10 | 8.7 | 6 | 7 | 10 | 8 |
| Letta | 9.7 | 6.3 | 5 | 4 | 8 | 9 |
| Graphiti | 6.7 | 5.7 | 6.3 | 8 | 6 | 8.7 |

Each cell is out of 10, so read these as hints, not measurements. Three things stand out:

- **Counting across sessions is hard for everyone.** No setup passed 7 of 10. Two questions were missed by all five, and on one of them all five gave the same answer (300 points, gold says 100), which may be a problem with the gold answer.
- **Extraction loses what the assistant said.** Mem0, Letta and Graphiti all dropped points on "what did you tell me earlier?" questions. Their extraction is built around facts about the user. Raw chunks keep everything.
- **The temporal graph did not win on changed facts.** Graphiti's design is built for facts that change over time, and it scored 6 of 10 on knowledge updates, where full context and Mem0 scored 10. It also answered "not enough information" on simple facts such as what time the user gets home. Its temporal score (8) was good.

## **Where the Money Goes**

The frameworks are cheap to query and expensive to load. To store one 85,000-token history:

| Setup | Model calls to load | Tokens read to load | Multiple of the history |
| :---- | :---- | :---- | :---- |
| pgvector retrieval | 2 (embeddings) | 54,000 | 0.6× |
| Mem0 | 95 | 420,000 | 5× |
| Letta | 54 | 1,180,000 | 14× |
| Graphiti | 310 | 3,030,000 | 36× |

Graphiti runs several LLM passes per session: extract entities, resolve them against the graph, extract facts, check for contradictions, summarise. That is the design, and it is why loading 60 histories cost $19.52 of the run's $34.87.

Whether that pays back depends on how often you ask. Against putting the whole history in the prompt, at these prices:

- **Mem0 breaks even after about 7 questions** on the same history.
- **Graphiti breaks even after about 34.**
- **pgvector breaks even on the first question,** and no framework ever catches it on cost.

The full-context baseline also gets worse as history grows. At 85,000 tokens an answer cost one cent. The benchmark's full histories are about twice that, which crosses Haiku's 100,000-token price tier, and an answer would cost roughly eight cents. Past the context window it stops working at all. That is the real case for a memory system, and this test, at 24 sessions, does not reach it.

## **One Odd Result: Ask Letta Twice**

Letta's three answers were not independent, because the agent remembers being asked. That turned out to be informative. On the first ask it got 38 of 60. On the second and third it got 44. In eight cases it said "not enough information", was asked the identical question again, searched its archive properly and found the answer.

The memory was there. The agent, running on Haiku, did not always look hard enough the first time. The other four setups moved by at most three questions between asks.

## **What This Does Not Show**

- **It is not the paid products.** Mem0 Platform, Zep Cloud and current Letta are different systems from what I ran.
- **Haiku 5.5 did all the memory work.** These frameworks default to OpenAI models and tune their prompts for them. My OpenAI key could not call Chat Completions, so I could not use the defaults. A stronger extraction model may well lift Graphiti and Letta; it would also multiply the load cost.
- **Graphiti ran without its default reranker,** for the same reason. I used its documented RRF search recipe instead.
- **I ran documented defaults, not tuned setups.** One session per Graphiti episode, 20 results, no tuning. Someone who knows these tools well could do better.
- **Letta answered with its own agent loop,** not through the shared answerer. Same model, same instructions, more model calls.
- **Histories were halved** to 24 sessions, which favours full context and makes retrieval easier.
- **Deterministic scoring covers 349 of the benchmark's 500 questions.** I read every answer marked wrong. Four were right in substance ("Ford F-150 pickup" for "Ford F-150 pickup truck"); I overrode those and list them in `results/overrides.json`. One near miss ("about 8.5 months" for "9 months") I left as wrong.
- **Each history was loaded once.** I measured how stable the answers are, not how stable the extraction is.
- **60 questions.** Differences of a few points mean nothing here.

## **What I Would Do**

1. **Start with the whole history in the prompt** until it stops fitting or the bill hurts. It was the most accurate thing I tested and it has no moving parts.
2. **Then add plain retrieval over raw turns.** It matched full context within noise, at a tenth of the cost per answer and a load cost near zero. It needs Postgres and an embedding call.
3. **Reach for an extraction framework when you need what it uniquely gives you:** small, readable memories you can show a user and let them edit (Mem0), or an explicit graph of entities and dated facts you can query directly (Graphiti). On recall alone, in this test, neither earned its load cost.
4. **Run your own matched test before believing a chart**, including mine. The harness is about 800 lines, and the full run cost $35.

All code, every answer and every model call's token count are in [jimmytoan/agent-memory-lab](https://github.com/jimmytoan/agent-memory-lab).
