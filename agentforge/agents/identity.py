"""Deterministic Identity Agent translating user requests into verifiable specifications.

SECURITY NOTICE:
This agent does NOT have direct filesystem, git, or subprocess access.
All interactions with the workspace and repository MUST be dispatched through
the ToolRegistry, ensuring that BaseTool permissions and validation gates
are strictly enforced.
"""

import re
from typing import Any, Callable, Dict, List, Optional, Set

from agentforge.agents.base import AgentMetadata, BaseAgent
from agentforge.models.audit import ActionType
from agentforge.models.state import OrchestratorState, TaskStatus
from agentforge.models.task import AcceptanceCriterion, TaskSpecification
from agentforge.tools.base import ToolRegistry
from agentforge.tools import get_default_tool_registry
from agentforge.workspace.manager import WorkspaceManager


DEFAULT_IDENTITY_TOOLS = [
    "read_file",
    "list_files",
    "search_code",
]


class IdentityAgent(BaseAgent):
    """Translates user requests into formal TaskSpecification with verifiable acceptance criteria."""

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        metadata: Optional[AgentMetadata] = None,
        custom_generator: Optional[
            Callable[[OrchestratorState, WorkspaceManager], TaskSpecification]
        ] = None,
    ):
        if metadata is None:
            metadata = AgentMetadata(
                name="IdentityAgent",
                role="identity",
                description="Translates user prompts into structured specifications and acceptance criteria.",
                allowed_tools=list(DEFAULT_IDENTITY_TOOLS),
            )
        super().__init__(metadata=metadata)
        self.tool_registry = tool_registry or get_default_tool_registry()
        self.custom_generator = custom_generator

    def _discover_repository_layout(
        self, workspace: WorkspaceManager, task_id: str
    ) -> Dict[str, Any]:
        """Lists files and locates existing source and test files in the workspace."""
        res = self.tool_registry.execute(
            tool_name="list_files",
            raw_input={"directory": ""},
            workspace=workspace,
            agent=self,
            task_id=task_id,
        )

        all_files: List[str] = []
        if res.success and res.data:
            files_data = getattr(res.data, "files", [])
            for item in files_data:
                if isinstance(item, str) and item:
                    all_files.append(item)
                elif isinstance(item, dict) and item.get("path"):
                    all_files.append(item["path"])
                elif hasattr(item, "path") and getattr(item, "path"):
                    all_files.append(getattr(item, "path"))

        source_files = [
            f for f in all_files if f.endswith(".py") and not f.startswith("tests/") and "test" not in f
        ]
        test_files = [f for f in all_files if "test" in f and f.endswith(".py")]

        # Check for pytest or test configuration
        has_pyproject = any("pyproject.toml" in f for f in all_files)
        has_setup = any("setup.cfg" in f or "setup.py" in f for f in all_files)

        return {
            "all_files": all_files,
            "source_files": source_files,
            "test_files": test_files,
            "has_pyproject": has_pyproject,
            "has_setup": has_setup,
        }

    def _extract_target_files_from_prompt(
        self, prompt: str, repo_layout: Dict[str, Any]
    ) -> List[str]:
        """Identifies target files mentioned in the prompt or infers appropriate files."""
        # Find explicit filenames matching path patterns in prompt
        file_candidates = set(re.findall(r"[\w\./\-]+\.py", prompt))

        # Check existing repo source files mentioned in prompt
        for src in repo_layout.get("source_files", []):
            base_name = src.split("/")[-1]
            if base_name in prompt or src in prompt:
                file_candidates.add(src)

        # Check test files
        for tst in repo_layout.get("test_files", []):
            base_name = tst.split("/")[-1]
            if base_name in prompt or tst in prompt:
                file_candidates.add(tst)

        # If no explicit files found, pick primary source file if available
        if not file_candidates and repo_layout.get("source_files"):
            file_candidates.add(repo_layout["source_files"][0])

        # Always include or suggest a corresponding test file if tests directory exists
        test_targets = [f for f in file_candidates if "test" in f]
        if not test_targets and file_candidates:
            # Pair each source file with a likely test file
            for src in list(file_candidates):
                name = src.split("/")[-1]
                paired_test = f"tests/test_{name}"
                file_candidates.add(paired_test)

        return sorted(list(file_candidates))

    def _synthesize_criteria(
        self, prompt: str, target_files: List[str]
    ) -> List[AcceptanceCriterion]:
        """Generates clear, verifiable acceptance criteria based on user intent."""
        criteria: List[AcceptanceCriterion] = []
        criterion_idx = 1

        # Look for explicit function/class mentions (e.g. `def ping()`, `health()`, `class User`)
        symbol_matches = re.findall(r"\b(?:function|def|endpoint|method|class)\s+([a-zA-Z_][a-zA-Z0-9_]*)", prompt, re.IGNORECASE)
        call_matches = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\(\)", prompt)
        extracted_symbols = set(symbol_matches + call_matches)

        for sym in sorted(list(extracted_symbols)):
            criteria.append(
                AcceptanceCriterion(
                    id=f"AC-{criterion_idx}",
                    description=f"Implement and export symbol '{sym}' satisfying the requirement specifications.",
                    verification_method="code_inspection",
                )
            )
            criterion_idx += 1

        # Automated test verification criterion
        has_test_target = any("test" in f for f in target_files)
        if has_test_target or "test" in prompt.lower():
            criteria.append(
                AcceptanceCriterion(
                    id=f"AC-{criterion_idx}",
                    description="Provide comprehensive automated tests verifying positive and negative execution paths.",
                    verification_method="unit_test",
                )
            )
            criterion_idx += 1

        # General correctness criterion if none were extracted from symbols
        if len(criteria) == 0:
            criteria.append(
                AcceptanceCriterion(
                    id=f"AC-{criterion_idx}",
                    description=f"Fulfill primary user requirement: '{prompt.strip()}'.",
                    verification_method="unit_test",
                )
            )

        return criteria

    def _determine_test_command(
        self, target_files: List[str], repo_layout: Dict[str, Any]
    ) -> str:
        """Determines the most specific and appropriate test runner command."""
        test_files = [f for f in target_files if "test" in f and f.endswith(".py")]
        if test_files:
            return f"pytest {' '.join(test_files)}"
        if repo_layout.get("test_files"):
            return f"pytest {' '.join(repo_layout['test_files'][:2])}"
        return "pytest"

    def _determine_constraints(self, prompt: str, target_files: List[str]) -> List[str]:
        """Establishes safety, architectural, and least-privilege constraints."""
        constraints = [
            f"All changes must be strictly restricted to the specified target_files: {', '.join(target_files)}.",
            "Do not modify public APIs or remove existing functions without explicit instructions.",
            "Ensure all automated tests exit with status code 0.",
        ]
        if "backward" in prompt.lower() or "compatibility" in prompt.lower():
            constraints.append("Maintain strict backward compatibility with existing callers.")
        return constraints

    async def run(
        self,
        state: OrchestratorState,
        workspace: WorkspaceManager,
        **kwargs: Any,
    ) -> TaskSpecification:
        """Generates a TaskSpecification from user prompt and workspace context.

        Args:
            state: Pipeline orchestrator state containing user_prompt and task_id.
            workspace: WorkspaceManager for repository inspection.
            **kwargs: Extra parameters.

        Returns:
            Structured TaskSpecification with acceptance criteria.
        """
        task_id = state.task_id

        # 1. Audit start
        start_event = self.create_audit_event(
            task_id=task_id,
            action_type=ActionType.AGENT_STARTED,
            description=f"IdentityAgent started requirement analysis for task '{task_id}'",
        )
        workspace.record_audit(
            action_type=start_event.action_type,
            description=start_event.description,
            status=start_event.status,
            metadata=start_event.metadata,
            actor=start_event.actor,
        )

        # 2. Custom generator hook
        if self.custom_generator:
            spec = self.custom_generator(state, workspace)
            state.task_spec = spec
            state.status = TaskStatus.SPECIFYING
            return spec

        # 3. Explore workspace layout
        repo_layout = self._discover_repository_layout(workspace, task_id)

        prompt = state.user_prompt or "Implement requested functionality"

        # 4. Extract title and description
        clean_prompt = prompt.strip()
        first_line = clean_prompt.splitlines()[0]
        title = first_line[:80] if len(first_line) > 80 else first_line

        # 5. Extract target files
        target_files = self._extract_target_files_from_prompt(clean_prompt, repo_layout)

        # 6. Extract verifiable acceptance criteria
        acceptance_criteria = self._synthesize_criteria(clean_prompt, target_files)

        # 7. Identify test command & constraints
        test_command = self._determine_test_command(target_files, repo_layout)
        constraints = self._determine_constraints(clean_prompt, target_files)

        spec = TaskSpecification(
            task_id=task_id,
            title=title,
            description=clean_prompt,
            target_files=target_files,
            acceptance_criteria=acceptance_criteria,
            suggested_test_command=test_command,
            constraints=constraints,
        )

        # 8. Audit completion & update state
        end_event = self.create_audit_event(
            task_id=task_id,
            action_type=ActionType.AGENT_COMPLETED,
            description=f"IdentityAgent finalized TaskSpecification with {len(acceptance_criteria)} criteria",
            status="success",
            metadata={
                "criteria_count": len(acceptance_criteria),
                "target_files": target_files,
                "suggested_test_command": test_command,
            },
        )
        workspace.record_audit(
            action_type=end_event.action_type,
            description=end_event.description,
            status=end_event.status,
            metadata=end_event.metadata,
            actor=end_event.actor,
        )

        state.task_spec = spec
        state.status = TaskStatus.SPECIFYING
        return spec
