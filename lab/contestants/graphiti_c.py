import asyncio, os, re
from datetime import timezone
os.environ["GRAPHITI_TELEMETRY_ENABLED"] = "false"
os.environ.setdefault("SEMAPHORE_LIMIT", "4")
from lab import llm
from lab.contestants.base import Contestant

MODEL = os.environ.get("MEMORY_LLM", "claude-haiku-5-5")
EPISODE = os.environ.get("GRAPHITI_EPISODE", "session")   # session | exchange


class GraphitiC(Contestant):
    name = "graphiti"
    config = {"package": "graphiti-core 0.31.2 (open-source engine behind Zep)", "graph_db": "Neo4j 5.26 community",
              "llm": MODEL, "small_llm": MODEL, "embedder": llm.EMBED_MODEL, "episode": EPISODE,
              "ingest": "add_episode(EpisodeType.message, reference_time=session date), sequential, one group_id per user",
              "search": "search_(COMBINED_HYBRID_SEARCH_RRF, limit=20): facts with valid/invalid dates + entity summaries",
              "reranker": "none (RRF); the default cross-encoder needs OpenAI chat completions", "SEMAPHORE_LIMIT": 4}

    def setup(self):
        from anthropic import AsyncAnthropic
        from graphiti_core import Graphiti
        from graphiti_core.llm_client.anthropic_client import AnthropicClient, LLMConfig
        from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
        from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
        self.loop = asyncio.new_event_loop()
        key = os.environ["ANTHROPIC_API_KEY"]
        self.g = Graphiti("bolt://127.0.0.1:57687", "neo4j", "agentmemlab",
            llm_client=AnthropicClient(config=LLMConfig(api_key=key, model=MODEL, small_model=MODEL),
                                       client=AsyncAnthropic(api_key=key, base_url=f"{llm.PROXY}/anthropic", max_retries=4)),
            embedder=OpenAIEmbedder(config=OpenAIEmbedderConfig(api_key=os.environ["OPENAI_API_KEY"],
                                    embedding_model=llm.EMBED_MODEL, base_url=f"{llm.PROXY}/openai/v1")),
            cross_encoder=OpenAIRerankerClient(config=LLMConfig(api_key=os.environ["OPENAI_API_KEY"], base_url=f"{llm.PROXY}/openai/v1")))
        self.loop.run_until_complete(self.g.build_indices_and_constraints())

    @staticmethod
    def gid(q): return re.sub(r"[^A-Za-z0-9_]", "_", q.qid)

    def _episodes(self, s):
        if EPISODE == "session":
            return [s.text()]
        out, buf = [], []
        for t in s.turns:
            if t["role"] == "user" and buf:
                out.append("\n".join(buf)); buf = []
            buf.append(f"{t['role']}: {t['content']}")
        return out + (["\n".join(buf)] if buf else [])

    def ingest(self, q):
        from graphiti_core.nodes import EpisodeType
        self.cleanup(q)
        async def go():
            for s in q.sessions:
                for i, body in enumerate(self._episodes(s)):
                    await self.g.add_episode(name=f"{s.sid}-{i}", episode_body=body, source=EpisodeType.message,
                        source_description="chat between the user and their assistant",
                        reference_time=s.date.replace(tzinfo=timezone.utc), group_id=self.gid(q))
        self.loop.run_until_complete(go())

    def retrieve(self, q):
        from graphiti_core.search.search_config_recipes import COMBINED_HYBRID_SEARCH_RRF
        cfg = COMBINED_HYBRID_SEARCH_RRF.model_copy(deep=True); cfg.limit = 20
        r = self.loop.run_until_complete(self.g.search_(q.question, config=cfg, group_ids=[self.gid(q)]))
        d = lambda x: x.strftime("%Y-%m-%d") if x else None
        facts = sorted(r.edges, key=lambda e: (e.valid_at or e.created_at).timestamp())
        lines = ["FACTS (valid_from -> valid_until; 'present' means still true):"]
        lines += [f"- [{d(e.valid_at) or 'unknown'} -> {d(e.invalid_at) or 'present'}] {e.fact}" for e in facts]
        lines += ["ENTITIES:"] + [f"- {n.name}: {n.summary}" for n in r.nodes]
        return "\n".join(lines)

    def cleanup(self, q):
        async def go():
            await self.g.driver.execute_query("MATCH (n {group_id: $g}) DETACH DELETE n", g=self.gid(q))
        self.loop.run_until_complete(go())
