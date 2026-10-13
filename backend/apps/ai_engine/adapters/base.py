from abc import ABC, abstractmethod
from typing import Dict, Any
from .schemas import CodeProposal

class BaseAIAdapter(ABC):
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name

    @abstractmethod
    def generate_changes(self, instructions: str, repo_context: Dict[str, Any]) -> CodeProposal:
        """
        Generate structured code proposals given user instructions and repository context.
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Verify API credentials with a minimal ping/completion request.
        """
        pass
