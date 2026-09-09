"""Deterministic code search tool across workspace files."""

from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

from agentforge.tools.base import BaseTool
from agentforge.workspace.manager import WorkspaceManager


class SearchMatch(BaseModel):
    file_path: str
    line_number: int
    line_content: str


class SearchCodeInput(BaseModel):
    query: str = Field(..., min_length=1, description="Text string to search for across files.")
    scope_directory: str = Field(default="", description="Optional directory to restrict search scope.")
    max_results: int = Field(default=50, ge=1, le=200, description="Maximum number of matches to return.")


class SearchCodeOutput(BaseModel):
    query: str
    matches: List[SearchMatch]
    total_matches: int
    truncated: bool


class SearchCodeTool(BaseTool):
    name = "search_code"
    description = "Searches for matching text in workspace files, returning file paths and line numbers."
    input_schema = SearchCodeInput
    output_schema = SearchCodeOutput

    def _is_binary_file(self, safe_path: Path) -> bool:
        """Heuristic check to detect binary files and avoid reading them."""
        try:
            with open(safe_path, "rb") as f:
                chunk = f.read(1024)
                return b"\x00" in chunk
        except Exception:
            return True

    def _run(self, input_data: SearchCodeInput, workspace: WorkspaceManager) -> SearchCodeOutput:
        if Path(input_data.scope_directory).is_absolute():
            raise ValueError(f"Absolute paths are forbidden: '{input_data.scope_directory}'")

        # Get candidates within the specified directory
        candidate_files = workspace.list_files(rel_dir=input_data.scope_directory)
        matches: List[SearchMatch] = []
        truncated = False

        query = input_data.query

        for rel_file in candidate_files:
            safe_path = workspace.resolve_safe_path(rel_file)
            if self._is_binary_file(safe_path):
                continue

            try:
                content = safe_path.read_text(encoding="utf-8", errors="ignore")
                for line_idx, line in enumerate(content.splitlines(), start=1):
                    if query in line:
                        matches.append(
                            SearchMatch(
                                file_path=rel_file,
                                line_number=line_idx,
                                line_content=line.strip()[:200],  # Truncate very long lines
                            )
                        )
                        if len(matches) >= input_data.max_results:
                            truncated = True
                            break
            except Exception:
                continue

            if truncated:
                break

        return SearchCodeOutput(
            query=query,
            matches=matches,
            total_matches=len(matches),
            truncated=truncated,
        )
