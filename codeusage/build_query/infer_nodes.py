import jedi.cache
from pydantic import BaseModel
from pathlib import Path
from .extract_node_needs_retrieve import ResultNode as IdentifierNode
from typing import Literal
import jedi
import jedi.api
from codeusage.utils import exception_handler_wrapper
from .completion_filter import CompletionFilter, MagicMethodFilter
from codeusage.utils.time_consuming import TimeComsuming
import contexttimer
from codeusage.utils.exceptions import TimeCost
from loguru import logger


default_time_limit_ms = 10000
        
        


class CodeSpan(BaseModel):
    path: Path
    start_position: tuple[int, int] | None
    end_position: tuple[int, int] | None

"""
someviriable: its'Type = expression

def somevariable()
"""
class RepoNormalType(BaseModel): # a type in the same repo
    name: str
    location: CodeSpan

class RepoModuleType(BaseModel):
    full_name: str
    location: Path

class NotResolvedType(BaseModel): # a type cannot resolved, which may from third party lib
    name: str

class BuiltinType(BaseModel):
    name: str

class ThirdPartyType(BaseModel):
    name: str

class StdType(BaseModel):
    name: str

class UnfinishedIdType(BaseModel): # e.g. someobj.call_some_fun_prefix_
    name: str

IdType = RepoNormalType | RepoModuleType | NotResolvedType | BuiltinType | StdType | ThirdPartyType


class IdDefinition(BaseModel): # how a identifier is defined. variable / class / function / others
    definition_stmt: str
    parent_name: str | None
    parent_type: Literal["module", "class"] | None
    is_in_init: bool
    location: CodeSpan | None

class IdInfo(BaseModel):
    id_name: str
    id_type: IdType
    definition: IdDefinition # a string represent the definition of this variable

    

class InferResult(BaseModel):
    ids: list[IdInfo]
    completions: list[IdInfo]

