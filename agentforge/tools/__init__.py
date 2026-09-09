"""Controlled execution tools for AgentForge."""

from agentforge.tools.base import (
    BaseTool,
    ToolExecutionError,
    ToolPermissionError,
    ToolRegistry,
    ToolResult,
)
from agentforge.tools.execution import (
    RunCommandInput,
    RunCommandOutput,
    RunCommandTool,
)
from agentforge.tools.filesystem import (
    ListFilesInput,
    ListFilesOutput,
    ListFilesTool,
    ReadFileInput,
    ReadFileOutput,
    ReadFileTool,
    WriteFileInput,
    WriteFileOutput,
    WriteFileTool,
)
from agentforge.tools.git import (
    GitCommitInput,
    GitCommitOutput,
    GitCommitTool,
    GitDiffInput,
    GitDiffOutput,
    GitDiffTool,
    GitStatusInput,
    GitStatusOutput,
    GitStatusTool,
)
from agentforge.tools.search import (
    SearchCodeInput,
    SearchCodeOutput,
    SearchCodeTool,
    SearchMatch,
)


def get_default_tool_registry() -> ToolRegistry:
    """Instantiates and registers all standard controlled execution tools."""
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(ListFilesTool())
    registry.register(SearchCodeTool())
    registry.register(RunCommandTool())
    registry.register(GitStatusTool())
    registry.register(GitDiffTool())
    registry.register(GitCommitTool())
    return registry


__all__ = [
    "BaseTool",
    "ToolResult",
    "ToolPermissionError",
    "ToolExecutionError",
    "ToolRegistry",
    "get_default_tool_registry",
    "ReadFileInput",
    "ReadFileOutput",
    "ReadFileTool",
    "WriteFileInput",
    "WriteFileOutput",
    "WriteFileTool",
    "ListFilesInput",
    "ListFilesOutput",
    "ListFilesTool",
    "SearchCodeInput",
    "SearchCodeOutput",
    "SearchMatch",
    "SearchCodeTool",
    "RunCommandInput",
    "RunCommandOutput",
    "RunCommandTool",
    "GitStatusInput",
    "GitStatusOutput",
    "GitStatusTool",
    "GitDiffInput",
    "GitDiffOutput",
    "GitDiffTool",
    "GitCommitInput",
    "GitCommitOutput",
    "GitCommitTool",
]
