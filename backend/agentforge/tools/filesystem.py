"""Filesystem tools: read_file, write_file, list_files."""

from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

from agentforge.tools.base import BaseTool
from agentforge.workspace.manager import WorkspaceManager


# --- 1. Read File Tool ---

class ReadFileInput(BaseModel):
    file_path: str = Field(..., description="Relative path of the file to read within the repository.")


class ReadFileOutput(BaseModel):
    file_path: str
    content: str
    size_bytes: int


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Safely reads content of a file within the workspace."
    input_schema = ReadFileInput
    output_schema = ReadFileOutput

    def _run(self, input_data: ReadFileInput, workspace: WorkspaceManager) -> ReadFileOutput:
        # Prevent absolute path input
        if Path(input_data.file_path).is_absolute():
            raise ValueError(f"Absolute paths are forbidden: '{input_data.file_path}'")

        content = workspace.read_file(input_data.file_path)
        size_bytes = len(content.encode("utf-8"))
        return ReadFileOutput(
            file_path=input_data.file_path,
            content=content,
            size_bytes=size_bytes,
        )


# --- 2. Write File Tool ---

class WriteFileInput(BaseModel):
    file_path: str = Field(..., description="Relative path of the file to write within the repository.")
    content: str = Field(..., description="Full text content to write into the file.")


class WriteFileOutput(BaseModel):
    file_path: str
    bytes_written: int
    lines_written: int


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Safely writes content to a file in the workspace, creating parent directories as needed."
    input_schema = WriteFileInput
    output_schema = WriteFileOutput

    def _run(self, input_data: WriteFileInput, workspace: WorkspaceManager) -> WriteFileOutput:
        # Prevent absolute path input
        if Path(input_data.file_path).is_absolute():
            raise ValueError(f"Absolute paths are forbidden: '{input_data.file_path}'")

        workspace.write_file(input_data.file_path, input_data.content)
        bytes_written = len(input_data.content.encode("utf-8"))
        lines_written = len(input_data.content.splitlines())

        return WriteFileOutput(
            file_path=input_data.file_path,
            bytes_written=bytes_written,
            lines_written=lines_written,
        )


# --- 3. List Files Tool ---

class ListFilesInput(BaseModel):
    directory: str = Field(default="", description="Relative directory path to list. Defaults to root.")
    max_depth: int = Field(default=5, ge=1, le=10, description="Maximum directory traversal depth.")


class ListFilesOutput(BaseModel):
    directory: str
    files: List[str]
    total_count: int


class ListFilesTool(BaseTool):
    name = "list_files"
    description = "Lists files within the workspace up to a maximum depth, ignoring internal/build folders."
    input_schema = ListFilesInput
    output_schema = ListFilesOutput

    def _run(self, input_data: ListFilesInput, workspace: WorkspaceManager) -> ListFilesOutput:
        if Path(input_data.directory).is_absolute():
            raise ValueError(f"Absolute paths are forbidden: '{input_data.directory}'")

        files = workspace.list_files(rel_dir=input_data.directory, max_depth=input_data.max_depth)
        return ListFilesOutput(
            directory=input_data.directory or ".",
            files=files,
            total_count=len(files),
        )
