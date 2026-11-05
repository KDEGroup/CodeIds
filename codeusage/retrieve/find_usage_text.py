import ast
import shutil
from pathlib import Path
from typing import List
from functools import lru_cache
from codeusage.utils.io import read_text
import contexttimer

from pydantic import BaseModel

class FindUsageTextTimeConsuming(BaseModel):
    index_ms: int = 0
    search_ms: int = 0


class UsageResult(BaseModel):
    file_path: Path
    matched_lineno: int
    start_lineno: int
    end_lineno: int
    code_block: str

def set_parent_links(node: ast.AST, parent: ast.AST = None):
    for child in ast.iter_child_nodes(node):
        setattr(child, 'parent', node)
        set_parent_links(child, child)


def is_in_import(node: ast.AST) -> bool:
    parent = getattr(node, 'parent', None)
    while parent:
        if isinstance(parent, (ast.Import, ast.ImportFrom)):
            return True
        parent = getattr(parent, 'parent', None)
    return False



def find_usages(
    repo_path: Path,
    target_name: str,
    context_lines: int = 3,
    max_usage_n: int | None = None,
    time_consuming: FindUsageTextTimeConsuming | None = None
    ) -> List[UsageResult]:
    if time_consuming is None:
        time_consuming = FindUsageTextTimeConsuming()
    """
    在 Python 代码仓库中，使用 AST 精确查找指定名称的使用位置（忽略 import 语句中的使用）。
    """
    all_results: List[UsageResult] = []

    if not repo_path.is_dir():
        raise ValueError(f"given path '{repo_path}' is not valid")

    for file_path in repo_path.rglob("*.py"):
        try:
            with contexttimer.Timer(factor=1000) as t:
                content = read_text(file_path)
                source_lines = content.splitlines()
                tree = ast.parse(content, filename=str(file_path))
                set_parent_links(tree)
            time_consuming.index_ms += round(t.elapsed)
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue

        for node in ast.walk(tree):
            with contexttimer.Timer(factor=1000) as t:
                is_match = False
                if isinstance(node, ast.Name) and node.id == target_name:
                    is_match = True
                elif isinstance(node, ast.Attribute) and node.attr == target_name:
                    is_match = True

                if is_match and hasattr(node, 'lineno') and not is_in_import(node):
                    matched_lineno_0_based = node.lineno - 1
                    start = max(0, matched_lineno_0_based - context_lines)
                    end = min(len(source_lines), matched_lineno_0_based + context_lines + 1)
                    block_slice = source_lines[start:end]
                    code_block_str = "\n".join(block_slice)

                    result_item = UsageResult(
                        file_path=file_path,
                        matched_lineno=matched_lineno_0_based,
                        start_lineno=start,
                        end_lineno=end,
                        code_block=code_block_str
                    )
                    all_results.append(result_item)
                time_consuming.search_ms += round(t.elapsed)

    # 去重
    with contexttimer.Timer(factor=1000) as t:
        unique_results: List[UsageResult] = []
        seen_locations = set()
        for res in all_results:
            location_key = (res.file_path, res.matched_lineno)
            if location_key not in seen_locations:
                unique_results.append(res)
                seen_locations.add(location_key)
    time_consuming.index_ms += round(t.elapsed)

    return unique_results