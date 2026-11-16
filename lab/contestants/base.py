from lab import llm


class Contestant:
    """ingest() stores one user's sessions; retrieve() returns the memory text given to the shared
    answerer. A contestant whose retrieval cannot be separated from answering (Letta) overrides answer()."""
    name = "base"
    config: dict = {}

    def setup(self): ...
    def ingest(self, q): ...                      # q: dataset.Question (uses q.qid, q.sessions)
    def retrieve(self, q) -> str: raise NotImplementedError
    def cleanup(self, q): ...

    def answer(self, q):
        ctx = self.retrieve(q)
        return llm.answer(q.question, ctx, q.date), ctx


class Scripted(Contestant):
    """No model calls: used to self-test the harness and scorer."""
    def __init__(self, mode): self.mode, self.name = mode, f"scripted-{mode}"
    def answer(self, q):
        if self.mode == "perfect":
            return ("ANSWER: NOT_ENOUGH_INFO" if q.abstain else f"Thinking.\nANSWER: {q.answer}"), ""
        if self.mode == "wrong":
            return ("ANSWER: 7 purple elephants" if q.abstain else "ANSWER: NOT_ENOUGH_INFO"), ""
        return "ANSWER: a plausible but wrong thing 987654", ""
