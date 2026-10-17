import os
import sys
import json
import argparse
import re
import difflib
import networkx as nx
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add project root to path for imports
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_dir))

try:
    from src.graph.builder import DependencyGraph
    from src.rag.query_router import LLMQueryRouter
except ImportError:
    print("Error: Could not import Project modules. Make sure src/ exists.")
    sys.exit(1)

console = Console()

def load_graph() -> DependencyGraph:
    """Loads the parsed AST data and builds the dependency graph."""
    active_repo = os.getenv("ACTIVE_REPO", "default")
    results_path = os.path.join(root_dir, "results", f"{active_repo}_ast.json")
    
    if not os.path.exists(results_path):
        # Fallback to legacy path from earlier implementation
        legacy_path = os.path.join(root_dir, "results", "ast_parse_output.json")
        if os.path.exists(legacy_path):
            results_path = legacy_path
        else:
            raise FileNotFoundError(f"Graph data not found for repository '{active_repo}'. Please use the [+ Index Repo] button to build it first.")
            
    with open(results_path, 'r') as f:
        data = json.load(f)
        
    builder = DependencyGraph()
    builder.build_from_analysis(data)
    return builder

def extract_target_node(query: str, builder: DependencyGraph, router_words: list = None) -> list[str]:
    """
    Attempts to map the natural language query to a specific node in the graph 
    using both exact token matching and fuzzy string matching.
    """
    # Map all human-readable names to their fully qualified node IDs
    name_to_nodes = {}
    for node, data in builder.graph.nodes(data=True):
        name = data.get('name')
        if name:
            if name not in name_to_nodes:
                name_to_nodes[name] = []
            name_to_nodes[name].append(node)
            
    available_names = list(name_to_nodes.keys())
    potential_nodes = set()
    
    words_to_check = []
    if router_words and len(router_words) > 0:
        words_to_check = [w.lower() for w in router_words]
    else:
        words_to_check = [w.lower() for w in re.findall(r'\b[a-zA-Z_]\w{3,}\b', query)]

    for word in words_to_check:
        # 1. Exact match check
        if word in name_to_nodes:
            potential_nodes.update(name_to_nodes[word])
        else:
            # 2. Fuzzy match check
            matches = difflib.get_close_matches(word, available_names, n=2, cutoff=0.85)
            for match in matches:
                potential_nodes.update(name_to_nodes[match])
            # 3. Substring check
            for name in available_names:
                if len(word) > 3 and word in name.lower():
                    potential_nodes.update(name_to_nodes[name])
                
    # Fallback if LLM router output failed fuzzy matching constraints
    if not potential_nodes and router_words:
        fallback_words = [w.lower() for w in re.findall(r'\b[a-zA-Z_]\w{3,}\b', query)]
        for word in fallback_words:
            if word in name_to_nodes:
                potential_nodes.update(name_to_nodes[word])
            else:
                matches = difflib.get_close_matches(word, available_names, n=2, cutoff=0.85)
                for match in matches:
                    potential_nodes.update(name_to_nodes[match])
                for name in available_names:
                    if len(word) > 3 and word in name.lower():
                        potential_nodes.update(name_to_nodes[name])
                    
    return list(potential_nodes)

def determine_search_direction(query: str, router_dir: str = "none") -> str:
    """
    Simple heuristic to determine if the user wants backwards (impact) or forwards (dependencies) search.
    """
    if router_dir in ["backward", "forward", "both"]:
        return router_dir
        
    query_lower = query.lower()
    
    impact_keywords = ['affect', 'change', 'impact', 'modify', 'break', 'calls']
    depend_keywords = ['depend', 'use', 'call', 'inside']
    
    # Simple regex to catch "what calls X" vs "what does X call"
    if re.search(r'calls?\s+\w+', query_lower) and not re.search(r'does\s+\w+\s+call', query_lower):
        return 'backward'
        
    for word in impact_keywords:
        if word in query_lower:
            return 'backward'
            
    for word in depend_keywords:
        if word in query_lower:
            return 'forward'
            
    return 'both' # Fallback to showing both

def get_context_string_for_llm(node_name: str, impact_paths: list, dep_paths: list, risk: str) -> str:
    """Feature 3: Return raw text injection ready for the Hybrid LLM Prompt"""
    ctx = f"STRUCTURAL GRAPH DATA FOR: {node_name}\n"
    ctx += f"Architectural Risk Level: {risk}\n"
    if impact_paths:
        ctx += "The following components CALL this function (Impacts):\n"
        for p in impact_paths:
            ctx += f"  - {p}\n"
    if dep_paths:
        ctx += "This function DEPENDS ON the following components:\n"
        for p in dep_paths:
            ctx += f"  - {p}\n"
    return ctx

