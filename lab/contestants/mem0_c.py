import os
os.environ["MEM0_TELEMETRY"] = "false"
from lab import llm
from lab.contestants.base import Contestant

MODEL = os.environ.get("MEMORY_LLM", "claude-haiku-5-5")


class Mem0(Contestant):
    name = "mem0"
    config = {"package": "mem0ai 2.2.1 (open source, in-process)", "llm": MODEL, "embedder": llm.EMBED_MODEL,
              "vector_store": "pgvector (HNSW, mem0 default)", "ingest": "one Memory.add(messages, infer=True) per session",
              "dates": "OSS add() rejects timestamps, so the session date is the first line of the session's first message and is stored in metadata",
              "search": "top_k=20, threshold=0.1, rerank=False (mem0 defaults)", "graph_memory": "not available in OSS 2.x"}

    def setup(self):
        from mem0 import Memory
        self.m = Memory.from_config({
            "llm": {"provider": "anthropic", "config": {"model": MODEL, "max_tokens": 8000,
                                                         "anthropic_base_url": f"{llm.PROXY}/anthropic"}},
            "embedder": {"provider": "openai", "config": {"model": llm.EMBED_MODEL, "openai_base_url": f"{llm.PROXY}/openai/v1"}},
            "vector_store": {"provider": "pgvector", "config": {
                "connection_string": "postgresql://lab:lab@127.0.0.1:55432/lab", "collection_name": "mem0_lab",
                "embedding_model_dims": 1536}},
            "history_db_path": "results/mem0_history.db",
        })

    def ingest(self, q):
        self.m.delete_all(user_id=q.qid)
        for s in q.sessions:
            stamp = f"{s.date:%Y-%m-%d (%A) %H:%M}"
            msgs = [dict(t) for t in s.turns]
            msgs[0]["content"] = f"[This conversation took place on {stamp}]\n{msgs[0]['content']}"
            self.m.add(msgs, user_id=q.qid, metadata={"session_date": stamp})

    def retrieve(self, q):
        hits = self.m.search(q.question, filters={"user_id": q.qid}, top_k=20, threshold=0.1, rerank=False)["results"]
        rows = sorted(((h.get("metadata") or {}).get("session_date", ""), h["memory"]) for h in hits)
        return "\n".join(f"- [{d}] {m}" for d, m in rows)

    def cleanup(self, q):
        self.m.delete_all(user_id=q.qid)
