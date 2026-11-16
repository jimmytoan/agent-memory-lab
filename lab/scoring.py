"""Deterministic scoring. No model calls.

The answerer must end with a line `ANSWER: <short answer>`; only that line is scored.
  * abstention question: correct iff the answer line is NOT_ENOUGH_INFO.
  * otherwise: wrong if NOT_ENOUGH_INFO; correct iff the normalised gold answer (or any accepted
    alternative written in the gold, e.g. "14 days. 15 days ... is also acceptable") is contained
    in the normalised answer line on word boundaries, or the gold is "<number> <unit>" and
    the answer line is exactly that number. For temporal-reasoning questions whose gold is
    a count of days/weeks/months, off-by-one is accepted, as in LongMemEval's own judge prompt.
"""
import re

SENTINEL = "NOT_ENOUGH_INFO"
WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
         "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
         "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
         "forty": 40, "fifty": 50, "once": 1, "twice": 2}
STOP = {"a", "an", "the", "about", "around", "approximately", "roughly"}
UNIT = {"days": "day", "weeks": "week", "months": "month", "years": "year", "hours": "hour", "minutes": "minute",
        "times": "time", "mins": "minute", "hrs": "hour"}


def extract(response: str) -> str:
    m = re.findall(r"ANSWER:\s*(.+)", response or "")
    return m[-1].strip() if m else ""


def norm(s: str) -> str:
    s = str(s).lower().replace(",", "")
    s = re.sub(r"\(.*?\)", " ", s)                      # drop parentheticals: "UCLA (…)" etc.
    s = re.sub(r"(?<=\d)\s*(am|pm)\b", r" \1", s)
    s = re.sub(r"\$\s*", "$", s)
    s = re.sub(r"[^\w$%.:/' -]", " ", s)
    toks = []
    for t in s.replace("-", " ").split():
        t = t.strip(".'")
        if t in STOP or not t:
            continue
        if t in WORDS:
            t = str(WORDS[t])
        t = UNIT.get(t, t)
        t = re.sub(r"^(\$?\d+)\.0+$", r"\1", t)
        t = re.sub(r"^(\d+)(st|nd|rd|th)$", r"\1", t)
        toks.append(t)
    return " ".join(toks)


def golds(answer: str) -> list:
    """Gold plus alternatives the dataset itself lists as acceptable."""
    parts = [answer]
    if re.search(r"acceptable", answer, re.I):
        parts = re.split(r"\.\s+", re.sub(r"\(.*?\)", "", answer))
        parts = [re.sub(r"\s*(is|are)\s+also\s+acceptable.*", "", p, flags=re.I) for p in parts]
    return [g for g in (norm(p) for p in parts) if g]


def contains(hay: str, needle: str) -> bool:
    return re.search(r"(?<![\w$])" + re.escape(needle) + r"(?![\w%])", hay) is not None


def score(answer_gold: str, response: str, qtype: str, abstain: bool) -> bool:
    line = extract(response)
    if abstain:
        return SENTINEL in line
    if not line or SENTINEL in line:
        return False
    hyp = norm(line)
    cands = golds(answer_gold)
    if qtype == "temporal-reasoning":
        extra = []
        for g in cands:
            m = re.fullmatch(r"(\d+) (day|week|month|year)", g)
            if m:
                n = int(m.group(1))
                extra += [f"{k} {m.group(2)}" for k in (n - 1, n + 1) if k >= 0]
        cands += extra
    if any(contains(hyp, g) for g in cands):
        return True
    # a bare number answers a count question: gold "8 days" vs answer line "8"
    bare = {m.group(1) for g in cands if (m := re.fullmatch(r"(\$?\d+(?:\.\d+)?) [a-z]+", g))}
    return hyp in bare
