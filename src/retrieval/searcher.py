import os
import argparse
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from pathlib import Path

# Try to import our index builder
import sys
# Add project root to path for imports
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_dir))

try:
    from src.vector.index_builder import VectorIndex
except ImportError:
    print("Error: Could not import VectorIndex. Make sure src/vector/index_builder.py exists.")
    sys.exit(1)

console = Console()

def run_search(query: str, n_results: int = 5):
    """
    Search the vector index and display results beautifully.
    """
    try:
        index = VectorIndex()
        results = index.search(query, n_results=n_results)
        
        if not results or not results['documents'][0]:
            console.print("[yellow]No relevant code chunks found.[/]")
            return

        table = Table(title=f"Semantic Search Results for: '{query}'", show_lines=True)
        table.add_column("Rank", style="dim", width=4)
        table.add_column("Score", style="cyan", width=8)
        table.add_column("Location & Code", style="white")

        for i, (doc, metadata, dist) in enumerate(zip(results['documents'][0], results['metadatas'][0], results['distances'][0])):
            # Score is distance (lower is better for Chroma default)
            score = 1 - dist # Heuristic similarity score
            
            location_info = f"[bold green]{metadata['file']}[/] | [bold blue]{metadata['type']}: {metadata['name']}[/] (Line {metadata['line']})"
            
            # Syntax highlighted code preview
            code_snippet = Syntax(doc.strip(), "python", theme="monokai", line_numbers=True, start_line=metadata['line'])
            
            table.add_row(
                str(i+1),
                f"{score:.4f}",
                Panel(code_snippet, title=location_info, border_style="bright_black")
            )
            
        console.print(table)

    except Exception as e:
        console.print(f"[red]Error during search: {e}[/]")
        if "OPENAI_API_KEY" in str(e):
             console.print("\n[bold]TIP:[/] Run `set OPENAI_API_KEY=your_key` or add it to a .env file.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Semantic code search using the hybrid-rag index.")
    parser.add_argument("query", type=str, help="The question or keywords to search for.")
    parser.add_argument("-n", "--num", type=int, default=3, help="Number of results to return.")
    
    args = parser.parse_args()
    
    run_search(args.query, n_results=args.num)
