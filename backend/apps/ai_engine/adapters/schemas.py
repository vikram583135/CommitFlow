from typing import List, Literal
from pydantic import BaseModel, Field

class ProposedFile(BaseModel):
    path: str = Field(description="Relative path of file within repository")
    change_type: Literal["CREATE", "MODIFY"] = Field(default="CREATE", description="Type of change")
    content: str = Field(description="Complete source code or documentation content")

class CodeProposal(BaseModel):
    summary: str = Field(description="Concise description of the generated work")
    commit_message: str = Field(description="Git commit message adhering to Conventional Commits")
    pr_title: str = Field(description="Pull request title")
    pr_body: str = Field(description="Detailed Pull request markdown description")
    files: List[ProposedFile] = Field(description="List of proposed file modifications or creations")
