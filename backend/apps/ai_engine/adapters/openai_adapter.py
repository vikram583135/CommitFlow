import json
from typing import Dict, Any
from openai import OpenAI
from .base import BaseAIAdapter
from .schemas import CodeProposal

class OpenAIAdapter(BaseAIAdapter):
    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini"):
        super().__init__(api_key, model_name or "gpt-4o-mini")
        self.client = OpenAI(api_key=self.api_key)

    def test_connection(self) -> bool:
        try:
            response = self.client.models.list()
            return True
        except Exception as e:
            return False

    def generate_changes(self, instructions: str, repo_context: Dict[str, Any]) -> CodeProposal:
        system_prompt = (
            "You are CommitFlow, an autonomous software engineering assistant that produces real, "
            "production-grade code, documentation, and unit tests to maintain authentic developer habits.\n"
            "STRICT RULES:\n"
            "1. Output MUST be a valid JSON object matching the requested schema.\n"
            "2. Never generate empty changes, whitespace-only files, or fake commits.\n"
            "3. Only modify files within allowed directory boundaries.\n"
            "4. Provide meaningful implementations and corresponding test assertions.\n"
        )

        user_prompt = f"""
Repository: {repo_context.get('repo_name', 'project')}
Allowed Paths: {repo_context.get('allowed_paths', ['src/'])}
Repository Summary / Existing Files:
{json.dumps(repo_context.get('file_tree', []), indent=2)}

Task Instructions:
{instructions}

Return ONLY valid JSON matching this schema:
{{
  "summary": "Short 1-line summary",
  "commit_message": "feat(scope): conventional commit message",
  "pr_title": "Clean Pull Request Title",
  "pr_body": "Detailed Markdown description of changes and test approach",
  "files": [
    {{
      "path": "relative/path/to/file.ext",
      "change_type": "CREATE or MODIFY",
      "content": "Full file content"
    }}
  ]
}}
"""

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )

        raw_json = response.choices[0].message.content
        data = json.loads(raw_json)
        return CodeProposal(**data)
