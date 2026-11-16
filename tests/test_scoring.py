"""Self-test of sampling and scoring with scripted answerers. No model calls."""
import pytest
from lab import dataset, scoring
from lab.contestants.base import Scripted

RAW = dataset.load_raw()
ALL = {st: 999 for st in dataset.STRATA}


@pytest.fixture(scope="module")
def qs():
    return dataset.sample(ALL, haystack=10, raw=RAW)


def run(mode, qs):
    c = Scripted(mode)
    return [scoring.score(q.answer, c.answer(q)[0], q.qtype, q.abstain) for q in qs]


def test_perfect_answerer_scores_100(qs):
    r = run("perfect", qs)
    assert all(r), [q.answer for q, ok in zip(qs, r) if not ok][:10]


def test_wrong_answerers_score_0(qs):
    assert not any(run("wrong", qs))
    assert not any(run("offtopic", qs))


def test_sampling_reproducible_and_keeps_evidence(qs):
    a = dataset.sample({st: 3 for st in dataset.STRATA}, 10, raw=RAW)
    b = dataset.sample({st: 3 for st in dataset.STRATA}, 10, raw=RAW)
    assert [q.qid for q in a] == [q.qid for q in b]
    assert [[s.sid for s in q.sessions] for q in a] == [[s.sid for s in q.sessions] for q in b]
    by = {r["question_id"]: r for r in RAW}
    for q in qs:
        assert set(by[q.qid]["answer_session_ids"]) <= {s.sid for s in q.sessions}
        assert len(q.sessions) >= min(10, len(by[q.qid]["haystack_sessions"]))
        assert q.sessions == sorted(q.sessions, key=lambda s: s.date)


@pytest.mark.parametrize("gold,resp,qtype,abst,ok", [
    ("Target", "Probably Walmart or Target.\nANSWER: Target", "single-session-user", False, True),
    ("Target", "ANSWER: Walmart", "single-session-user", False, False),
    ("Target", "I think Target\nANSWER: NOT_ENOUGH_INFO", "single-session-user", False, False),
    ("Target", "It was Target.", "single-session-user", False, False),          # no ANSWER line
    ("six", "ANSWER: 6 times", "knowledge-update", False, True),
    ("6", "ANSWER: 16", "knowledge-update", False, False),
    ("$50", "ANSWER: $500", "multi-session", False, False),
    ("$1,200", "ANSWER: $1200.00", "multi-session", False, True),
    ("6:00 pm", "ANSWER: 6:00 PM", "knowledge-update", False, True),
    ("4 days.", "ANSWER: 5 days ago", "temporal-reasoning", False, True),     # off-by-one allowed
    ("4 days.", "ANSWER: 6 days", "temporal-reasoning", False, False),
    ("4 days", "ANSWER: 5 days", "multi-session", False, False),              # only for temporal
    ("14 days. 15 days (including the last day) is also acceptable.", "ANSWER: 15 days", "temporal-reasoning", False, True),
    ("8 days.", "ANSWER: 8", "multi-session", False, True),                   # bare number for a count
    ("1 week", "ANSWER: 1", "temporal-reasoning", False, True),
    ("8 days.", "ANSWER: 18", "multi-session", False, False),
    ("8 days.", "ANSWER: 8 weeks", "multi-session", False, False),
    ("You did not mention this.", "ANSWER: NOT_ENOUGH_INFO", "multi-session", True, True),
    ("You did not mention this.", "ANSWER: 30 minutes", "multi-session", True, False),
    ("University of California, Los Angeles (UCLA)", "ANSWER: University of California Los Angeles", "single-session-user", False, True),
])
def test_cases(gold, resp, qtype, abst, ok):
    assert scoring.score(gold, resp, qtype, abst) is ok
