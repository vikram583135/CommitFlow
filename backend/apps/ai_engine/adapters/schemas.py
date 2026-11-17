from typing import List, Literal
from pydantic import BaseModel, Field, ConfigDict

class ProposedFile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    path: str = Field(min_length=1, max_length=500, description="Relative path of file within repository")
    change_type: Literal["CREATE", "MODIFY"] = Field(default="CREATE", description="Type of change")
    content: str = Field(max_length=250000, description="Complete source code or documentation content")

class CodeProposal(BaseModel):
    model_config = ConfigDict(extra='forbid')
    summary: str = Field(min_length=1, max_length=2000, description="Concise description of the generated work")
    commit_message: str = Field(min_length=1, max_length=255, description="Git commit message")
    pr_title: str = Field(min_length=1, max_length=255, description="Pull request title")
    pr_body: str = Field(max_length=20000, description="Pull request description")
    files: List[ProposedFile] = Field(min_length=1, max_length=10, description="Proposed changes")
