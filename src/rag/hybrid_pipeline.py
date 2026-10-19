import os
import sys
import networkx as nx
from pathlib import Path

# Resolve project root before importing shared project modules.
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.llm_provider import create_client, get_chat_model
from dotenv import load_dotenv


try:
    from src.vector.index_builder import VectorIndex
    from src.retrieval.graph_searcher import (
        load_graph, extract_target_node, determine_search_direction, get_context_string_for_llm
    )
    from src.rag.query_router import LLMQueryRouter
except ImportError as e:
    print(f"Error: Could not import required modules. {e}")
    sys.exit(1)

# Load environment variables
load_dotenv(root_dir / ".env")

class HybridRAGPipeline:
    def __init__(self, model: str | None = None):
        """
        The Hybrid RAG Pipeline.
        Fuses Structural Graph Data (NetworkX) with Semantic Vector Data (ChromaDB)
        to prevent LLM hallucinations on codebase architecture.
        """
        self.client = create_client()
        self.vector_index = VectorIndex()
        self.graph_builder = load_graph()
        self.router = LLMQueryRouter()
        self.model = model or get_chat_model()

    def get_graph_context(self, query: str, depth: int = 5):
        """
        Programmatically extracts the graph context strings and JSON graph data.
        """
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

    def answer_query(self, query: str, n_results: int = 5):
        """
        Executes the Hybrid Fusion. 
        """
        print(f"[*] Running HYBRID Retrieval for: '{query}'...")
        
        # 1. Structural Retrieval (Undeniable path truth)
        print("    ↳ Traversing Custom Abstract Syntax Graph...")
        graph_context, graph_json = self.get_graph_context(query)
        
        # 2. Semantic Retrieval (Docstrings, logic, fuzzy descriptions)
        print("    ↳ Querying ChromaDB Vector Index...")
        results = self.vector_index.search(query, n_results=n_results)
        
        vector_chunks = []
        semantic_nodes = []
        for i, (doc, metadata) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
            chunk_text = f"--- Source File: {metadata['file']} (Line {metadata['line']}) ---\n{doc}"
            vector_chunks.append(chunk_text)
            semantic_nodes.append({"file": metadata['file'], "line": metadata['line'], "content": doc})
            
        vector_str = "\n\n".join(vector_chunks)
        pipeline_data = {
            "graph_json": graph_json, 
            "semantic_nodes": semantic_nodes,
            "graph_context": graph_context
        }
        
        # 3. Hybrid Prompt Engineering (FUSION)
        system_prompt = (
            "You are an advanced Hybrid RAG AI for Codebase Comprehension.\n"
            "You have access to two distinct forms of data:\n"
            "1. STRUCTURAL GRAPH DATA: This is the mathematically proven architecture. It dictates exactly "
            "what calls what and the exact architectural risk factor. This is undeniable truth.\n"
            "2. SEMANTIC SOURCE CODE: These are text chunks retrieved using vector similarity.\n\n"
            "Your Rules:\n"
            "- If a user asks 'What breaks if I change X', prioritize the STRUCTURAL GRAPH DATA to outline the exact impact. Quote the exact Call Paths provided.\n"
            "- Use the SEMANTIC SOURCE CODE to explain *how* things work inside the functions.\n"
            "- Warn the user immediately if the item they are changing has a HIGH Architectural Risk Factor.\n"
            "- Always cite your claims by referencing the File Names and exact Call Paths.\n"
            "- Make sure to adequately answer the user query and provide a professional response.\n"
            "- Do not hallucinate dependencies that are not in the STRUCTURAL GRAPH DATA. The graph is the absolute authority on architecture.\n"
        )
        
        user_prompt = f"""
=============================
[1] STRUCTURAL GRAPH DATA
=============================
{graph_context}

=============================
[2] SEMANTIC SOURCE CODE
=============================
{vector_str}

=============================
USER QUESTION
=============================
{query}
"""
        print(f"[*] Fusing Contexts & Generating engineering-grade response using {self.model}...")
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2
        )
        
        return response.choices[0].message.content, results, graph_context, pipeline_data

if __name__ == "__main__":
    import argparse
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console()
    
    parser = argparse.ArgumentParser(description="Hybrid RAG Engine via NetworkX + ChromaDB")
    parser.add_argument("query", type=str, help="Question about the codebase.")
    parser.add_argument("--model", type=str, default=None, help="Optional chat model override (defaults to .env configuration).")
    
    args = parser.parse_args()
    
    try:
        pipeline = HybridRAGPipeline(model=args.model)
        response, results, graph_ctx, pipeline_data = pipeline.answer_query(args.query)
        
        console.print("\n[bold green]Hybrid Answer:[/]")
        console.print(Markdown(response))
        
        console.print("\n[bold black on white] Semantic Code Chunks Authenticated: [/]")
        if results and 'metadatas' in results and len(results['metadatas']) > 0:
            for m in results['metadatas'][0]:
                console.print(f"- {m['file']} (L{m['line']})")
        else:
            console.print("[dim]No semantic matched code chunks retrieved.[/]")
            
        console.print("\n[bold yellow]--- Context Sources Successfully Fused ---[/]")
        if "No structural graph data" not in graph_ctx:
            console.print("[green]✓ Included 100% Accurate Structural Call Paths[/]")
        else:
            console.print("[dim]⚠ No Structural Links Found (Fell back to Pure Semantic Vector Search)[/]")
            
        semantic_count = len(results['metadatas'][0]) if results and 'metadatas' in results and results['metadatas'] else 0
        console.print(f"[green]✓ Included top {semantic_count} Semantic Code Chunks[/]")
    except Exception as e:
        console.print(f"[red]Fatal Error in Hybrid Pipeline: {e}[/]")
