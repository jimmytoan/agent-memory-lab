"""LongMemEval-S (cleaned) loader, reproducible stratified sample, and reduced haystacks.

Sampling (all seeded, see sample()):
  * eligible questions = abstention questions (question_id ends with _abs) plus questions whose gold
    answer is short (<= 4 words), so they can be scored without an LLM judge;
    single-session-preference (rubric-graded) is excluded.
  * strata = knowledge-update, temporal-reasoning, multi-session, single-session-user,
    single-session-assistant, abstention. Within a stratum, questions are sorted by question_id and
    drawn with random.Random(f"{seed}:{stratum}").sample.
  * haystack for a question = all of its evidence sessions + distractor sessions drawn from that
    question's own LongMemEval-S haystack with random.Random(f"{seed}:{question_id}"), up to
    `haystack` sessions in total, kept in chronological order. haystack=0 keeps the full haystack.
"""
import json, random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

PATH = Path("data/longmemeval/longmemeval_s_cleaned.json")
SHA256 = "d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442"
STRATA = ["knowledge-update", "temporal-reasoning", "multi-session", "single-session-user",
          "single-session-assistant", "abstention"]


def parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y/%m/%d (%a) %H:%M")


@dataclass
class Session:
    sid: str
    date: datetime
    turns: list  # [{"role","content"}]
    is_evidence: bool = False

    def text(self) -> str:
        return "\n".join(f"{t['role']}: {t['content']}" for t in self.turns)


@dataclass
class Question:
    qid: str
    qtype: str
    stratum: str
    question: str
    answer: str
    date: datetime
    sessions: list = field(default_factory=list)

    @property
    def abstain(self) -> bool:
        return self.qid.endswith("_abs")


def stratum_of(rec) -> str:
    return "abstention" if rec["question_id"].endswith("_abs") else rec["question_type"]


def eligible(rec) -> bool:
    if rec["question_id"].endswith("_abs"):
        return True
    if rec["question_type"] == "single-session-preference":
        return False
    return len(str(rec["answer"]).split()) <= 4


def load_raw():
    return json.load(PATH.open())


def build(rec, haystack: int, seed: int) -> Question:
    ev = set(rec["answer_session_ids"])
    idx = list(range(len(rec["haystack_sessions"])))
    ev_idx = [i for i in idx if rec["haystack_session_ids"][i] in ev]
    other = [i for i in idx if i not in set(ev_idx)]
    if haystack and haystack < len(idx):
        rng = random.Random(f"{seed}:{rec['question_id']}")
        keep = set(ev_idx) | set(rng.sample(other, max(0, haystack - len(ev_idx))))
    else:
        keep = set(idx)
    sess = [Session(rec["haystack_session_ids"][i], parse_date(rec["haystack_dates"][i]),
                    [{"role": t["role"], "content": t["content"]} for t in rec["haystack_sessions"][i]],
                    i in set(ev_idx)) for i in sorted(keep)]
    sess.sort(key=lambda s: s.date)
    return Question(rec["question_id"], rec["question_type"], stratum_of(rec), rec["question"],
                    str(rec["answer"]), parse_date(rec["question_date"]), sess)


def sample(per_stratum: dict, haystack: int, seed: int = 20261116, raw=None) -> list:
    raw = raw or load_raw()
    out = []
    for st in STRATA:
        pool = sorted((r for r in raw if eligible(r) and stratum_of(r) == st), key=lambda r: r["question_id"])
        n = min(per_stratum.get(st, 0), len(pool))
        for rec in random.Random(f"{seed}:{st}").sample(pool, n):
            out.append(build(rec, haystack, seed))
    return out
