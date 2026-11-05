from tree_sitter import Language, Parser
import tree_sitter_python as tspython
def extract_tokens_with_tree_sitter(code: str) -> list[str]:
    PYTHON_LANGUAGE = Language(tspython.language())
    parser = Parser(PYTHON_LANGUAGE)
    tree = parser.parse(code.encode())
    root = tree.root_node
    tokens = []

    def traverse(node):
        if node.child_count == 0:
            token = code[node.start_byte:node.end_byte]
            if token.strip():
                tokens.append(token)
        else:
            for child in node.children:
                traverse(child)

    traverse(root)
    return tokens