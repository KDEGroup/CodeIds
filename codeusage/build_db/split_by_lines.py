from pathlib import Path
from pydantic import BaseModel
from .common import Doc
import os


def split_by_lines(
    repo_path: str | Path,
    each_line_n: int,
    overlap: int
) -> list[Doc]:
    repo_path = Path(repo_path)
    all_docs: list[Doc] = []

    if overlap >= each_line_n:
        raise ValueError("Overlap must be less than each_line_n")

    for dirpath, _, filenames in os.walk(repo_path):
        for filename in filenames:
            file_path = Path(dirpath) / filename
            if not filename.endswith(".py"):
                continue
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                if not lines:
                    continue

                start_line_idx = 0
                total_lines = len(lines)
                while start_line_idx < total_lines:
                    end_line_idx_exclusive = min(start_line_idx + each_line_n, total_lines)
                    
                    chunk_lines = lines[start_line_idx:end_line_idx_exclusive]
                    
                    content = "".join(chunk_lines).rstrip('\n')

                    if content:
                        doc = Doc(
                            content=content,
                            path=file_path,
                            start_line=start_line_idx, 
                            end_line=end_line_idx_exclusive 
                        )
                        all_docs.append(doc)
                    
                    step = each_line_n - overlap
                    start_line_idx += step

            except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError):
                continue
                
    return all_docs
