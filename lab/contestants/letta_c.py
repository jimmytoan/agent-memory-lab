import os
from lab import llm
from lab.contestants.base import Contestant

MODEL = os.environ.get("MEMORY_LLM", "claude-haiku-5-5")
URL = "http://127.0.0.1:58283"
PERSONA = ("I am a personal assistant with long-term memory. I keep durable facts about the user in my core memory, "
           "store details in archival memory, and search my memory before answering questions about the past.")


class LettaC(Contestant):
    name = "letta"
    config = {"server": "letta/letta:0.15.1 Docker image (last image of the retired Python server), letta-client 1.12.1",
              "llm": f"anthropic/{MODEL}", "embedder": llm.EMBED_MODEL, "context_window_limit": 32000,
              "memory": "default base tools: core memory blocks (human, persona), archival memory, conversation search",
              "ingest": "each session is sent to the agent as one user message containing the dated transcript",
              "answer": "the agent answers itself (its retrieval is tool calls); the shared answer instructions are placed in the question message"}

    def setup(self):
        from letta_client import Letta
        self.c = Letta(base_url=URL, timeout=900)
        self.agents = {}

    def ingest(self, q):
        a = self.c.agents.create(
            name=f"lab-{q.qid}"[:48], model=f"anthropic/{MODEL}", context_window_limit=32000,
            embedding_config={"embedding_endpoint_type": "openai", "embedding_endpoint": "http://host.docker.internal:8177/openai/v1",
                              "embedding_model": llm.EMBED_MODEL, "embedding_dim": 1536, "embedding_chunk_size": 300},
            memory_blocks=[{"label": "human", "value": "", "limit": 5000}, {"label": "persona", "value": PERSONA, "limit": 2000}],
            include_base_tools=True)
        self.agents[q.qid] = a.id
        for s in q.sessions:
            body = (f"[Log of a past conversation between me (the user) and my assistant, dated {s.date:%Y-%m-%d (%A) %H:%M}. "
                    f"Remember what matters from it; no reply to its content is needed.]\n\n{s.text()}")
            self.c.agents.messages.create(agent_id=a.id, messages=[{"role": "user", "content": body}])

    def answer(self, q):
        msg = (f"{llm.answer_instructions(q.date)}\n\nHere MEMORY means your own memory: search it with your tools before answering."
               f"\n\nQUESTION: {q.question}")
        r = self.c.agents.messages.create(agent_id=self.agents[q.qid], messages=[{"role": "user", "content": msg}])
        text, trace = "", []
        for m in r.messages:
            t = getattr(m, "message_type", "")
            if t == "assistant_message":
                c = m.content if isinstance(m.content, str) else " ".join(getattr(p, "text", "") for p in m.content)
                text += c + "\n"
            elif t == "tool_call_message":
                trace.append(f"CALL {m.tool_call.name} {m.tool_call.arguments}")
            elif t == "tool_return_message":
                trace.append(f"RETURN {str(m.tool_return)}")
        return text, "\n".join(trace)

    def cleanup(self, q):
        if q.qid in self.agents:
            self.c.agents.delete(self.agents.pop(q.qid))