def infer_from_definition(
    id_name: str,
    repo_path: Path,
    definition: jedi.api.classes.BaseName,
    time_limit_ms: int | None = None
) -> tuple[IdInfo, int]:
    total_ms = 0
    if time_limit_ms is None:
        time_limit_ms = default_time_limit_ms
    is_in_init = False
    parent_scope_name: str | None = None
    parent_type = None
    time_cost = TimeCost()
    with contexttimer.Timer(factor=1000) as t:
        parent_name = exception_handler_wrapper(
            lambda: definition.parent(),
            timeout_limit=time_limit_ms / 1000,
            default_value=None,
            time_cost=time_cost
        ) 
    logger.debug(f"parent_name={t.elapsed}ms")
    time_limit_ms -= time_cost.cost_ms
    total_ms += time_cost.cost_ms

    if parent_name is not None:
        is_in_init = parent_name.name == "__init__"
        if is_in_init:
            time_cost = TimeCost()
            with contexttimer.Timer(factor=1000) as t:
                parent_p_name = exception_handler_wrapper(
                    lambda: parent_name.parent(),
                    timeout_limit=time_limit_ms / 1000,
                    default_value=None,
                    time_cost=time_cost
                ) 
            logger.debug(f"parent_p_name={t.elapsed}ms")
            time_limit_ms -= time_cost.cost_ms
            total_ms += time_cost.cost_ms

            if parent_p_name is not None and parent_p_name.type == "class":
                parent_scope_name = parent_p_name.name
        else:
            if parent_name.type == "class":
                parent_scope_name = parent_name.name
                parent_type = "class"
            elif parent_name.type == "module":
                full_name = parent_name.full_name
                assert isinstance(full_name, str)
                parent_scope_name = full_name
                parent_type = "module"

    
    def get_definition_stmt():
        with contexttimer.Timer(factor=1000) as t:
            signatures: list[jedi.api.classes.BaseSignature] = definition.get_signatures()
        logger.debug(f"signatures={t.elapsed}ms")
        stmt = definition.description
        if len(signatures) > 0:
            signature = signatures[0]
            if signature.type != "instance":
                stmt = signature.to_string()
        return stmt
    time_cost = TimeCost()
    with contexttimer.Timer(factor=1000) as t:
        definition_stmt = exception_handler_wrapper(
            lambda: get_definition_stmt(),
            timeout_limit=time_limit_ms / 1000,
            default_value=id_name,
            time_cost=time_cost
        )
    logger.debug(f"definition_stmt={t.elapsed}ms")
    time_limit_ms -= time_cost.cost_ms
    total_ms += time_cost.cost_ms
    location: CodeSpan | None = None
    if definition.module_path is not None:
        start_position = definition.get_definition_start_position()
        end_position = definition.get_definition_end_position()
        if start_position is not None:
            start_position = (start_position[0]-1, start_position[1])
        if end_position is not None:
            end_position = (end_position[0]-1, end_position[1])

        location = CodeSpan(
            path=definition.module_path,
            start_position=start_position,
            end_position=end_position
        )

    id_definition = IdDefinition(
        definition_stmt=definition_stmt,
        parent_name=parent_scope_name,
        parent_type=parent_type,
        is_in_init=is_in_init,
        location=location
    )
    id_type: IdType | None = None
    def base_name_infer() -> list:
        infer_ret = definition.infer()
        if not isinstance(infer_ret, list):
            infer_ret = [infer_ret]
        return infer_ret
    time_cost = TimeCost()
    with contexttimer.Timer(factor=1000) as t:
        infered_types: list[jedi.api.classes.Name] = exception_handler_wrapper(
            lambda: base_name_infer(),
            timeout_limit=time_limit_ms / 1000,
            default_value=[],
            time_cost=time_cost
        )
    logger.debug(f"infered_types={t.elapsed}ms")
    time_limit_ms -= time_cost.cost_ms
    total_ms += time_cost.cost_ms
    if len(infered_types) == 0:
        id_type = NotResolvedType(
            name=id_name
        )
        return IdInfo(
            id_name=id_name,
            id_type=id_type,
            definition=id_definition
        ), total_ms
    infered_type = infered_types[0]
    if infered_type.in_builtin_module():
        id_type = BuiltinType(name=infered_type.name)
    else:
        module_path = infered_type.module_path
        type_name = infered_type.name
        assert isinstance(type_name, str)
        if module_path is not None and module_path.resolve().is_relative_to(repo_path.resolve()):
            if infered_type.type == "module":
                type_full_name = infered_type.full_name
                assert isinstance(type_full_name, str)
                id_type = RepoModuleType(
                    full_name=type_full_name,
                    location=module_path
                )
            else:
                start_position = infered_type.get_definition_start_position()
                end_position = infered_type.get_definition_end_position()
                if start_position is not None:
                    start_line, start_column = start_position
                    assert isinstance(start_line, int)
                    assert isinstance(start_column, int)
                    start_position = (start_line - 1, start_column)
                if end_position is not None:
                    end_line, end_column = end_position
                    assert isinstance(end_line, int)
                    assert isinstance(end_column, int)
                    end_position = (end_line - 1, end_column)
                    
                id_type = RepoNormalType(
                    name=type_name,
                    location=CodeSpan(
                        path=module_path,
                        start_position=start_position,
                        end_position=end_position,
                    )
                )
        else:
            if module_path is None:
                id_type = ThirdPartyType(name=type_name)
            else:
                id_type = StdType(name=type_name)
    assert id_type is not None
    return IdInfo(
        id_name=id_name,
        id_type=id_type,
        definition=id_definition
    ), total_ms
    

def infer_a_completion(
    repo_path: Path,
    jedi_script: jedi.Script,
    completion: jedi.api.classes.Completion,
    time_limit_ms: int | None = None
) -> tuple[IdInfo, int]:
    total_ms = 0
    if time_limit_ms is None:
        time_limit_ms = default_time_limit_ms
    id_name = completion.name
    assert isinstance(id_name, str)
    time_cost = TimeCost()
    definitions: list[jedi.api.classes.Name | jedi.api.classes.Completion] = exception_handler_wrapper(
        lambda: completion.goto(follow_imports=True),
        timeout_limit=time_limit_ms / 1000,
        default_value=[],
        time_cost=time_cost
    )
    time_limit_ms -= time_cost.cost_ms
    total_ms += time_cost.cost_ms
    if len(definitions) == 0:
        return IdInfo(
            id_name=completion.name,
            id_type=NotResolvedType(
                name=id_name
            ),
            definition=IdDefinition(
                definition_stmt=id_name,
                parent_name=None,
                parent_type=None,
                is_in_init=False,
                location=None
            )
        ), total_ms
    assert len(definitions) > 0
    definition = definitions[0]
    assert isinstance(definition, jedi.api.classes.BaseName)
    return infer_from_definition(
        id_name=id_name,
        repo_path=repo_path,
        definition=definition,
        time_limit_ms=time_limit_ms
    )


