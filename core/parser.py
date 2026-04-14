import re


def parse(text, strategy="lines", delimiter=";",
          custom_mode="delimiter", regex_pattern=""):
    if strategy == "lines":
        return [l.strip() for l in text.splitlines() if l.strip()]
    if strategy == "comma":
        return [x.strip() for x in text.split(',') if x.strip()]
    if strategy == "sentences":
        return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]
    if strategy == "custom":
        if custom_mode == "regex_split":
            pat = regex_pattern or r'\s+'
            return [x.strip() for x in re.split(pat, text) if x.strip()]
        if custom_mode == "regex_findall":
            pat = regex_pattern or r'\S+'
            return re.findall(pat, text)
        return [x.strip() for x in text.split(delimiter) if x.strip()]
    return [text]


def transform(items, prefix="", suffix=""):
    if not prefix and not suffix:
        return items
    return [f"{prefix}{x}{suffix}" for x in items]
