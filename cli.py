import os
import sys
import subprocess
import shutil
from pathlib import Path

# Provide a clean fallback if rich isn't installed
try:
    from rich.console import Console
    from rich.prompt import Prompt, Confirm
    console = Console()
except ImportError:
    print("Error: The 'rich' library is required. Run 'pip install rich'")
    sys.exit(1)

root_dir = Path(__file__).resolve().parent

def run_cmd(cmd_list):
    """Executes a terminal command and handles errors."""
    try:
        subprocess.run(cmd_list, check=True, cwd=str(root_dir))
    except subprocess.CalledProcessError:
        console.print(f"[red]❌ Command failed:[/] {' '.join(cmd_list)}")
        console.print("[dim]Please check the output above for specific errors.[/dim]")
        # Do not exit entirely, allow user to continue if possible
    except FileNotFoundError:
        console.print(f"[red]❌ Could not find executable for command:[/] {cmd_list[0]}")
        sys.exit(1)

def on_rm_error(func, path, exc_info):
    """Helper to forcefully delete read-only files on Windows."""
    import stat
    os.chmod(path, stat.S_IWRITE)
    os.unlink(path)

def main():
    console.print("[bold cyan]===========================================================[/]")
    console.print("[bold cyan]        HYBRID RAG ORCHESTRATOR (CLI INTERFACE)            [/]")
    console.print("[bold cyan]===========================================================\n[/]")

    # -------------------------------------------------------------
    # 1. SETUP REPOSITORY
    # -------------------------------------------------------------
    repo_input = Prompt.ask("[bold green]Enter a local directory path OR a GitHub URL to analyze[/]")
    
    if "github.com" in repo_input or "http" in repo_input:
        repo_name = repo_input.rstrip("/").split("/")[-1].replace(".git", "")
        repos_dir = root_dir / "data" / "repos"
        os.makedirs(repos_dir, exist_ok=True)
        target_dir = repos_dir / repo_name
        
        if os.path.exists(target_dir):
            if Confirm.ask(f"[yellow]Repo '{repo_name}' already exists in data/repos/. Delete and re-clone?[/]", default=False):
                console.print(f"[dim]Deleting existing {target_dir}...[/]")
                shutil.rmtree(target_dir, onerror=on_rm_error)
                console.print(f"[dim]Cloning {repo_input}...[/]")
                run_cmd(["git", "clone", repo_input, str(target_dir)])
        else:
            console.print(f"[dim]Cloning {repo_input}...[/]")
            run_cmd(["git", "clone", repo_input, str(target_dir)])
            
        repo_path = str(target_dir)
        os.environ["ACTIVE_REPO"] = repo_name
    else:
        repo_path = repo_input
        if not os.path.exists(repo_path):
            console.print(f"[red]Error: The path '{repo_path}' does not exist![/]")
            sys.exit(1)
        repo_name = Path(repo_path).name
        os.environ["ACTIVE_REPO"] = repo_name

    console.print(f"\n[green]✅ Target repository isolated as:[/] {repo_name}")

    # -------------------------------------------------------------
    # 2. RUN PIPELINES (AST + VECTOR)
    # -------------------------------------------------------------
    if Confirm.ask("\n[bold yellow]Rebuild the AST and Dependency Graph?[/] (Required if code changed since last time)", default=True):
        console.print("\n[dim]Running parser.py...[/]")
        run_cmd([sys.executable, "src/ast_parser/parser.py", repo_path])

    if Confirm.ask("\n[bold yellow]Rebuild the Semantic Vector Embeddings?[/] (Costs OpenAI API credits, skip if already indexed)", default=False):
        console.print("\n[dim]Running index_builder.py...[/]")
        run_cmd([sys.executable, "src/vector/index_builder.py"])

    # -------------------------------------------------------------
    # 3. INTERACTIVE SEARCH LOOP
    # -------------------------------------------------------------
    console.print("\n[bold cyan]==================== SEARCH MODE ==========================[/]")
    console.print("[italic]You can now ask architectural and dependency questions.[/]\n")
    
    while True:
        mode = Prompt.ask(
            "[bold green]Select search engine[/]", 
            choices=["vector", "graph", "hybrid", "both", "exit"], 
            default="hybrid"
        )
        
        if mode == "exit":
            console.print("\n[dim]Exiting orchestrator. Goodbye![/]")
            break
            
        query = Prompt.ask("\n[bold magenta]Enter your question (e.g., 'What breaks if I change process_data?')[/]")
        
        if not query.strip():
            continue
            
        console.print("") # spacing
        
        if mode in ["vector", "both"]:
            console.print("[bold black on white] --- SEMANTIC VECTOR SEARCH RESULTS --- [/]")
            run_cmd([sys.executable, "src/retrieval/searcher.py", query])
            console.print("\n")
            
        if mode in ["graph", "both"]:
            console.print("[bold black on white] --- STRUCTURAL GRAPH SEARCH RESULTS --- [/]")
            run_cmd([sys.executable, "src/retrieval/graph_searcher.py", query])

        if mode == "hybrid":
            console.print("[bold black on white] --- FULL HYBRID RAG ENGINE --- [/]")
            run_cmd([sys.executable, "src/rag/hybrid_pipeline.py", query])
            
        console.print("\n[dim]" + "-"*60 + "[/]\n")

if __name__ == "__main__":
    # Ensure run from correct directory
    os.chdir(root_dir)
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[dim]Exited by user.[/]")
        sys.exit(0)
