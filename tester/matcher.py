"""Forgiving name matching: finds a project, session or talent even when the typed name has another capitalization, extra spaces,
accents, a missing word or a typo. It never guesses silently: when two names are about equally close, the answer is "ambiguous"
with the candidates listed, and the caller asks the person. Numbers must match exactly (Audition 10 is not Audition 100).
"""
import difflib
import re
import unicodedata

MIN_SCORE = 0.70        # below this a name is not considered a match at all
CLEAR_MARGIN = 0.08     # the best match must beat the second by this much to be used without asking


def normalize(text):
    """Lowercase, no accents, no punctuation/emoji, single spaces. 'Nov-04  Café!' -> 'nov 04 cafe'."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(text):
    out = []
    for token in normalize(text).split():
        # '04' and '4' are the same number; letters and digits stuck together ('v2', '4th') stay one token.
        out.append(str(int(token)) if token.isdigit() else token)
    return out


def _token_score(wanted, have):
    if wanted == have:
        return 1.0
    if wanted.isdigit() or have.isdigit():
        return 0.0                                   # numbers never blur
    if len(wanted) >= 3 and (have.startswith(wanted) or wanted.startswith(have)):
        return 0.92                                  # nov / november
    if len(wanted) >= 4 and len(have) >= 4:
        ratio = difflib.SequenceMatcher(None, wanted, have).ratio()
        if ratio >= 0.78:
            return 0.6 + 0.4 * ratio * 0.9           # a typo: close, but less than a clean match
    return 0.0


def score(query, candidate):
    """0..1 how well `candidate` answers `query` (1.0 = the same name once capitalization/spacing/accents are ignored)."""
    q, c = tokens(query), tokens(candidate)
    if not q or not c:
        return 0.0
    if q == c:
        return 1.0
    numbers = [t for t in q if t.isdigit()]
    if any(n not in c for n in numbers):
        return 0.0
    per_token = []
    for token in q:
        per_token.append(max(_token_score(token, other) for other in c))
    best = sum(per_token) / len(per_token)
    if min(per_token) == 0.0:
        # words run together or split ('notme' / 'not me'): compare the whole text without spaces
        joined = difflib.SequenceMatcher(None, "".join(q), "".join(c)).ratio()
        if joined >= 0.88 and all(n in c for n in numbers):
            best = max(0.0, joined * 0.95)
        else:
            return 0.0
    coverage = min(1.0, len(q) / len(c))             # prefer the name that is fully described by the query
    return round(min(0.99, best * (0.85 + 0.15 * coverage)), 4)


def find(query, candidates, key=None):
    """Looks for `query` among `candidates` (strings, or any objects with `key(obj)` giving the name).

    Returns {"status": "found"|"ambiguous"|"none", "best": candidate or None, "score": float,
             "candidates": [(candidate, score), ...] (the closest three), "why": short sentence}."""
    name_of = key or (lambda item: item)
    scored = sorted(((item, score(query, name_of(item))) for item in candidates), key=lambda pair: -pair[1])
    close = [(item, s) for item, s in scored if s >= MIN_SCORE]
    nearest = scored[:3]
    if not close:
        return {"status": "none", "best": None, "score": 0.0, "candidates": nearest,
                "why": f"nothing is close to '{query}'" + (": nearest are " + ", ".join(f"'{name_of(i)}'" for i, _ in nearest) if nearest else "")}
    best, best_score = close[0]
    if best_score >= 1.0 and (len(close) == 1 or close[1][1] < 1.0):
        return {"status": "found", "best": best, "score": 1.0, "candidates": close[:3], "why": f"'{query}' is '{name_of(best)}'"}
    if len(close) > 1 and best_score - close[1][1] < CLEAR_MARGIN:
        names = ", ".join(f"'{name_of(i)}' ({round(s * 100)}%)" for i, s in close[:3])
        return {"status": "ambiguous", "best": None, "score": best_score, "candidates": close[:3],
                "why": f"'{query}' fits more than one name: {names}"}
    return {"status": "found", "best": best, "score": best_score, "candidates": close[:3],
            "why": f"'{query}' -> '{name_of(best)}' ({round(best_score * 100)}%)"}
