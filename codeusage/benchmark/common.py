from pydantic import BaseModel
from pathlib import Path

class CodeRepo(BaseModel):
    name: str
    path: Path

class CodeLocation(BaseModel):
    path: Path
    start_line_no: int
    end_line_no: int

class BenchmarkItem(BaseModel):
    task_name: str
    code_context: str
    ground_truth: str

    repo: CodeRepo
    code_context_location: CodeLocation


class Benchmark(BaseModel):
    data_list: list[BenchmarkItem]
    repos: list[CodeRepo]

