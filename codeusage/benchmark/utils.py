from pathlib import Path
from loguru import logger
import os
import json

def load_jsonl(fname: Path) -> list:
    with open(fname, 'r', encoding='utf8') as f:
        lines = []
        for line in f:
            lines.append(json.loads(line))
        return lines
