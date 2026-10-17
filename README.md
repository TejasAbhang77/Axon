# Hybrid RAG for Codebase Comprehension

A research-focused Hybrid Retrieval-Augmented Generation (RAG) system that integrates semantic vector retrieval with AST-derived dependency graphs.

## Core Features
- **AST Parsing**: uses `tree-sitter` to extract functions, classes, and call relationships.
- **Dependency Graph**: Built with `NetworkX` for multi-hop impact analysis.
- **Hybrid Retrieval**: (In Progress) Fusing vector and structural signals.

## Project Structure
- `src/ast_parser`: Tree-sitter parsing logic.
- `src/graph`: Dependency graph construction and visualization.
- `results/`: Output data and visualizations (ignored in git).
- `data/repos/`: Target repositories for analysis (ignored in git).

## Setup
1. Create venv: `python -m venv venv`
2. Activate venv: `.\venv\Scripts\activate`
3. Install deps: `pip install -r requirements.txt`

## Usage
Refer to `project_commands.txt` for detailed instructions on running the parser and visualizer.
