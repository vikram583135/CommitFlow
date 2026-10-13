import json
from typing import Dict, Any
from anthropic import Anthropic
from .base import BaseAIAdapter
from .schemas import CodeProposal

class AnthropicAdapter(BaseAIAdapter):
    def __init__(self, api_key: str, model_name: str = "claude-3-5-sonnet-20241022"):
        super().__init__(api_key, model_name or "claude-3-5-sonnet-20241022")
        self.client = Anthropic(api_key=self.api_key)

    def test_connection(self) -> bool:
        try:
            self.client.messages.create(
                model=self.model_name,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}]
            )
            return True
        except Exception:
            return False

    def generate_changes(self, instructions: str, repo_context: Dict[str, Any]) -> CodeProposal:
        prompt = f"""
You are CommitFlow, an automated engineering habit assistant.
Generate real, high-quality code changes matching user instructions.

Repository: {repo_context.get('repo_name', 'project')}
Allowed Paths: {repo_context.get('allowed_paths', ['src/'])}
Context: {json.dumps(repo_context.get('file_tree', []))}
Task: {instructions}

Respond ONLY with valid raw JSON (no markdown formatting, no code blocks):
{{
  "summary": "...",
  "commit_message": "...",
  "pr_title": "...",
  "pr_body": "...",
  "files": [
    {{"path": "...", "change_type": "CREATE", "content": "..."}}
  ]
}}
"""
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=4096,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.content[0].text.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        data = json.loads(content.strip())
        return CodeProposal(**data)
