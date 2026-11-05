from codeusage.build_db import Doc
from pathlib import Path
from pydantic import BaseModel
from codeusage.utils.time_consuming import TimeComsuming
from codeusage.utils.io import read_text

class IdUsages(BaseModel):
    id: str
    usages: list[Doc]

class RetrievalResultItem(BaseModel):
    definitions: list[str]
    usages: list[IdUsages]
    sparse_retrievals: list[Doc]
    time_consuming: TimeComsuming

class RetrievalResult(BaseModel):
    data_list: list[RetrievalResultItem]
    average_time_consuming: TimeComsuming

def get_file_lines(
    file_path: Path,
    line: int,
    line_n: int
):
    lines = read_text(file_path).splitlines(keepends=True)
    start = max(0, line - line_n)
    end = min(len(lines), line + line_n + 1)
    lines = lines[start: end]
    return "\n".join(lines)