def infer_a_node(
    repo_path: Path,
    file_path: Path,
    code: str,
    identifier: IdentifierNode,
    jedi_script: jedi.Script,
    time_limit_ms: int | None = None
) -> tuple[IdInfo, int]:
    total_ms = 0
    if time_limit_ms is None:
        time_limit_ms = default_time_limit_ms
    line = identifier.end_position[0] + 1
    column = identifier.end_position[1]
    time_cost = TimeCost()
    with contexttimer.Timer(factor=1000) as t:
        definitions: list[jedi.api.classes.Name] = exception_handler_wrapper(
            lambda: jedi_script.goto(line, column, follow_imports=True),
            timeout_limit=time_limit_ms / 1000,
            default_value=[],
            time_cost = time_cost
        )
    logger.debug(f"definitions take {t.elapsed}ms")
    total_ms += time_cost.cost_ms
    time_limit_ms -= time_cost.cost_ms
    id_name = identifier.identifier_name
    if len(definitions) == 0:
        id_type = NotResolvedType(name=identifier.identifier_name)
        id_definition = IdDefinition(
            definition_stmt=f"{id_name}: Unknown",
            parent_name=None,
            parent_type=None,
            is_in_init=False,
            location=None
            )
        return IdInfo(
            id_name=id_name,
            id_type=id_type,
            definition=id_definition
        ), total_ms
    definition = definitions[0]
    with contexttimer.Timer(factor=1000) as t:
        infer_from_definition_ret, infer_from_definition_cost_ms = infer_from_definition(
            id_name=id_name,
            repo_path=repo_path,
            definition=definition,
            time_limit_ms=time_limit_ms
        )
    logger.debug(f"infer from definitions take {t.elapsed}ms")
    return infer_from_definition_ret, infer_from_definition_cost_ms + total_ms

import ast

def get_all_imports_in_project(repo_path: Path):
    """Scan project and find all imported modules"""
    imports = set()
    
    for py_file in repo_path.rglob('*.py'):
        try:
            with open(py_file) as f:
                tree = ast.parse(f.read())
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split('.')[0])
        except:
            pass
    
    return imports

def preload_project_modules(repo_path: Path, jedi_project):
    """Preload all modules used in project"""
    imports = get_all_imports_in_project(repo_path)
    imports.add("adecty_design")
    imports.add("adecty_design.elements")
    imports.add("adecty_design.elements.config")
    imports.add("adecty_design.elements.header_navigation_item")
    imports.add("adecty_design.markups")
    imports.add("adecty_design.markups.markups")
    imports.add("builtins")
    
    for module_name in sorted(imports):
        try:
            jedi.preload_module(module_name)
            logger.debug(f"jedi preloads {module_name}")
        except:
            logger.warning(f"jedi cannot preload {module_name}")
            pass  # Third-party or missing modules
    

def delete_jedi_cache():
    # Create a Script (not get completions)
    """Create a fresh Script with warm caches"""
    script = jedi.Script("import sys\nimport os")
    # Warm up by doing simple analysis
    script.complete(1, 0)

    # Access inference_state from the Script object directly
    inference_state = script._inference_state
    inference_state.memoize_cache.clear()           # Method memoization
    inference_state.module_cache._name_cache.clear() # Imported modules
    inference_state.stub_module_cache.clear()        # Stub files
    inference_state.compiled_cache.clear()           # Compiled modules
    inference_state.mixed_cache.clear()              # Mixed objects
    inference_state.inferred_element_counts.clear()  # Element counts
    inference_state.access_cache.clear()             # Attribute access cache  

    from parso.cache import parser_cache
    parser_cache.clear()

    import gc
    n = gc.collect()
    logger.debug(f"gc collects {n} object")
    # Warm up BEFORE analyzing any files


