from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
import sys
import subprocess
import shutil
from pathlib import Path

from src.rag.pipeline import RAGPipeline
from src.rag.graph_pipeline import GraphRAGPipeline
from src.rag.hybrid_pipeline import HybridRAGPipeline

app = FastAPI(title="Axon Engine API", description="Backend API for the Axon RAG web platform.")

# Allow CORS for local frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str
    mode: str = "hybrid" # 'vector', 'graph', or 'hybrid'
    repo: str = "default" # Target Repository

@app.get("/")
def health_check():
    return {"status": "Axon API is running."}

class CloneRequest(BaseModel):
    url: str

@app.get("/api/repos")
def list_repos():
    repos_dir = Path("data/repos")
    if not repos_dir.exists():
        return {"repos": []}
    
    repos = []
    for item in repos_dir.iterdir():
        if item.is_dir():
            repos.append(item.name)
        
    return {"repos": repos}

@app.post("/api/repos/clone")
def clone_repo(req: CloneRequest):
    url = req.url.strip()
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid repository URL")
        
    repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
    repos_dir = Path("data/repos")
    repos_dir.mkdir(parents=True, exist_ok=True)
    target_dir = repos_dir / repo_name
    
    try:
        # Clone repo if it doesn't exist
        if not target_dir.exists():
            subprocess.run(["git", "clone", url, str(target_dir)], check=True)
            
        ensure_repo_indexed(repo_name)
        return {"status": "success", "repo": repo_name}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Pipeline Process Failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")

def ensure_repo_indexed(repo_name: str):
    """
    Check if the repo has AST and Vector data. If not, trigger the pipeline.
    """
    repos_dir = Path("data/repos")
    target_dir = repos_dir / repo_name
    if not target_dir.exists():
        return # Repo doesn't even exist locally

    ast_file = Path("results") / f"{repo_name}_ast.json"
    
    # Isolate environment variable internally for nested subprocesses
    env = os.environ.copy()
    env["ACTIVE_REPO"] = repo_name

    # 1. Run AST Parser if missing
    if not ast_file.exists():
        print(f"[*] Missing AST for {repo_name}. Running Parser...")
        subprocess.run([sys.executable, "src/ast_parser/parser.py", str(target_dir)], check=True, env=env)
    
    # 2. Run Vector Indexer (Always safe to run, updates existing or creates new)
    # We check if collection exists in Chroma inside the script or just run it.
    # To be fast, let's just trigger it if Chroma dir is empty or we suspect it's missing.
    # For now, let's just RUN IT to ensure it's built if repo is selected.
    print(f"[*] Ensuring Vector Index for {repo_name}...")
    subprocess.run([sys.executable, "src/vector/index_builder.py"], check=True, env=env)

@app.post("/api/query")
def run_query(req: QueryRequest):
    if not req.query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
        
    # Dynamically isolate the memory space to target repo
    os.environ["ACTIVE_REPO"] = req.repo
    
    # ENSURE INDEXED BEFORE RUNNING
    try:
        ensure_repo_indexed(req.repo)
    except Exception as e:
        print(f"Indexing auto-trigger failed: {e}")

    try:
        metadata = []
        graph_data = None
        pipeline_data = None
        
        if req.mode == "hybrid":
            pipeline = HybridRAGPipeline()
            answer, sources, graph_ctx, p_data = pipeline.answer_query(req.query)
            if sources and 'metadatas' in sources and len(sources['metadatas']) > 0:
                metadata = sources['metadatas'][0]
            graph_data = graph_ctx
            pipeline_data = p_data
        elif req.mode == "graph":
            pipeline = GraphRAGPipeline()
            answer, graph_ctx, p_data = pipeline.answer_query(req.query)
            graph_data = graph_ctx
            pipeline_data = p_data
        elif req.mode == "vector":
            pipeline = RAGPipeline()
            answer, sources, p_data = pipeline.answer_query(req.query)
            if sources and 'metadatas' in sources and len(sources['metadatas']) > 0:
                metadata = sources['metadatas'][0]
            pipeline_data = p_data
        else:
            raise HTTPException(status_code=400, detail="Mode must be 'hybrid', 'graph', or 'vector'")
            
        return {
            "answer": answer, 
            "mode": req.mode,
            "metadata": metadata,
            "graph_data": graph_data,
            "pipeline_data": pipeline_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Engine Error: {str(e)}")

@app.get("/api/repos/{repo}/graph")
def get_full_graph(repo: str):
    os.environ["ACTIVE_REPO"] = repo
    try:
        ensure_repo_indexed(repo)
    except:
        pass

    try:
        from src.retrieval.graph_searcher import load_graph
        builder = load_graph()
        nodes = []
        for n, data in builder.graph.nodes(data=True):
            nodes.append({
                "id": n,
                "label": data.get("name", n.split(":")[-1]),
                "type": data.get("type", "node"),
                "file": data.get("file", "")
            })
        
        links = []
        for u, v in builder.graph.edges():
            links.append({"source": u, "target": v})
            
        return {"nodes": nodes, "links": links}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Start server locally
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
