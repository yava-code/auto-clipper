import re

strategies = {
    "lines":     lambda t: [l.strip() for l in t.splitlines() if l.strip()],
    "comma":     lambda t: [x.strip() for x in t.split(',') if x.strip()],
    "sentences": lambda t: [s.strip() for s in re.split(r'(?<=[.!?])\s+', t.strip()) if s.strip()],
}


def parse(text, strategy="lines"):
    fn = strategies.get(strategy, strategies["lines"])
    return fn(text)
