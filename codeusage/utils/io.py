from functools import lru_cache
from pathlib import Path

# @lru_cache(1000)
def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")