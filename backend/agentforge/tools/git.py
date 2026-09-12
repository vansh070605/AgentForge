"""Controlled Git tools: git_status, git_diff, git_commit."""

from typing import List, Optional
from pydantic import BaseModel, Field

from agentforge.tools.base import BaseTool
from agentforge.workspace.manager import WorkspaceManager


# --- 1. Git Status Tool ---

class GitStatusInput(BaseModel):
    pass


class GitStatusOutput(BaseModel):
    branch: Optional[str]
    base_commit: Optional[str]
    modified: List[str]
    untracked: List[str]
    staged: List[str]
    is_clean: bool


class GitStatusTool(BaseTool):
    name = "git_status"
    description = "Inspects the repository working tree status, tracking modified, untracked, and staged files."
    input_schema = GitStatusInput
    output_schema = GitStatusOutput

    def _run(self, input_data: GitStatusInput, workspace: WorkspaceManager) -> GitStatusOutput:
        status_dict = workspace.git_status()
        modified = status_dict.get("modified", [])
        untracked = status_dict.get("untracked", [])
        staged = status_dict.get("staged", [])
        is_clean = not (modified or untracked or staged)

        return GitStatusOutput(
            branch=workspace.current_branch,
            base_commit=workspace.base_commit,
            modified=modified,
            untracked=untracked,
            staged=staged,
            is_clean=is_clean,
        )


# --- 2. Git Diff Tool ---

class GitDiffInput(BaseModel):
    against_base: bool = Field(
        default=True,
        description=(
            "If True, produces a cumulative diff comparing base_commit against current state "
            "(including all commits made on the branch). If False, compares against HEAD."
        ),
    )


class GitDiffOutput(BaseModel):
    diff: str
    against_base: bool
    character_count: int
    is_empty: bool


class GitDiffTool(BaseTool):
    name = "git_diff"
    description = (
        "Generates a unified diff of changes. By default, compares against base_commit "
        "so all committed and uncommitted changes are visible to Review and Proof agents."
    )
    input_schema = GitDiffInput
    output_schema = GitDiffOutput

    def _run(self, input_data: GitDiffInput, workspace: WorkspaceManager) -> GitDiffOutput:
        diff_str = workspace.git_diff(against_base=input_data.against_base)
        return GitDiffOutput(
            diff=diff_str,
            against_base=input_data.against_base,
            character_count=len(diff_str),
            is_empty=len(diff_str.strip()) == 0,
        )


# --- 3. Git Commit Tool ---

class GitCommitInput(BaseModel):
    message: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Clear commit message explaining the change.",
    )


class GitCommitOutput(BaseModel):
    commit_hash: str
    message: str


class GitCommitTool(BaseTool):
    name = "git_commit"
    description = (
        "Stages modified and untracked files in the workspace and creates an atomic git commit. "
        "Dangerous operations (force push, reset, checkout, rebase) are strictly blocked."
    )
    input_schema = GitCommitInput
    output_schema = GitCommitOutput

    def _run(self, input_data: GitCommitInput, workspace: WorkspaceManager) -> GitCommitOutput:
        # Check if there are changes to commit
        status = workspace.git_status()
        if not (status["modified"] or status["untracked"] or status["staged"]):
            raise ValueError("No changes present in workspace to commit.")

        commit_hash = workspace.git_commit(message=input_data.message)
        return GitCommitOutput(
            commit_hash=commit_hash,
            message=input_data.message,
        )
