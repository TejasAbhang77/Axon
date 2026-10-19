import os
import json
from src.llm_provider import create_client, get_chat_model, has_api_key

class LLMQueryRouter:
    def __init__(self):
        """
        Uses a highly efficient LLM to parse natural language queries into 
        exact intent structured data. Provides much higher accuracy than regex heuristics.
        """
        self.client = create_client() if has_api_key() else None

    def extract_intent(self, query: str) -> dict:
        """
        Returns a dictionary: {"target_nodes": ["func_name"], "direction": "backward"|"forward"|"both"}
        """
        if not self.client:
            return {"target_nodes": [], "direction": "none"}


        system_prompt = (
            "You are a routing agent for a codebase graph RAG system.\n"
            "Given a human query, extract the specific literal function or class names they are asking about.\n"
            "Also determine the strict 'direction' of the graph traversal needed:\n"
            "- 'backward' (if asking about impact: what breaks, what calls X, what is affected by X)\n"
            "- 'forward' (if asking about dependencies: what does X call, what does X depend on)\n"
            "- 'both' (if ambiguous or just asking for a general explanation).\n"
            "Return ONLY a raw valid JSON object.\n"
            'Example 1: {"target_nodes": ["authenticate_user"], "direction": "backward"}\n'
            'Example 2: {"target_nodes": ["process_data"], "direction": "both"}'
        )
        try:
            response = self.client.chat.completions.create(
                model=get_chat_model(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                response_format={ "type": "json_object" },
                temperature=0,
                max_tokens=60
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"[dim]LLM Router warning: {e}. Falling back to fuzzy heuristics.[/dim]")
            return {"target_nodes": [], "direction": "none"}
