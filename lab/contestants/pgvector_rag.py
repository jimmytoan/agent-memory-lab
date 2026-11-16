import psycopg
from pgvector.psycopg import register_vector
import numpy as np
from lab import llm
from lab.contestants.base import Contestant

DSN = "postgresql://lab:lab@127.0.0.1:55432/lab"


class PgvectorRAG(Contestant):
    name = "pgvector-rag"
    config = {"chunk": "one user turn + the assistant reply that follows, prefixed with the session date",
              "embedder": llm.EMBED_MODEL, "top_k": 10, "index": "exact cosine (no ANN index)", "llm_at_ingest": "none"}

    def setup(self):
        self.db = psycopg.connect(DSN, autocommit=True)
        self.db.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(self.db)
        self.db.execute("CREATE TABLE IF NOT EXISTS rag_chunks (id bigserial PRIMARY KEY, qid text, ts timestamp, body text, emb vector(1536))")
        self.db.execute("CREATE INDEX IF NOT EXISTS rag_qid ON rag_chunks(qid)")

    def ingest(self, q):
        self.db.execute("DELETE FROM rag_chunks WHERE qid=%s", (q.qid,))
        chunks = []
        for s in q.sessions:
            buf = []
            for t in s.turns:
                if t["role"] == "user" and buf:
                    chunks.append((s.date, "\n".join(buf))); buf = []
                buf.append(f"{t['role']}: {t['content']}")
            if buf:
                chunks.append((s.date, "\n".join(buf)))
        texts = [f"[{d:%Y-%m-%d (%A) %H:%M}]\n{b}" for d, b in chunks]
        embs = llm.embed(texts)
        with self.db.cursor() as cur:
            cur.executemany("INSERT INTO rag_chunks (qid, ts, body, emb) VALUES (%s,%s,%s,%s)",
                            [(q.qid, d, t, np.array(e)) for (d, _), t, e in zip(chunks, texts, embs)])

    def retrieve(self, q):
        e = np.array(llm.embed([q.question])[0])
        rows = self.db.execute("SELECT ts, body FROM rag_chunks WHERE qid=%s ORDER BY emb <=> %s LIMIT %s",
                               (q.qid, e, self.config["top_k"])).fetchall()
        return "\n\n".join(b for _, b in sorted(rows))

    def cleanup(self, q):
        self.db.execute("DELETE FROM rag_chunks WHERE qid=%s", (q.qid,))
