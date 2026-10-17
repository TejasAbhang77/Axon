import os
import json
from openai import OpenAI

class LLMQueryRouter:
    def __init__(self):
        """
        Uses a highly efficient LLM to parse natural language queries into 
        exact intent structured data. Provides much higher accuracy than regex heuristics.
        """
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key)

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
                model="gpt-4o-mini",
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
