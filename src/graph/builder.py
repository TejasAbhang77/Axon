"""
Dependency Graph Builder using NetworkX.
========================================

This module takes the structured output from the AST parser and builds
a directed graph representing the codebase's architecture.

NODES:
  - Functions (e.g., "flask.app.Flask.run")
  - Classes (e.g., "flask.app.Flask")
  - Files (e.g., "src/flask/app.py")

EDGES:
  - CALLS (Function A → Function B)
  - CONTAINS (File → Class, Class → Method, File → Function)
  - INHERITS (Class A → Class B)
  - IMPORTS (File A → File B)

CHALLENGE: CROSS-FILE RESOLUTION
  When a file calls `jsonify()`, we need to know that `jsonify` is defined
  in `flask.json`. We use the extracted `ImportInfo` to resolve these names.
"""

import json
import os
from pathlib import Path
import networkx as nx
from typing import Dict, List, Any, Optional

class DependencyGraph:
    def __init__(self):
        self.graph = nx.DiGraph()
        # Maps name in a file to its fully qualified name
        # { file_path: { alias/name: fully_qualified_name } }
        self.resolution_map = {}

    def build_from_analysis(self, analyses: List[Dict[str, Any]]):
        """
        Build the graph from a list of FileAnalysis dictionaries.
        """
        # Step 1: Add all nodes (Files, Classes, Functions)
        for file_data in analyses:
            file_path = file_data['file_path']
            rel_path = self._get_repo_rel_path(file_path)
            
            # File node
            self.graph.add_node(rel_path, type='file', path=file_path)
            
            # Imports for resolution later
            self._process_imports(file_path, file_data['imports'])

            # Class nodes
            for cls in file_data.get('classes', []):
                cls_name = cls['name']
                fq_cls_name = f"{rel_path}:{cls_name}"
                self.graph.add_node(fq_cls_name, type='class', name=cls_name, file=rel_path)
                self.graph.add_edge(rel_path, fq_cls_name, relation='contains')
                
                # Methods
                for meth_name in cls.get('methods', []):
                    fq_meth_name = f"{fq_cls_name}.{meth_name}"
                    self.graph.add_node(fq_meth_name, type='function', name=meth_name, file=rel_path, class_name=cls_name)
                    self.graph.add_edge(fq_cls_name, fq_meth_name, relation='contains')

            # Standalone Function nodes
            # (Note: In Python, some functions are inside others or classes.
            # Tree-sitter found all of them. We need to be careful with nesting.)
            for func in file_data['functions']:
                # If it's not already added as a method
                func_name = func['name']
                fq_func_name = f"{rel_path}:{func_name}"
                
                # Check if this function belongs to a class (heuristic)
                # For now, let's just add it if not already there
                if fq_func_name not in self.graph:
                    self.graph.add_node(fq_func_name, type='function', name=func_name, file=rel_path)
                    self.graph.add_edge(rel_path, fq_func_name, relation='contains')

        # Step 2: Add Call Edges (This is the "Hybrid" part)
        for file_data in analyses:
            rel_path = self._get_repo_rel_path(file_data['file_path'])
            for func in file_data['functions']:
                caller_name = func['name']
                # Determine fully qualified caller name
                # (Simple heuristic for now, assuming unique names in file)
                caller_node = self._find_node_in_file(rel_path, caller_name)
                
                if not caller_node:
                    continue

                for callee_raw in func['calls']:
                    # Resolve where this call goes
                    callee_node = self._resolve_call(rel_path, callee_raw)
                    if callee_node:
                        self.graph.add_edge(caller_node, callee_node, relation='calls')

        # Step 3: Add Inheritance Edges (Improvement 3)
        for file_data in analyses:
            rel_path = self._get_repo_rel_path(file_data['file_path'])
            for cls in file_data.get('classes', []):
                fq_cls_name = f"{rel_path}:{cls['name']}"
                for base in cls.get('bases', []):
                    # Resolve where the base class comes from
                    base_node = self._resolve_call(rel_path, base)
                    if base_node:
                        # This class depends on the base class
                        self.graph.add_edge(fq_cls_name, base_node, relation='inherits')

    def _get_repo_rel_path(self, abs_path: str) -> str:
        # Simple heuristic: find the last 'src' or 'repos' and take everything after
        # In a real system, we'd pass the repo root.
        p = Path(abs_path)
        parts = p.parts
        if 'repos' in parts:
            idx = parts.index('repos')
            return "/".join(parts[idx+2:]) # repos/name/remainder
        return p.name

    def _process_imports(self, file_path: str, imports: List[Dict[str, Any]]):
        rel_path = self._get_repo_rel_path(file_path)
        self.resolution_map[rel_path] = {}
        for imp in imports:
            module = imp['module']
            for name in imp['names']:
                # Map name to its source module
                self.resolution_map[rel_path][name] = f"{module}.{name}"

    def _find_node_in_file(self, rel_path: str, name: str) -> Optional[str]:
        # Search for a function or class node in this file
        for node, data in self.graph.nodes(data=True):
            if data.get('file') == rel_path and data.get('name') == name:
                return node
        return None

    def _resolve_call(self, caller_file: str, callee_raw: str) -> Optional[str]:
        """
        Try to find the node for the called function.
        1. Local search (same file)
        2. External search (via imports)
        """
        # 1. Local search
        local_node = self._find_node_in_file(caller_file, callee_raw)
        if local_node:
            return local_node

        # 2. External search (using resolution_map)
        # This is hard because we don't have the full path of every library.
        # For now, we look for nodes in other files that match.
        for name, fq_name in self.resolution_map.get(caller_file, {}).items():
            if callee_raw == name or callee_raw.startswith(name + "."):
                # Try to find a node in ANY file that matches the suffix
                # (e.g., if we import flask.jsonify, look for jsonify() in any flask file)
                for node, data in self.graph.nodes(data=True):
                    if data.get('name') == name:
                        return node
        
        return None

    def save_graph(self, path: str):
        # Save as GraphML for viewing in Gephi or Cytoscape
        nx.write_graphml(self.graph, path)
        print(f"Graph saved to {path}")

    def get_impact_radius(self, node_name: str, depth: int = 5) -> List[str]:
        """
        Find all nodes affected by a change in node_name (multi-hop).
        Returns a list of nodes that depend on (call) this node.
        """
        if node_name not in self.graph:
            return []
        
        # Invert the graph to find "who calls me"
        inverted = self.graph.reverse()
        all_affected = []
        for d in range(1, depth + 1):
            all_affected.extend(nx.descendants_at_distance(inverted, node_name, distance=d))
        
        return list(set(all_affected))

    def get_dependencies(self, node_name: str, depth: int = 5) -> List[str]:
        """
        Find all nodes that node_name depends on (forward calls).
        Returns a list of nodes that this node calls.
        """
        if node_name not in self.graph:
            return []
        
        # successors are the nodes this one calls
        all_deps = []
        for d in range(1, depth + 1):
            all_deps.extend(nx.descendants_at_distance(self.graph, node_name, distance=d))
        
        return list(set(all_deps))

