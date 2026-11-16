"""Take-length profiles and the time / disk estimate shown before a run starts. Lengths are random from the run's seed."""
import shutil

# seconds (min, max)
PROFILES = {
    "short": (30, 60),
    "normal": (60, 300),
    "long": (25 * 60, 50 * 60),
}
LABELS = {
    "short": "Short (30 s to 1 min)",
    "normal": "Normal (1 to 5 min)",
    "long": "Long (25 to 50 min)",
    "mixed": "Mixed (each take picks Short, Normal or Long)",
}
DEFAULT_MIX = {"short": 50, "normal": 40, "long": 10}      # percent
MB_PER_SECOND = 0.55          # measured: a 29 min take is about 890 MB


def parse_mix(text):
    """'50/40/10' or {'short': 50, ...} -> weights; falls back to the default for anything unusable."""
    try:
        if isinstance(text, dict):
            values = [float(text.get(k, 0)) for k in ("short", "normal", "long")]
        else:
            values = [float(part) for part in str(text).replace(",", "/").split("/")]
        if len(values) == 3 and all(v >= 0 for v in values) and sum(values) > 0:
            return dict(zip(("short", "normal", "long"), values))
    except (TypeError, ValueError):
        pass
    return dict(DEFAULT_MIX)


def pick_kind(profile, rnd, mix=None):
    if profile in PROFILES:
        return profile
    weights = parse_mix(mix or DEFAULT_MIX)
    return rnd.choices(list(weights), weights=list(weights.values()))[0]


def pick_length(profile, rnd, mix=None):
    """(kind, seconds) for one take."""
    kind = pick_kind(profile, rnd, mix)
    low, high = PROFILES[kind]
    return kind, rnd.randint(low, high)


def estimate(takes, profile, mix=None, seconds_overhead=25):
    """Expected total recording seconds and disk MB for `takes` takes (average length, not a promise)."""
    if profile in PROFILES:
        average = sum(PROFILES[profile]) / 2
    else:
        weights = parse_mix(mix or DEFAULT_MIX)
        total = sum(weights.values())
        average = sum(weights[k] / total * sum(PROFILES[k]) / 2 for k in PROFILES)
    seconds = takes * (average + seconds_overhead)
    return {"seconds": int(seconds), "disk_mb": int(takes * average * MB_PER_SECOND), "average_take_seconds": int(average)}


def free_disk_mb(path="/"):
    return shutil.disk_usage(path).free // (1024 * 1024)


def disk_problem(takes, profile, mix=None, path="/", keep_free_mb=5000):
    """A plain sentence when the disk is too small for this run, otherwise None."""
    need = estimate(takes, profile, mix)["disk_mb"] + keep_free_mb
    have = free_disk_mb(path)
    if have < need:
        return f"This run needs about {need // 1024} GB free (it keeps 5 GB spare) and this Mac has {have // 1024} GB. Choose shorter takes or fewer."
    return None


def describe(seconds):
    hours, rest = divmod(int(seconds), 3600)
    minutes = rest // 60
    return f"{hours} h {minutes} min" if hours else f"{minutes} min"
