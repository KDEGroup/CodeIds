import ast
from pathlib import Path
from typing import List, Union

from pydantic import BaseModel

class Definition(BaseModel):
    """
    Represents a single definition found in a file.
    """
    path: Path
    content: str

def _format_function_from_node(node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> str:
    """
    Robustly formats a function AST node into a string signature by building it
    from its components, correctly handling type hints and defaults.
    """
    prefix = 'async def' if isinstance(node, ast.AsyncFunctionDef) else 'def'
    name = node.name
    
    # *** THIS IS THE FINAL FIX FOR PARENTHESES ***
    # We will manually add the parentheses to guarantee they exist,
    # regardless of how ast.unparse behaves.
    try:
        # Get the inner content of the arguments, e.g., "self, data_source"
        args_content = ast.unparse(node.args)
        # Manually wrap the content in parentheses.
        args_str = f"({args_content})"
    except Exception:
        # Fallback for any unexpected issue
        args_str = '(...)'

    returns_str = ''
    if node.returns:
        try:
            returns_str = f" -> {ast.unparse(node.returns)}"
        except Exception:
            returns_str = " -> ..."
    
    # Note the space between prefix and name is already handled.
    return f"{prefix} {name}{args_str}{returns_str}: ..."

def _parse_class_body_from_node(class_node: ast.ClassDef) -> str:
    """
    Parses a class AST node to extract members, clearly distinguishing between
    class attributes, instance attributes (from __init__), and methods.
    """
    class_attrs = []
    instance_attrs = []
    methods = []

    # First pass: find __init__ and extract instance attributes
    init_node = next((n for n in class_node.body if isinstance(n, ast.FunctionDef) and n.name == "__init__"), None)
    if init_node:
        for node in ast.walk(init_node):
            target_node = None
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target_node = node.targets[0]
            elif isinstance(node, ast.AnnAssign):
                target_node = node.target

            if isinstance(target_node, ast.Attribute) and isinstance(target_node.value, ast.Name) and target_node.value.id == 'self':
                instance_attrs.append(ast.unparse(node))
    
    # Second pass: find class attributes and all methods
    for node in class_node.body:
        is_class_attr = False
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            is_class_attr = True
        elif isinstance(node, ast.Assign) and node.targets and isinstance(node.targets[0], ast.Name):
            is_class_attr = True
        
        if is_class_attr:
            class_attrs.append(ast.unparse(node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(_format_function_from_node(node))

    # Assemble the final class body
    body_members = []
    if class_attrs:
        body_members.extend(class_attrs)
    if class_attrs and instance_attrs:
        body_members.append("")
    if instance_attrs:
        body_members.extend(instance_attrs)
    if (class_attrs or instance_attrs) and methods:
        body_members.append("")
    if methods:
        body_members.extend(methods)

    base_classes = [ast.unparse(base) for base in class_node.bases]
    class_header = f"class {class_node.name}({', '.join(base_classes)}):"
    
    if not body_members:
        return f"{class_header}\n    pass"
    else:
        final_body_lines = []
        for member_string in body_members:
            final_body_lines.extend(member_string.split('\n'))
        
        indented_body = "\n".join(f"    {line}" for line in final_body_lines)
        return f"{class_header}\n{indented_body}"

def extract_definitions_from_repo(repo_path: Path) -> list[Definition]:
    """
    Recursively finds all definitions in a Python repository using AST.
    """
    definitions: list[Definition] = []
    if not repo_path.is_dir():
        raise ValueError("Provided path is not a directory.")

    python_files = list(repo_path.rglob("*.py"))

    for file_path in python_files:
        try:
            source_code = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source_code, filename=str(file_path))

            for node in tree.body:
                content = ""
                if isinstance(node, ast.ClassDef):
                    content = _parse_class_body_from_node(node)
                
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    content = _format_function_from_node(node)
                    
                elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                    content = ast.unparse(node)
                
                elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                    call_node = node.value
                    if isinstance(call_node.func, ast.Name) and call_node.func.id == 'setup':
                        content = ast.unparse(node)

                if content:
                    definitions.append(Definition(path=file_path, content=content))

        except (SyntaxError, UnicodeDecodeError) as e:
            print(f"Skipping {file_path} due to parsing error: {e}")
            continue
            
    return definitions
