"""USD per million tokens. Sources recorded in PLAN.md. Update here only."""
PRICES = {
    # model: (input, output, cache_read, cache_write)
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),   # prompts <=100K tokens
    "claude-haiku-5-5:long": (0.50, 2.50, 0.05, 0.625),  # prompts >100K tokens
    "claude-sonnet-5-5": (2.00, 10.00, 0.10, 2.50),
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
    "text-embedding-3-small": (0.02, 0.0, 0.0, 0.0),
    "text-embedding-3-large": (0.13, 0.0, 0.0, 0.0),
}


def cost(model: str, inp: int, out: int, cache_read: int = 0, cache_write: int = 0) -> float:
    key = model
    if model.startswith("claude-haiku-5-5") and (inp + cache_read + cache_write) > 100_000:
        key = "claude-haiku-5-5:long"
    for k in (key, *[p for p in PRICES if model.startswith(p)]):
        if k in PRICES:
            pi, po, pr, pw = PRICES[k]
            return (inp * pi + out * po + cache_read * pr + cache_write * pw) / 1e6
    return float("nan")