def run_graph_search(query: str, depth: int = 5):
    """
    Executes a structural search on the Dependency Graph with advanced features.
    """
    try:
        console.print("[dim]Loading Dependency Graph...[/dim]")
        builder = load_graph()
        
        console.print("[dim]LLM Parsing Query Intent...[/dim]")
        router = LLMQueryRouter()
        intent = router.extract_intent(query)
        
        target_nodes = extract_target_node(query, builder, router_words=intent.get("target_nodes", []))
        
        if not target_nodes:
            console.print(f"[yellow]Could not find any function or class in the graph matching words in: '{query}'[/]")
            return
            
        direction = determine_search_direction(query, router_dir=intent.get("direction", "none"))
        
        for target in target_nodes:
            node_data = builder.graph.nodes[target]
            node_type = node_data.get('type', 'node')
            
            # --- NEW FEATURE 1: Architectural Risk / Centrality computation ---
            # How many things directly rely on this exact node?
            in_degree = builder.graph.in_degree(target)
            risk = "HIGH" if in_degree > 5 else ("MEDIUM" if in_degree > 2 else "LOW")
            risk_color = "red" if in_degree > 5 else ("yellow" if in_degree > 2 else "green")
            
            console.print(f"\n[bold magenta]Graph Matches for {node_type.capitalize()}:[/] [green]{target}[/]")
            console.print(f"Architectural Risk Factor: [bold {risk_color}]{risk}[/] [dim](Called directly by {in_degree} components)[/]")
            
            impact_paths_for_llm = []
            dep_paths_for_llm = []

            if direction in ['backward', 'both']:
                impact = builder.get_impact_radius(target, depth=depth)
                
                table = Table(title=f"IMPACT ANALYSIS (What calls {node_data.get('name')})", show_lines=True)
                table.add_column("Distance", style="dim", justify="center")
                table.add_column("Caller Node", style="cyan")
                table.add_column("Exact Call Path", style="green")  # --- NEW FEATURE 2: Call Path Visualization ---
                
                if not impact:
                    table.add_row("-", "No callers found in graph (Top-level entry point)", "-")
                else:
                    impact_sorted = []
                    for imp_node in impact:
                        try:
                            path = nx.shortest_path(builder.graph, source=imp_node, target=target)
                            dist = len(path) - 1
                            # Format nicely: A -> B -> target
                            path_str = " → ".join([p.split(':')[-1] for p in path])
                        except:
                            dist = depth
                            path_str = "Unknown"
                        impact_sorted.append((dist, imp_node, path_str))
                    
                    impact_sorted.sort(key=lambda x: x[0])
                    for dist, imp_node, path_str in impact_sorted:
                        imp_data = builder.graph.nodes[imp_node]
                        if imp_data.get('type') != 'file':
                            table.add_row(f"{dist} hop(s)", imp_node, path_str)
                            impact_paths_for_llm.append(path_str)
                            
                console.print(table)
                
            if direction in ['forward', 'both']:
                deps = builder.get_dependencies(target, depth=depth)
                
                table = Table(title=f"DEPENDENCY ANALYSIS (What does {node_data.get('name')} call?)", show_lines=True)
                table.add_column("Distance", style="dim", justify="center")
                table.add_column("Called Node", style="cyan")
                table.add_column("Exact Call Path", style="green") # --- NEW FEATURE 2 ---
                
                if not deps:
                    table.add_row("-", "No dependencies found in graph (Leaf function)", "-")
                else:
                    deps_sorted = []
                    for dep_node in deps:
                        try:
                            path = nx.shortest_path(builder.graph, source=target, target=dep_node)
                            dist = len(path) - 1
                            path_str = " → ".join([p.split(':')[-1] for p in path])
                        except:
                            dist = depth
                            path_str = "Unknown"
                        deps_sorted.append((dist, dep_node, path_str))
                        
                    deps_sorted.sort(key=lambda x: x[0])
                    for dist, dep_node, path_str in deps_sorted:
                        dep_data = builder.graph.nodes[dep_node]
                        if dep_data.get('type') != 'file':
                            table.add_row(f"{dist} hop(s)", dep_node, path_str)
                            dep_paths_for_llm.append(path_str)
                            
                console.print(table)
                
            # Secret unseen export method that the final Hybrid RAG model will use
            # to feed the LLM. 
            _ = get_context_string_for_llm(target, impact_paths_for_llm, dep_paths_for_llm, risk)

    except Exception as e:
        console.print(f"[red]Error during graph search: {e}[/]")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Structural graph search using AST dependency graph.")
    parser.add_argument("query", type=str, help="The question (e.g., 'What breaks if I change authenticate?')")
    parser.add_argument("-d", "--depth", type=int, default=5, help="Max depth (hops) to traverse the graph.")
    
    args = parser.parse_args()
    run_graph_search(args.query, depth=args.depth)
