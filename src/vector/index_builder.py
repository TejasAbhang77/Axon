import os
import sys
import json
import hashlib
import re
import chromadb
from pathlib import Path
from typing import List, Dict, Any

root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.llm_provider import create_client, get_embedding_model, get_provider, is_openrouter_free_embedding
from dotenv import load_dotenv

# Load environment variables from the project root .env file.
load_dotenv(root_dir / ".env")

def _truncate_utf8(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8")[:max_bytes]
    return encoded.decode("utf-8", errors="ignore")


def _split_utf8(text: str, max_bytes: int = 450) -> List[str]:
    """Split text into small pieces compatible with the free model's 512-token cap."""
    if not text:
        return [""]
    pieces = []
    start = 0
    while start < len(text):
        end = start
        size = 0
        while end < len(text):
            char_size = len(text[end].encode("utf-8"))
            if size + char_size > max_bytes:
                break
            size += char_size
            end += 1
        if end < len(text):
            newline = text.rfind("\n", start + max(1, (end - start) // 2), end)
            if newline > start:
                end = newline + 1
        if end == start:
            end += 1
        pieces.append(text[start:end])
        start = end
    return pieces


def _split_chunks_for_free_embedding(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not is_openrouter_free_embedding():
        return chunks
    expanded = []
    for chunk in chunks:
        content = chunk["content"]
        parts = _split_utf8(content)
        offset = 0
        for index, part in enumerate(parts):
            metadata = dict(chunk["metadata"])
            if len(parts) > 1:
                start_line = int(metadata.get("line", 1)) + content[:offset].count("\n")
                line_count = part.count("\n")
                end_line = start_line + max(0, line_count - (1 if part.endswith("\n") else 0))
                metadata["line"] = start_line
                metadata["end_line"] = min(int(metadata.get("end_line", end_line)), end_line)
                metadata["part"] = index + 1
                metadata["parts"] = len(parts)
            item = dict(chunk)
            item["id"] = f"{chunk['id']}:part:{index + 1}" if len(parts) > 1 else chunk["id"]
            item["content"] = part
            item["metadata"] = metadata
            expanded.append(item)
            offset += len(part)
    return expanded


class VectorIndex:
    """
    Handles embedding generation and storage in ChromaDB.
    """
    def __init__(self, collection_name: str = None):
        repo_name = collection_name or os.getenv("ACTIVE_REPO", "default")
        self.embedding_model = get_embedding_model()
        self.provider = get_provider()
        self.client = create_client()

        # Keep vectors from different embedding models in separate collections.
        # OpenAI's default vectors are 1536-dimensional; the free OpenRouter model
        # returns 1024 dimensions, so sharing a collection would fail at query time.
        repo_slug = re.sub(r"[^a-z0-9_-]+", "-", repo_name.lower()).strip("-_") or "default"
        model_hash = hashlib.sha256(self.embedding_model.encode("utf-8")).hexdigest()[:10]
        namespaced_collection = f"{repo_slug[:45]}-{model_hash}"

        self.chroma_client = chromadb.PersistentClient(path=os.path.join(root_dir, "data", "chroma"))
        self.collection = self.chroma_client.get_or_create_collection(name=namespaced_collection)

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings with the configured provider and model in batches of 50.
        The free OpenRouter embedding model is limited to 512 tokens per input;
        indexing chunks are split before this method is called.
        """
        all_embeddings = []
        batch_size = 50
        
        safe_texts = list(texts)
        if is_openrouter_free_embedding():
            # Query text should normally be short. Keep pathological prompts below
            # the provider's 512-token input cap (UTF-8 byte cap is conservative).
            safe_texts = [_truncate_utf8(t, 450) for t in safe_texts]

        for i in range(0, len(safe_texts), batch_size):
            batch = safe_texts[i : i + batch_size]
            print(f"  > Batch {i//batch_size + 1}/{ (len(safe_texts)-1)//batch_size + 1}")
            try:
                response = self.client.embeddings.create(
                    input=batch,
                    model=self.embedding_model
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

        chunks = _split_chunks_for_free_embedding(chunks)
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
        if "API key" in str(e):
            print("\nTIP: Configure AI_PROVIDER and the matching API key in the project root .env file.")
