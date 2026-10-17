import os
import json
import chromadb
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Dict, Any

# Load environment variables from the project root .env file
# We look for it in the parent of src/vector/ (which is src/) and its parent (root)
root_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(root_dir / ".env")

class VectorIndex:
    """
    Handles embedding generation and storage in ChromaDB.
    """
    def __init__(self, collection_name: str = None):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not collection_name:
            collection_name = os.getenv("ACTIVE_REPO", "default")

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables.")
            
        self.client = OpenAI(api_key=self.api_key)
        
        # Initialize ChromaDB persistent storage
        self.chroma_client = chromadb.PersistentClient(path=os.path.join(root_dir, "data", "chroma"))
        self.collection = self.chroma_client.get_or_create_collection(name=collection_name)
        
        # Fallback mechanism for legacy repositories indexed under codebase_index
        if self.collection.count() == 0:
            legacy = self.chroma_client.get_or_create_collection(name="codebase_index")
            if legacy.count() > 0:
                self.collection = legacy

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings using OpenAI's text-embedding-3-small.
        Splits into batches of 50 to avoid request timeouts and limits.
        Truncates individual strings to 20,000 characters to stay within 8k token limit.
        """
        all_embeddings = []
        batch_size = 50
        
        # Truncate logic
        safe_texts = [t[:20000] if len(t) > 20000 else t for t in texts]

        for i in range(0, len(safe_texts), batch_size):
            batch = safe_texts[i : i + batch_size]
            print(f"  > Batch {i//batch_size + 1}/{ (len(safe_texts)-1)//batch_size + 1}")
            try:
                response = self.client.embeddings.create(
                    input=batch,
                    model="text-embedding-3-small"
                )
                all_embeddings.extend([data.embedding for data in response.data])
            except Exception as e:
                print(f"Error in batch {i}: {e}")
                # Fallback zero-filled embeddings for this batch or raise
                raise e
        return all_embeddings

    def add_chunks(self, chunks: List[Dict[str, Any]]):
        """
        Process and add code chunks to the vector store.
        """
        if self.collection.count() > 0:
            print(f"Collection '{self.collection.name}' already contains {self.collection.count()} items. Skipping indexing.")
            return

        ids = [chunk['id'] for chunk in chunks]
        texts = [chunk['content'] for chunk in chunks]
        metadatas = [chunk['metadata'] for chunk in chunks]
        
        print(f"Generating embeddings for {len(chunks)} chunks...")
        embeddings = self.generate_embeddings(texts)
        
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
        print(f"Successfully added {len(chunks)} chunks to collection '{self.collection.name}'")

    def search(self, query: str, n_results: int = 5):
        """
        Semantic search for the most relevant code chunks.
        """
        query_embedding = self.generate_embeddings([query])[0]
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        return results

class CodeChunker:
    """
    Chunks code based on AST structure (function/class level).
    """
    def __init__(self, analysis_path: str):
        self.analysis_path = analysis_path
        if not os.path.exists(analysis_path):
            raise FileNotFoundError(f"AST analysis file not found: {analysis_path}")
            
        with open(analysis_path, 'r') as f:
            self.analysis = json.load(f)

    def extract_chunks(self) -> List[Dict[str, Any]]:
        """
        Read original source files and extract code bodies.
        """
        chunks = []
        for file_data in self.analysis:
            file_path = file_data['file_path']
            if not os.path.exists(file_path):
                print(f"Warning: Source file not found: {file_path}")
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                continue

            # Process functions
            for func in file_data.get('functions', []):
                # line numbers in analysis are 1-indexed
                start = func['line'] - 1
                end = func['end_line']
                body = "".join(lines[start:end])
                
                # Create a unique ID
                # We use a short path for readability in IDs
                try:
                    rel_path = os.path.relpath(file_path, root_dir)
                except ValueError:
                    rel_path = os.path.basename(file_path)
                    
                chunk_id = f"{rel_path}:func:{func['name']}:{func['line']}"
                chunks.append({
                    "id": chunk_id,
                    "content": body,
                    "metadata": {
                        "type": "function",
                        "name": func['name'],
                        "file": rel_path,
                        "line": func['line'],
                        "end_line": func['end_line']
                    }
                })

            # Process classes
            for cls in file_data.get('classes', []):
                start = cls['line'] - 1
                end = cls['end_line']
                body = "".join(lines[start:end])
                
                try:
                    rel_path = os.path.relpath(file_path, root_dir)
                except ValueError:
                    rel_path = os.path.basename(file_path)

                chunk_id = f"{rel_path}:class:{cls['name']}:{cls['line']}"
                chunks.append({
                    "id": chunk_id,
                    "content": body,
                    "metadata": {
                        "type": "class",
                        "name": cls['name'],
                        "file": rel_path,
                        "line": cls['line'],
                        "end_line": cls['end_line']
                    }
                })
        return chunks

if __name__ == "__main__":
    # --- Configuration ---
    # Path to the AST analysis output
    active_repo = os.getenv("ACTIVE_REPO", "default")
    AST_RESULTS = root_dir / "results" / f"{active_repo}_ast.json"
    
    try:
        # 1. Extact chunks from source code using AST metadata
        print(f"Loading AST analysis from: {AST_RESULTS}")
        chunker = CodeChunker(str(AST_RESULTS))
        chunks = chunker.extract_chunks()
        print(f"Extracted {len(chunks)} code chunks.")

        # 2. Build/Update the Vector Index
        index = VectorIndex()
        index.add_chunks(chunks)
        
        # 3. Quick test query
        test_query = "how to decrypt data using a gps hash?"
        print(f"\n[TEST SEARCH] Query: '{test_query}'")
        results = index.search(test_query, n_results=3)
        
        for i, (doc, metadata, dist) in enumerate(zip(results['documents'][0], results['metadatas'][0], results['distances'][0])):
            print(f"\n--- Result {i+1} (Distance: {dist:.4f}) ---")
            print(f"Location: {metadata['file']} | {metadata['type']}: {metadata['name']} (Line {metadata['line']})")
            # Print a preview of the code
            lines = doc.strip().split('\n')
            preview = "\n".join(lines[:5]) + ("\n..." if len(lines) > 5 else "")
            print(f"Code Preview:\n{preview}")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        if "OPENAI_API_KEY" in str(e):
            print("\nTIP: Create a .env file in the project root with: OPENAI_API_KEY=your_key_here")
