import os
import sys
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

# Add project root to path for imports
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_dir))

try:
    from src.vector.index_builder import VectorIndex
except ImportError:
    print("Error: Could not import VectorIndex from src/vector/index_builder.py")
    sys.exit(1)

# Load environment variables
load_dotenv(root_dir / ".env")

class RAGPipeline:
    def __init__(self, model: str = "gpt-4o-mini"):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment. Please add it to your .env file.")
            
        self.client = OpenAI(api_key=self.api_key)
        self.vector_index = VectorIndex()
        self.model = model

    def answer_query(self, query: str, n_results: int = 5):
        """
        Full RAG flow: Retrieval -> Augmentation -> Generation
        """
        # 1. RETRIEVAL
        print(f"[*] Searching for context for: '{query}'...")
        results = self.vector_index.search(query, n_results=n_results)
        
        context_chunks = []
        semantic_nodes = []
        for i, (doc, metadata) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
            chunk_text = f"--- Chunk {i+1} (Source: {metadata['file']}, Line {metadata['line']}) ---\n{doc}"
            context_chunks.append(chunk_text)
            semantic_nodes.append({"file": metadata['file'], "line": metadata['line'], "content": doc})
        
        context_str = "\n\n".join(context_chunks)
        pipeline_data = {"semantic_nodes": semantic_nodes}

        # 2. GENERATION (Strict adherence to provided context)
        system_prompt = (
            "You are a strict technical assistant. Your goal is to explain code dependencies "
            "based ONLY on the provided snippets. Follow these rules EXACTLY:\n"
            "1. If the answer is not explicitly contained in the provided context, state: 'I do not have enough "
            "information in the retrieved snippets to answer this fully.'\n"
            "2. DO NOT use your internal knowledge about libraries or typical code patterns to fill gaps.\n"
            "3. Cite the exact filename and line number for EVERY claim you make.\n"
            "4. If you see a function call but don't have the body of that function, DO NOT guess what it does.\n"
            "5. If the user asks for an 'impact' or 'dependency,' only list the connections you can see in the text."
        )
        
        user_prompt = f"Context:\n{context_str}\n\nQuestion: {query}\n\nAnswer:"

        print(f"[*] Generating answer using {self.model}...")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0
        )
        
        return response.choices[0].message.content, results, pipeline_data

if __name__ == "__main__":
    import argparse
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console()
    
    parser = argparse.ArgumentParser(description="Full RAG Pipeline for Codebase Comprehension")
    parser.add_argument("query", type=str, help="Question about the codebase.")
    parser.add_argument("--model", type=str, default="gpt-4o-mini", help="OpenAI model to use.")
    
    args = parser.parse_args()
    
    try:
        pipeline = RAGPipeline(model=args.model)
        answer, sources, pipeline_data = pipeline.answer_query(args.query)
        
        console.print("\n[bold cyan]=== RAG ANSWER ===[/]\n")
        console.print(Markdown(answer))
        
        console.print("\n[bold yellow]=== SOURCES USED ===[/]")
        for i, metadata in enumerate(sources['metadatas'][0]):
            console.print(f"{i+1}. {metadata['file']} (Line {metadata['line']}) - {metadata['type']}: {metadata['name']}")
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
