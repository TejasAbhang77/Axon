"""
AST Visualizer Tool.
====================
Prints a readable tree structure of a Python file's AST using tree-sitter.
"""

import sys
import os
from tree_sitter import Language, Parser
import tree_sitter_python as tspython

def print_node(node, level=0, max_depth=2, source_code=None):
    """Recursively prints the AST node with indentation and a depth limit."""
    if level > max_depth:
        return

    indent = "  " * level
    
    # Get the text content for identifiers and certain small nodes
    text = ""
    if node.type in ["identifier", "string", "integer", "attribute", "comparison_operator"]:
        if source_code:
            text = f" -> '{source_code[node.start_byte:node.end_byte].decode('utf-8')}'"
    
    print(f"{indent}type: {node.type}{text} [{node.start_point[0]}:{node.start_point[1]}]")
    
    for child in node.children:
        print_node(child, level + 1, max_depth, source_code)

def visualize_file(file_path, max_depth=2):
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return

    # Setup parser
    PY_LANGUAGE = Language(tspython.language())
    parser = Parser(PY_LANGUAGE)

    with open(file_path, "rb") as f:
        source_code = f.read()

    tree = parser.parse(source_code)
    
    print(f"\n--- AST STRUCTURE (Depth {max_depth}) FOR: {file_path} ---")
    print_node(tree.root_node, 0, max_depth, source_code)
    print("-" * (30 + len(file_path)))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/ast_parser/visualize_ast.py <file_path> [max_depth]")
        # Default to a small example
        example = "data/repos/geoencrypt-pro/backend.py"
        if os.path.exists(example):
            print(f"No file provided. Visualizing default example: {example} (Depth 2)\n")
            visualize_file(example, max_depth=2)
    else:
        depth = 2
        if len(sys.argv) > 2:
            try:
                depth = int(sys.argv[2])
            except ValueError:
                pass
        visualize_file(sys.argv[1], max_depth=depth)
