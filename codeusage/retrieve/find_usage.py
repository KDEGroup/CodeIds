import jedi.cache
from codeusage.build_query.infer_nodes import InferResult, IdInfo
from codeusage.build_db import Doc
from pydantic import BaseModel
from pathlib import Path
from codeusage.build_db import merge_docs_by_reading_file
from .find_usage_text import find_usages as find_usages_text
from .find_usage_text import FindUsageTextTimeConsuming
import jedi
import jedi.api
from .common import get_file_lines
from codeusage.utils import exception_handler_wrapper
from codeusage.config import settings
import contexttimer
import time
from typing import TypedDict

DEFAULT_STATIC_USAGE_TIMEOUT_S = 5

class UsageTimeConsuming(BaseModel):
    static_usage_ms: int = 0
    ast_usage_ms: int = 0

class IdInfoUsages(BaseModel):
    id_info: IdInfo
    usages: list[Doc]

class ProcessJediResult(TypedDict):
    docs: list[Doc]
    time_ms: int

def process_jedi(
    jedi_script: jedi.Script,
    line: int,
    column: int,
    repo_path: Path,
    exclude_path: Path,
    context_lines: int
) -> ProcessJediResult:
    start_time = time.time()
    references: list[jedi.api.classes.BaseName] = jedi_script.get_references(line, column)
    docs: list[Doc] = []
    for reference in references:
        reference_line = reference.line
        reference_column = reference.column
        reference_path = reference.module_path
        if not (reference_path is not None and 
                isinstance(reference_line, int) and
                reference_path.resolve() != exclude_path.resolve() and
                reference_path.resolve().is_relative_to(repo_path.resolve())
                ):
            continue
        content = get_file_lines(
            file_path=reference_path,
            line=reference_line,
            line_n=context_lines
        )
        start_line = max(0, reference_line-context_lines)
        end_line = start_line + len(content.splitlines())
        doc = Doc(
            content=content,
            path=reference_path,
            start_line=start_line,
            end_line=end_line
        )
        docs.append(doc)
    end_time = time.time()
    return {
        "docs": docs,
        "time_ms": round((end_time - start_time) * 1000)
    }


def find_usage(
    repo_path: Path,
    exclude_path: Path,
    infer_result: InferResult,
    context_lines: int,
    max_usage_n: int | None = None,
    enable_usage_analysis: bool = True,
    enable_usage_ast: bool = True,
    time_consuming: UsageTimeConsuming | None = None
) -> list[IdInfoUsages]:
    if time_consuming is None:
        time_consuming = UsageTimeConsuming()
    if enable_usage_analysis:
        jedi.cache.clear_time_caches(delete_all=True)
        jedi_project = jedi.Project(str(repo_path), smart_sys_path=True)
    result: list[IdInfoUsages] = []
    ids = infer_result.ids + infer_result.completions
    left_static_usage_time_ms = settings.retrieve.max_static_usage_time_ms
    for id_info in ids:
        location = id_info.definition.location
        use_text_find_usage = False
        usages_docs: list[Doc] = []
        if location is not None and location.start_position is not None and enable_usage_analysis:
            assert isinstance(jedi_project, jedi.Project)
            jedi_script = jedi.Script(
               path=location.path,
               project=jedi_project
            )
            line = location.start_position[0] + 1
            column = location.start_position[1]

            if left_static_usage_time_ms is None or (left_static_usage_time_ms is not None and left_static_usage_time_ms > 0):
                with contexttimer.Timer(factor=1000) as t:
                    ret = exception_handler_wrapper(
                        lambda: process_jedi(
                            jedi_script=jedi_script,
                            line=line,
                            column=column,
                            repo_path=repo_path,
                            exclude_path=exclude_path,
                            context_lines=context_lines
                        ),
                        timeout_limit=(
                            left_static_usage_time_ms / 1000
                            if left_static_usage_time_ms is not None
                            else DEFAULT_STATIC_USAGE_TIMEOUT_S
                        ),
                        default_value={"docs": [], "time_ms": -1},
                        multiprocessing=True
                    )
                    usages_docs = ret["docs"]
                # A successful sub-millisecond call can round to zero; only -1
                # marks a failed or timed-out analysis.
                if ret["time_ms"] >= 0:
                    elapsed_ms = ret["time_ms"]
                    if left_static_usage_time_ms is not None:
                        left_static_usage_time_ms -= ret["time_ms"]
                else:
                    elapsed_ms = (
                        left_static_usage_time_ms
                        if left_static_usage_time_ms is not None
                        else DEFAULT_STATIC_USAGE_TIMEOUT_S * 1000
                    )
                    if left_static_usage_time_ms is not None:
                        left_static_usage_time_ms = 0
                time_consuming.static_usage_ms += elapsed_ms
            if len(usages_docs) == 0:
                use_text_find_usage = True    
        else:
            use_text_find_usage = True
        if enable_usage_ast and use_text_find_usage:
            # find usages use text
            text_time_consuming = FindUsageTextTimeConsuming()
            usages = find_usages_text(
                repo_path=repo_path,
                target_name=id_info.id_name,
                context_lines=context_lines,
                max_usage_n=max_usage_n,
                time_consuming=text_time_consuming
            )
            usages_docs = [Doc(
                content=it.code_block,
                path=it.file_path,
                start_line=it.start_lineno,
                end_line=it.end_lineno
            ) for it in usages if it.file_path.resolve() != exclude_path.resolve() and
                        it.file_path.resolve().is_relative_to(repo_path.resolve())
            ]
            time_consuming.ast_usage_ms += text_time_consuming.search_ms
        
        usages_docs = merge_docs_by_reading_file(usages_docs)
        if max_usage_n is not None:
            usages_docs = usages_docs[:max_usage_n]
        result.append(IdInfoUsages(
            id_info=id_info,
            usages=usages_docs
        ))
    return result