if __name__ == "__main__":
    import sys
    # Load the output if __name__ == "__main__":
    active_repo = os.getenv("ACTIVE_REPO", "default")
    results_path = os.path.join("results", f"{active_repo}_ast.json")
    if os.path.exists(results_path):
        with open(results_path, 'r') as f:
            data = json.load(f)
        
        builder = DependencyGraph()
        builder.build_from_analysis(data)
        
        print(f"Nodes: {builder.graph.number_of_nodes()}")
        print(f"Edges: {builder.graph.number_of_edges()}")
        
        # Configuration
        target_name = 'add_ctx'  # Try: 'decrypt', 'generate_gps_hash', 'extract_key_from_image'
        
        # Find target node
        target = None
        for node in builder.graph.nodes():
            if target_name in node:
                target = node
                break
        
        if target is not None:
            print(f"\n--- ANALYSIS FOR: {target} ---")
            
            # 1. IMPACT (Who depends on me?)
            impact = builder.get_impact_radius(target)
            print(f"\n[BACKWARD] Impact of changing this (Who calls me?):")
            if not impact:
                print("  (None found - this might be a top-level route or entry point)")
            for node in impact:
                # Filter out the file node if you only want functional impacts
                if builder.graph.nodes[node].get('type') != 'file':
                    print(f"  ← {node}")
            
            # 2. DEPENDENCIES (What do I use?)
            deps = builder.get_dependencies(target)
            print(f"\n[FORWARD] Dependencies (What does this function call?):")
            if not deps:
                print("  (None found - this might be a leaf function)")
            for node in deps:
                print(f"  → {node}")
        
        builder.save_graph("results/dependency_graph.graphml")
    else:
        print(f"Run the parser on a repo first to generate results/{active_repo}_ast.json")
