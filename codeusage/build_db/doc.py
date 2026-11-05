from .common import Doc
from typing import List
from collections import defaultdict
from codeusage.utils.io import read_text
def merge_docs_by_reading_file(docs: List[Doc]) -> List[Doc]:
    path_groups = defaultdict(list)
    for doc in docs:
        path_groups[doc.path].append(doc)

    merged_results = []

    for path, group in path_groups.items():
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # 一次性读取整个文件内容
        lines = read_text(path).splitlines(keepends=True)

        group.sort(key=lambda d: d.start_line)

        merged_group = []
        for doc in group:
            if not merged_group:
                merged_group.append(doc)
                continue

            last = merged_group[-1]

            if doc.start_line <= last.end_line:
                new_start = last.start_line
                new_end = max(last.end_line, doc.end_line)
                new_content = "".join(lines[new_start:new_end])
                merged_group[-1] = Doc(
                    content=new_content,
                    path=path,
                    start_line=new_start,
                    end_line=new_end
                )
            else:
                merged_group.append(Doc(
                    content="".join(lines[doc.start_line:doc.end_line]),
                    path=path,
                    start_line=doc.start_line,
                    end_line=doc.end_line
                ))

        merged_results.extend(merged_group)

    return merged_results