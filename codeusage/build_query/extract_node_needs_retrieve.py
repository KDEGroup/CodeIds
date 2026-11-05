from tree_sitter import Language, Parser, Node
import tree_sitter_python as tspython
from pydantic import BaseModel
from collections import defaultdict
from typing import List, Dict, Any
import re

PYTHON_LANGUAGE = Language(tspython.language())

parser = Parser(PYTHON_LANGUAGE)

class ResultNode(BaseModel):
    identifier_name: str
    start_position: tuple[int, int]
    end_position: tuple[int, int]
    last_with_dot: bool
    is_last: bool



def find_last_statement_identifiers(code_snippet: str) -> List[ResultNode]:
    code_bytes = code_snippet.encode("utf8")
    tree = parser.parse(code_bytes)
    tree.root_node_with_offset
    right_most_node = tree.root_node
    while right_most_node.child_count > 0:
        for node in reversed(right_most_node.children):
            if node.text != b'':
                right_most_node = node
                break
    
    identifier_nodes: list[Node] = []
    def extract_identifier_nodes(node: Node):
        cursor = node.walk()
        if not cursor.goto_first_child():
            if cursor.node.type == "identifier":
                identifier_nodes.append(cursor.node)
            return
        while True:
            if cursor.node.type == "identifier":
                identifier_nodes.append(cursor.node)
            if cursor.goto_first_child():
                continue
            if cursor.goto_next_sibling():
                continue
            
            while cursor.goto_parent():
                if cursor.goto_next_sibling():
                    break
            else:
                break
        
    def is_statement(node: Node) -> bool:
        if node.type.endswith("statement"):
            return True
        if node.type.endswith("clause"):
            return True
        if node.type in ("function_definition", "call"):
            return True
        if node.child_count > 0:
            return True
        
        return False
    p = right_most_node
    if p.type in (".", "("):
        p = p.prev_sibling
    elif p.type == ")":
        p = p.parent
        if p is not None:
            p = p.prev_named_sibling
    while p is not None:
        p1 = p
        found = False
        while p1.prev_sibling is not None:
            p1 = p1.prev_sibling
            if is_statement(p1):
                p2 = p1.next_sibling
                while p2 is not None:
                    extract_identifier_nodes(p2)
                    p2 = p2.next_sibling
                found = True
                break
        if found:
            break
                
        p = p.parent
            
    excluded_names = ("isinstance",)
    result =  [ResultNode(
        identifier_name=it.text.decode('utf-8'),
        start_position=it.start_point,
        end_position=it.end_point,
        last_with_dot=False,
        is_last=False
    ) for it in identifier_nodes]
    if len(identifier_nodes) > 0:
        last_id_node = identifier_nodes[-1]
        last_not_empty_byte = None
        for b in reversed(code_bytes):
            if b != ord(" "):
                last_not_empty_byte = b
                break
        last_with_dot = last_not_empty_byte == ord(".")
        is_last = len(code_bytes) == last_id_node.end_byte
        result[-1].last_with_dot = last_with_dot
        result[-1].is_last = is_last
        
    result = [it for it in result if not it.identifier_name in excluded_names]
    return result


