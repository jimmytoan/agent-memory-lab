from lab.contestants.base import Contestant


def render(sessions) -> str:
    return "\n\n".join(f"### Session on {s.date:%Y-%m-%d (%A) %H:%M}\n{s.text()}" for s in sessions)


class FullContext(Contestant):
    name = "full-context"
    config = {"memory": "none; every session is placed in the prompt in chronological order"}
    def retrieve(self, q): return render(q.sessions)
