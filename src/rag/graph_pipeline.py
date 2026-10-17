import os
import sys
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_dir))

try:
    from src.retrieval.graph_searcher import (
        load_graph, extract_target_node, determine_search_direction, get_context_string_for_llm
    )
    from src.rag.query_router import LLMQueryRouter
    import networkx as nx
except ImportError as e:
    print(f"Error: Could not import required modules. {e}")
    sys.exit(1)

load_dotenv(root_dir / ".env")

class GraphRAGPipeline:
    def __init__(self, model: str = "gpt-4o-mini"):
        """
        The Graph-Only RAG Pipeline.
        Feeds ONLY Structural Graph Data (NetworkX) into the LLM. 
        It is completely blind to Semantic Vector Data. Excellent for 
        testing pure architectural questions.
        """
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables.")
            
        self.client = OpenAI(api_key=self.api_key)
        self.graph_builder = load_graph()
        self.router = LLMQueryRouter()
        self.model = model

    def get_graph_context(self, query: str, depth: int = 5):
        """Extracts the exact graph trace strings securely and returns JSON structure."""
        intent = self.router.extract_intent(query)
        target_nodes = extract_target_node(query, self.graph_builder, router_words=intent.get("target_nodes", []))
        
        graph_json = {"nodes": [], "edges": []}
        added_nodes = set()
        added_edges = set()
        
        def add_node(n):
            if n not in added_nodes:
                added_nodes.add(n)
                data = self.graph_builder.graph.nodes[n] if n in self.graph_builder.graph.nodes else {}
                graph_json["nodes"].append({
                    "id": n,
                    "label": data.get("name", n.split(":")[-1]),
                    "type": data.get("type", "node"),
                    "file": data.get("file", "")
                })

        def add_edge(u, v):
            edge_id = f"{u}->{v}"
            if edge_id not in added_edges:
                added_edges.add(edge_id)
                graph_json["edges"].append({"source": u, "target": v})

        if not target_nodes:
            return "No structural graph data found for this query.", graph_json
            
        direction = determine_search_direction(query, router_dir=intent.get("direction", "none"))
        all_graph_contexts = []
        
        for target in target_nodes:
            add_node(target)
            in_degree = self.graph_builder.graph.in_degree(target)
            risk = "HIGH" if in_degree > 5 else ("MEDIUM" if in_degree > 2 else "LOW")
            
            impact_paths_for_llm = []
            dep_paths_for_llm = []
            
            if direction in ['backward', 'both']:
                impact = self.graph_builder.get_impact_radius(target, depth=depth)
                for imp_node in impact:
                    if self.graph_builder.graph.nodes[imp_node].get('type') == 'file': continue
                    try:
                        path_nodes = nx.shortest_path(self.graph_builder.graph, source=imp_node, target=target)
                        path_str = " -> ".join([p.split(':')[-1] for p in path_nodes])
                        for i in range(len(path_nodes) - 1):
                            add_node(path_nodes[i])
                            add_node(path_nodes[i+1])
                            add_edge(path_nodes[i], path_nodes[i+1])
                    except:
                        path_str = imp_node.split(':')[-1]
                        add_node(imp_node)
                        add_edge(imp_node, target)
                    impact_paths_for_llm.append(path_str)
                    
            if direction in ['forward', 'both']:
                deps = self.graph_builder.get_dependencies(target, depth=depth)
                for dep_node in deps:
                    if self.graph_builder.graph.nodes[dep_node].get('type') == 'file': continue
                    try:
                        path_nodes = nx.shortest_path(self.graph_builder.graph, source=target, target=dep_node)
                        path_str = " -> ".join([p.split(':')[-1] for p in path_nodes])
                        for i in range(len(path_nodes) - 1):
                            add_node(path_nodes[i])
                            add_node(path_nodes[i+1])
                            add_edge(path_nodes[i], path_nodes[i+1])
                    except:
                        path_str = dep_node.split(':')[-1]
                        add_node(dep_node)
                        add_edge(target, dep_node)
                    dep_paths_for_llm.append(path_str)
            
            ctx = get_context_string_for_llm(target, impact_paths_for_llm, dep_paths_for_llm, risk)
            all_graph_contexts.append(ctx)
            
        return "\n\n".join(all_graph_contexts), graph_json

    def answer_query(self, query: str):
        """Executes the Graph-Only Generation limit testing Semantic Blindness."""
        print(f"[*] Running PURE GRAPH Retrieval for: '{query}'...")
        
        # 1. Structural Retrieval Only
        print("    ↳ Traversing Custom Abstract Syntax Graph...")
        graph_context, graph_json = self.get_graph_context(query)
        pipeline_data = {
            "graph_json": graph_json, 
            "semantic_nodes": [],
            "graph_context": graph_context
        }
        
        # 2. Strict Generation Protocol
        system_prompt = (
            "You are a strict Graph RAG Architecture Assistant.\n"
            "You only have access to STRUCTURAL GRAPH DATA which represents undeniable architectural reality.\n"
            "You do NOT have access to the actual source code or logic implementation. You are blind to semantical context.\n"
            "Your Rules:\n"
            "1. Answer strictly based on the provided Call Paths.\n"
            "2. If the user asks *how* a function runs internally, politely state that you operate entirely on macro-architecture and lack access to internal logic."
        )
        
        user_prompt = f"[STRUCTURAL GRAPH DATA]\n{graph_context}\n\n[USER QUESTION]\n{query}"
        
        print(f"[*] Generating graph-bound response using {self.model}...")
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1
        )
        
        return response.choices[0].message.content, graph_context, pipeline_data

if __name__ == "__main__":
    import argparse
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console()
    
    parser = argparse.ArgumentParser(description="Graph Only Engine")
    parser.add_argument("query", type=str)
    
    args = parser.parse_args()
    
    try:
        pipeline = GraphRAGPipeline()
        answer, graph_ctx, pipeline_data = pipeline.answer_query(args.query)
        
        console.print("\n[bold cyan]=== PURE GRAPH ENGINE ANSWER ===[/]\n")
        console.print(Markdown(answer))
        
        if "No structural graph data" not in graph_ctx:
            console.print("\n[green]✓ Powered by 100% Accurate Structural Graph Traversal[/]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