def infer_nodes(
    repo_path: Path,
    file_path: Path,
    code: str,
    ids: list[IdentifierNode],
    completion_filter: CompletionFilter | None = None,
    time_consuming: TimeComsuming | None = None,
    time_limit_ms: int | None = None
) -> InferResult:
    if time_limit_ms is None:
        time_limit_ms = default_time_limit_ms
    if time_consuming is None:
        time_consuming = TimeComsuming()

    time_consuming.infer_types_ms = 0
    jedi.cache.clear_time_caches(delete_all=True)
    delete_jedi_cache()
    with contexttimer.Timer(factor=1000) as t:
        jedi_project = jedi.Project(str(repo_path), smart_sys_path=True)
    logger.debug(f"project init={t.elapsed}ms")

    with contexttimer.Timer(factor=1000) as t:
        preload_project_modules(repo_path=repo_path, jedi_project=jedi_project)
    logger.debug(f"jedi preload={t.elapsed}ms")

    with contexttimer.Timer(factor=1000) as t:
        jedi_script = jedi.Script(code=code, path=str(file_path), project=jedi_project)
    logger.debug(f"jedi_script first init = {t.elapsed}ms")
    result = InferResult(
        ids=[],
        completions=[]
    )
    # for each identifier, analysis its definition, and then infer it's type
    for identifier in ids:
        with contexttimer.Timer(factor=1000) as t:
            infer_ret, time_ms = infer_a_node(
                    repo_path=repo_path,
                    file_path=file_path,
                    code=code,
                    identifier=identifier,
                    jedi_script=jedi_script,
                    time_limit_ms=time_limit_ms
                )
        logger.debug(f"infer a node = {t.elapsed}ms")
        result.ids.append(infer_ret)
        time_consuming.infer_types_ms += time_ms
        time_limit_ms -= time_ms
    if len(result.ids) == 0:
        return result
    # for last identifier, try to complete
    last_id_idx = -1
    last_identifier_node: IdentifierNode | None = None
    for idx, identifier in enumerate(ids):
        if identifier.is_last or identifier.last_with_dot:
            last_identifier_node = identifier
            last_id_idx = idx
    if last_identifier_node is None:
        return result
    last_id = result.ids[last_id_idx]
    line = last_identifier_node.end_position[0] + 1
    column = last_identifier_node.end_position[1]
    if completion_filter is None:
        completion_filter = MagicMethodFilter()

    code_to_complete = code
    completions = []
    add_dot = False
    good_completions = []
    if last_identifier_node.last_with_dot:
        code_lines = code.splitlines()
        complete_line = len(code_lines)
        complete_column = len(code_lines[-1])
        time_cost = TimeCost()
        with contexttimer.Timer(factor=1000) as t:
            completions: list[jedi.api.classes.Completion] = exception_handler_wrapper(
                lambda: jedi_script.complete(complete_line, complete_column),
                timeout_limit=time_limit_ms / 1000,
                default_value=[],
                multiprocessing=False,
                time_cost=time_cost
            ) 
        logger.debug(f"completion={t.elapsed}ms")
        time_consuming.infer_types_ms += time_cost.cost_ms
        time_limit_ms -= time_cost.cost_ms
    else:
        time_cost = TimeCost()
        with contexttimer.Timer(factor=1000) as t:
            good_completions: list[jedi.api.classes.Completion] = exception_handler_wrapper(
                lambda: jedi_script.complete(line, column),
                timeout_limit=time_limit_ms / 1000,
                default_value=[],
                multiprocessing=False,
                time_cost=time_cost
            ) 
        logger.debug(f"good completion={t.elapsed}ms")
        time_consuming.infer_types_ms += time_cost.cost_ms
        time_limit_ms -= time_cost.cost_ms
        good_completions = [it for it in good_completions if it.name != last_identifier_node.identifier_name]

        code_to_complete = code + "."
        add_dot = True
        add_dot_script = jedi.Script(code_to_complete, path=str(file_path), project=jedi_project)
        time_cost = TimeCost()
        with contexttimer.Timer(factor=1000) as t:
            completions: list[jedi.api.classes.Completion] = exception_handler_wrapper(
                lambda: add_dot_script.complete(line, column + 1),
                timeout_limit=time_limit_ms / 1000,
                default_value=[],
                multiprocessing=False,
                time_cost=time_cost
            ) 
        logger.debug(f"add dot completion={t.elapsed}ms")
        time_consuming.infer_types_ms += time_cost.cost_ms
        time_limit_ms -= time_cost.cost_ms
        if isinstance(result.ids[last_id_idx].id_type, UnfinishedIdType):
            result.ids.pop(last_id_idx)
            
    completion_names: list[str] = []
    for completion in completions:
        completion_name = completion.name
        assert isinstance(completion_name, str)
        completion_names.append(completion_name)
    completion_code = code
    if add_dot:
        completion_code = completion_code + "."
    with contexttimer.Timer(factor=1000) as t:
        valids = completion_filter.filter_name(code=completion_code, completions=completion_names)
    time_consuming.ppl_ms = round(t.elapsed)
    completions = [completion for completion, valid in zip(completions, valids, strict=True) if valid]

    completions = completions + good_completions
    for completion in completions:
        with contexttimer.Timer(factor=1000) as t:
            infer_a_completion_ret, cost_ms = infer_a_completion(
                repo_path=repo_path,
                jedi_script=jedi_script,
                completion=completion,
                time_limit_ms=time_limit_ms
            )
        logger.debug(f"infer a completion={t.elapsed}ms")
        result.completions.append(infer_a_completion_ret)
        time_limit_ms -= cost_ms
        time_consuming.infer_types_ms += cost_ms
    return result