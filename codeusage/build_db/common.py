from pydantic import BaseModel
from pathlib import Path
class Doc(BaseModel):
    content: str
    path: Path
    start_line: int
    end_line: int # exclusive

class Definition(BaseModel):
    path: Path
    content: str