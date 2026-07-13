import json
import os


def load_seen(path: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    with open(path) as f:
        return set(json.load(f))


def save_seen(path: str, ids: set[str]) -> None:
    with open(path, "w") as f:
        json.dump(sorted(ids), f, indent=2)
