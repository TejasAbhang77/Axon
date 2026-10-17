"""
AST Parser for Python source files using tree-sitter.
=====================================================

This module extracts structural information from Python files:
  - Function definitions (name, file, line number, body)
  - Import statements (module name, imported names)
  - Function calls inside each function (caller → callee relationships)

WHY TREE-SITTER?
  tree-sitter is a fast, incremental parser that builds concrete syntax trees.
  Unlike Python's built-in `ast` module, tree-sitter:
    1. Works on ANY language (we might add JS/TS later)
    2. Handles broken/incomplete code gracefully
    3. Is used by GitHub, Neovim, and many production tools

HOW IT WORKS:
  1. We load the Python grammar for tree-sitter
  2. Parse a .py file into a syntax tree
  3. Walk the tree looking for specific node types:
     - "function_definition" → extract function name, line, body
     - "import_statement" / "import_from_statement" → extract imports
     - "call" nodes inside functions → extract which functions are called

OUTPUT FORMAT:
  {
    "file": "path/to/file.py",
    "functions": [
      {"name": "my_func", "line": 10, "end_line": 25, "calls": ["other_func", "helper"]}
    ],
    "imports": [
      {"module": "os", "names": ["path", "getcwd"]},
      {"module": "flask", "names": ["Flask", "request"]}
    ]
  }

YOUR TASKS (things for you to try after reading this):
  ──────────────────────────────────────────────────────
  1. Run this script on a single Flask source file and inspect the output
  2. Try to understand what each tree-sitter node type looks like
     (uncomment the debug_print_tree() call at the bottom)
  3. CHALLENGE: Add support for extracting class definitions and methods
     Hint: Look for node type "class_definition" in the tree
  4. CHALLENGE: Handle decorated functions (e.g., @app.route)
     Hint: The decorator is a sibling node, not a child of function_definition
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

import tree_sitter_python as tspython
from tree_sitter import Language, Parser


# ============================================================================
# DATA CLASSES — These define the structure of our extracted information
# ============================================================================

@dataclass
class FunctionInfo:
    """Represents a function found in the source code."""
    name: str                          # Function name (e.g., "parse_request")
    file_path: str                     # Which file it's in
    line: int                          # Starting line number (1-indexed)
    end_line: int                      # Ending line number
    calls: list[str] = field(default_factory=list)  # Functions this one calls
    decorators: list[str] = field(default_factory=list)  # Any decorators


@dataclass
class ClassInfo:
    """Represents a class definition found in the source code."""
    name: str                          # Class name (e.g., "Flask")
    file_path: str                     # Which file it's in
    line: int                          # Starting line number
    end_line: int                      # Ending line number
    methods: list[str] = field(default_factory=list)  # Names of methods defined in class
    bases: list[str] = field(default_factory=list)    # Base classes (inheritance)
    decorators: list[str] = field(default_factory=list)


@dataclass
class ImportInfo:
    """Represents an import statement."""
    module: str                        # Module being imported (e.g., "flask")
    names: list[str] = field(default_factory=list)  # Specific names imported
    is_from_import: bool = False       # True if "from X import Y" style
    alias: Optional[str] = None        # Alias if "import X as Y"


@dataclass
class FileAnalysis:
    """Complete analysis of a single Python file."""
    file_path: str
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    imports: list[ImportInfo] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)  # Any parsing errors


# ============================================================================
# PARSER CLASS — The main tree-sitter based parser
# ============================================================================

class PythonASTParser:
    """
    Parses Python source files using tree-sitter and extracts:
      - Function definitions
      - Import statements
      - Function call relationships (caller → callee)

    Usage:
        parser = PythonASTParser()
        analysis = parser.parse_file("path/to/file.py")
        print(analysis.functions)
        print(analysis.imports)
    """

    def __init__(self):
        # Load tree-sitter Python grammar
        # tree-sitter needs a "Language" object that knows Python syntax
        self.PY_LANGUAGE = Language(tspython.language())
        self.parser = Parser(self.PY_LANGUAGE)

    def parse_file(self, file_path: str) -> FileAnalysis:
        """
        Parse a single Python file and extract all structural information.

        Args:
            file_path: Path to the .py file to parse

        Returns:
            FileAnalysis object with functions, imports, and any errors
        """
        file_path = str(Path(file_path).resolve())
        analysis = FileAnalysis(file_path=file_path)

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                source_code = f.read()
        except (FileNotFoundError, PermissionError) as e:
            analysis.errors.append(f"Could not read file: {e}")
            return analysis

        # Parse the source code into a tree-sitter syntax tree
        # This tree is a concrete syntax tree (CST), not an abstract one (AST)
        # It includes ALL tokens including whitespace, comments, etc.
        tree = self.parser.parse(bytes(source_code, "utf-8"))
        root_node = tree.root_node

        # Check for syntax errors in the file
        if root_node.has_error:
            analysis.errors.append("File contains syntax errors (parsed partially)")

        # Walk the tree and extract what we need
        self._extract_imports(root_node, analysis)
        self._extract_classes(root_node, analysis, file_path)
        self._extract_functions(root_node, analysis, file_path)

        return analysis

    def _extract_imports(self, root_node, analysis: FileAnalysis):
        """
        Extract all import statements from the syntax tree.

        Handles two forms:
          - import os           → ImportInfo(module="os", names=["os"])
          - from flask import X → ImportInfo(module="flask", names=["X"], is_from_import=True)
        """
        for node in self._walk_tree(root_node):
            if node.type == "import_statement":
                # "import os" or "import os, sys" or "import os as operating_system"
                for child in node.children:
                    if child.type == "dotted_name":
                        module_name = child.text.decode("utf-8")
                        analysis.imports.append(ImportInfo(
                            module=module_name,
                            names=[module_name.split(".")[-1]],
                            is_from_import=False
                        ))
                    elif child.type == "aliased_import":
                        # "import os as operating_system"
                        dotted = child.child_by_field_name("name")
                        alias_node = child.child_by_field_name("alias")
                        if dotted:
                            module_name = dotted.text.decode("utf-8")
                            alias = alias_node.text.decode("utf-8") if alias_node else None
                            analysis.imports.append(ImportInfo(
                                module=module_name,
                                names=[module_name.split(".")[-1]],
                                is_from_import=False,
                                alias=alias
                            ))

            elif node.type == "import_from_statement":
                # "from flask import Flask, request"
                module_node = node.child_by_field_name("module_name")
                module_name = module_node.text.decode("utf-8") if module_node else "unknown"

                imported_names = []
                for child in node.children:
                    if child.type == "dotted_name" and child != module_node:
                        imported_names.append(child.text.decode("utf-8"))
                    elif child.type == "aliased_import":
                        name_node = child.child_by_field_name("name")
                        if name_node:
                            imported_names.append(name_node.text.decode("utf-8"))

                # Handle wildcard imports: "from module import *"
                if not imported_names:
                    for child in node.children:
                        if child.type == "wildcard_import":
                            imported_names.append("*")

                analysis.imports.append(ImportInfo(
                    module=module_name,
                    names=imported_names,
                    is_from_import=True
                ))

    def _extract_functions(self, root_node, analysis: FileAnalysis, file_path: str):
        """
        Extract all function definitions and the calls they make.

        For each function, we:
          1. Record its name, line numbers
          2. Walk its body to find all "call" nodes
          3. Extract the function name being called

        NOTE: This only captures STATIC calls (things written in the code).
        Dynamic calls via variables (e.g., `func = get_handler(); func()`)
        are NOT captured. We acknowledge this as a limitation in the paper.
        """
        for node in self._walk_tree(root_node):
            if node.type == "function_definition":
                name_node = node.child_by_field_name("name")
                if not name_node:
                    continue

                func_name = name_node.text.decode("utf-8")

                # Extract decorator names (e.g., @app.route, @staticmethod)
                decorators = []
                # Check for a decorated_definition parent
                parent = node.parent
                if parent and parent.type == "decorated_definition":
                    for child in parent.children:
                        if child.type == "decorator":
                            dec_text = child.text.decode("utf-8").lstrip("@")
                            # Remove arguments from decorator: @app.route("/") → app.route
                            if "(" in dec_text:
                                dec_text = dec_text[:dec_text.index("(")]
                            decorators.append(dec_text)

                # Find all function calls INSIDE this function's body
                calls = self._extract_calls_from_node(node)

                func_info = FunctionInfo(
                    name=func_name,
                    file_path=file_path,
                    line=node.start_point[0] + 1,       # tree-sitter is 0-indexed
                    end_line=node.end_point[0] + 1,
                    calls=calls,
                    decorators=decorators
                )
                analysis.functions.append(func_info)

    def _extract_classes(self, root_node, analysis: FileAnalysis, file_path: str):
        """
        Extract all class definitions, their base classes, and methods.
        """
        for node in self._walk_tree(root_node):
            if node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                if not name_node:
                    continue

                class_name = name_node.text.decode("utf-8")

                # Extract base classes (inheritance)
                bases = []
                superclasses_node = node.child_by_field_name("superclasses")
                if superclasses_node:
                    for arg in superclasses_node.children:
                        if arg.type in ["identifier", "attribute"]:
                            bases.append(arg.text.decode("utf-8"))

                # Extract decorators
                decorators = []
                parent = node.parent
                if parent and parent.type == "decorated_definition":
                    for child in parent.children:
                        if child.type == "decorator":
                            dec_text = child.text.decode("utf-8").lstrip("@")
                            if "(" in dec_text:
                                dec_text = dec_text[:dec_text.index("(")]
                            decorators.append(dec_text)

                # Find methods (functions defined inside this class block)
                methods = []
                body_node = node.child_by_field_name("body")
                if body_node:
                    for child in body_node.children:
                        # Direct children might be decorated_definition or function_definition
                        target = child
                        if child.type == "decorated_definition":
                            for grandchild in child.children:
                                if grandchild.type == "function_definition":
                                    target = grandchild
                                    break
                        
                        if target.type == "function_definition":
                            meth_name_node = target.child_by_field_name("name")
                            if meth_name_node:
                                methods.append(meth_name_node.text.decode("utf-8"))

                class_info = ClassInfo(
                    name=class_name,
                    file_path=file_path,
                    line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    methods=methods,
                    bases=bases,
                    decorators=decorators
                )
                analysis.classes.append(class_info)

    def _extract_calls_from_node(self, node) -> list[str]:
        """
        Recursively find all function calls within a node.

        This handles:
          - Simple calls: my_func()
          - Method calls: self.my_method()    → extracts "my_method"
          - Chained calls: obj.method()       → extracts "obj.method"
          - Nested calls: outer(inner())      → extracts both

        Returns a deduplicated list of called function names.
        """
        calls = []
        for child in self._walk_tree(node):
            if child.type == "call":
                func_node = child.child_by_field_name("function")
                if func_node:
                    call_name = self._get_call_name(func_node)
                    if call_name:
                        calls.append(call_name)

        # Deduplicate while preserving order
        seen = set()
        unique_calls = []
        for c in calls:
            if c not in seen:
                seen.add(c)
                unique_calls.append(c)
        return unique_calls

    def _get_call_name(self, func_node) -> Optional[str]:
        """
        Extract the name from a function call node.

        Examples:
          my_func()           → "my_func"
          self.method()       → "method"        (strips "self.")
          module.func()       → "module.func"
          obj.method.chain()  → "obj.method.chain"
        """
        if func_node.type == "identifier":
            return func_node.text.decode("utf-8")
        elif func_node.type == "attribute":
            full_text = func_node.text.decode("utf-8")
            # Strip "self." prefix — we want the method name
            if full_text.startswith("self."):
                return full_text[5:]  # Remove "self."
            return full_text
        return None

    def _walk_tree(self, node):
        """
        Generator that yields all nodes in a tree (depth-first traversal).

        This is a utility to make it easy to iterate over all nodes:
            for node in self._walk_tree(root):
                if node.type == "function_definition":
                    ...
        """
        yield node
        for child in node.children:
            yield from self._walk_tree(child)


# ============================================================================
# REPO PARSER — Walks an entire repository directory
# ============================================================================

class RepoParser:
    """
    Parses all Python files in a repository directory.

    Usage:
        repo_parser = RepoParser()
        results = repo_parser.parse_repo("path/to/flask")
        for analysis in results:
            print(f"{analysis.file_path}: {len(analysis.functions)} functions")
    """

    def __init__(self):
        self.parser = PythonASTParser()

    def parse_repo(self, repo_path: str, exclude_dirs: list[str] = None) -> list[FileAnalysis]:
        """
        Parse all .py files in a directory tree.

        Args:
            repo_path: Root directory of the repository
            exclude_dirs: Directory names to skip (default: tests, venv, __pycache__, .git, node_modules)

        Returns:
            List of FileAnalysis objects, one per file
        """
        if exclude_dirs is None:
            exclude_dirs = ["tests", "test", "venv", ".venv", "__pycache__",
                            ".git", "node_modules", ".tox", "docs", "examples"]

        repo_path = Path(repo_path).resolve()
        results = []

        # Find all Python files
        py_files = []
        for root, dirs, files in os.walk(repo_path):
            # Skip excluded directories (modifying dirs in-place skips them)
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for f in files:
                if f.endswith(".py"):
                    py_files.append(os.path.join(root, f))

        print(f"Found {len(py_files)} Python files in {repo_path}")

        # Parse each file
        for file_path in py_files:
            analysis = self.parser.parse_file(file_path)
            results.append(analysis)

        return results


# ============================================================================
# UTILITY — Debug helper to visualize the tree-sitter syntax tree
# ============================================================================

def debug_print_tree(node, indent=0, max_depth=5):
    """
    Print the tree-sitter syntax tree structure (useful for learning).

    Try this on a small Python file to understand what nodes tree-sitter creates:
        parser = PythonASTParser()
        tree = parser.parser.parse(b"def hello(): return 42")
        debug_print_tree(tree.root_node)

    This will show you things like:
        module [0:0 - 0:22]
          function_definition [0:0 - 0:22]
            name: identifier [0:4 - 0:9] "hello"
            parameters: parameters [0:9 - 0:11]
            body: block [0:13 - 0:22]
              return_statement [0:13 - 0:22]
                expression_list [0:20 - 0:22]
                  integer [0:20 - 0:22] "42"
    """
    if indent > max_depth:
        return

    # Build the display string
    text_preview = ""
    if node.child_count == 0:  # Leaf node — show its text
        text_preview = f' "{node.text.decode("utf-8")}"'

    field_name = ""
    if node.parent:
        for i, child in enumerate(node.parent.children):
            if child == node:
                fname = node.parent.field_name_for_child(i)
                if fname:
                    field_name = f"{fname}: "
                break

    print(f"{'  ' * indent}{field_name}{node.type} "
          f"[{node.start_point[0]}:{node.start_point[1]} - "
          f"{node.end_point[0]}:{node.end_point[1]}]{text_preview}")

    for child in node.children:
        debug_print_tree(child, indent + 1, max_depth)


# ============================================================================
# MAIN — Run this to test the parser
# ============================================================================

if __name__ == "__main__":
    import sys
    from rich.console import Console
    from rich.table import Table
    from rich import print as rprint

    console = Console()

    # ----- SINGLE FILE MODE -----
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        # Default: parse this file itself as a demo!
        target = __file__

    if os.path.isfile(target):
        console.print(f"\n[bold cyan]Parsing single file:[/] {target}\n")
        parser = PythonASTParser()
        result = parser.parse_file(target)

        # Show functions
        if result.functions:
            table = Table(title="Functions Found", show_lines=True)
            table.add_column("Function", style="green")
            table.add_column("Lines", style="yellow")
            table.add_column("Calls", style="cyan")
            table.add_column("Decorators", style="magenta")

            for func in result.functions:
                table.add_row(
                    func.name,
                    f"{func.line}-{func.end_line}",
                    ", ".join(func.calls) if func.calls else "—",
                    ", ".join(func.decorators) if func.decorators else "—"
                )
            console.print(table)

        # Show classes
        if result.classes:
            table = Table(title="Classes Found", show_lines=True)
            table.add_column("Class", style="green")
            table.add_column("Bases", style="yellow")
            table.add_column("Methods", style="cyan")

            for cls in result.classes:
                table.add_row(
                    cls.name,
                    ", ".join(cls.bases) if cls.bases else "—",
                    ", ".join(cls.methods) if cls.methods else "—"
                )
            console.print(table)

        # Show imports
        if result.imports:
            table = Table(title="Imports Found", show_lines=True)
            table.add_column("Module", style="green")
            table.add_column("Names", style="cyan")
            table.add_column("Type", style="yellow")

            for imp in result.imports:
                table.add_row(
                    imp.module,
                    ", ".join(imp.names) if imp.names else "—",
                    "from...import" if imp.is_from_import else "import"
                )
            console.print(table)

        if result.errors:
            for err in result.errors:
                console.print(f"[red]⚠ {err}[/]")

    # ----- REPO MODE -----
    elif os.path.isdir(target):
        console.print(f"\n[bold cyan]Parsing repository:[/] {target}\n")
        repo_parser = RepoParser()
        results = repo_parser.parse_repo(target)

        total_functions = sum(len(r.functions) for r in results)
        total_imports = sum(len(r.imports) for r in results)
        total_calls = sum(len(f.calls) for r in results for f in r.functions)
        files_with_errors = sum(1 for r in results if r.errors)

        console.print(f"[bold]Summary:[/]")
        console.print(f"  Files parsed:    {len(results)}")
        console.print(f"  Functions found: {total_functions}")
        console.print(f"  Imports found:   {total_imports}")
        console.print(f"  Call edges:      {total_calls}")
        console.print(f"  Files w/ errors: {files_with_errors}")

        # Save full results to JSON
        active_repo = os.getenv("ACTIVE_REPO", "default")
        output_path = os.path.join(os.path.dirname(__file__), "..", "..", "results", f"{active_repo}_ast.json")
        output_path = os.path.normpath(output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        output_data = [asdict(r) for r in results]
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)
        console.print(f"\n[green]Full results saved to:[/] {output_path}")

    else:
        console.print(f"[red]Error: '{target}' is not a valid file or directory[/]")
        console.print("Usage: python parser.py <file.py | repo_directory>")
