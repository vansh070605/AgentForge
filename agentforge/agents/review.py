"""Deterministic Review Agent operating strictly through ToolRegistry.

SECURITY NOTICE:
This agent does NOT have direct filesystem, git, or subprocess access.
All interactions with the workspace and repository MUST be dispatched through
the ToolRegistry, ensuring that BaseTool permissions and validation gates
are strictly enforced.
"""

import ast
import re
from typing import Any, Callable, Dict, List, Optional, Set

from agentforge.agents.base import AgentMetadata, BaseAgent
from agentforge.models.audit import ActionType
from agentforge.models.review import (
    ReviewIssue,
    ReviewReport,
    ReviewStatus,
    SeverityLevel,
)
from agentforge.models.state import OrchestratorState
from agentforge.tools.base import ToolRegistry
from agentforge.tools import get_default_tool_registry
from agentforge.workspace.manager import WorkspaceManager


DEFAULT_REVIEW_TOOLS = [
    "read_file",
    "list_files",
    "search_code",
    "git_diff",
    "git_status",
]

# Patterns for secret leakage detection in diff additions
SECRET_PATTERNS = [
    (
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        SeverityLevel.CRITICAL,
        "Potential hardcoded AWS Access Key detected in code.",
        "Remove the AWS key and use environment variables or secret vaults.",
    ),
    (
        re.compile(r"\b(?:ghp_[A-Za-z0-9_]{36}|github_pat_[A-Za-z0-9_]{82})\b"),
        SeverityLevel.CRITICAL,
        "Potential hardcoded GitHub token detected in code.",
        "Revoke the token and inject via environment variables.",
    ),
    (
        re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|DSA|PGP)? PRIVATE KEY-----"),
        SeverityLevel.CRITICAL,
        "Hardcoded private key detected in code.",
        "Store private keys securely outside version control.",
    ),
    (
        re.compile(
            r"(?i)(?:api_key|apikey|secret_key|private_key|auth_token)\s*[:=]\s*['\"][A-Za-z0-9_\-\.]{16,}['\"]"
        ),
        SeverityLevel.HIGH,
        "Suspected hardcoded API key or secret token detected.",
        "Extract secret credentials into environment variables or secrets manager.",
    ),
]

# Patterns for dangerous function calls or code injection
DANGEROUS_CALL_PATTERNS = [
    (
        re.compile(r"\beval\s*\("),
        SeverityLevel.HIGH,
        "Use of eval() detected, which is susceptible to arbitrary code execution.",
        "Refactor to avoid eval(); use ast.literal_eval() or safe parsing.",
    ),
    (
        re.compile(r"\bexec\s*\("),
        SeverityLevel.HIGH,
        "Use of exec() detected, posing severe security and injection risks.",
        "Avoid dynamic code execution via exec().",
    ),
    (
        re.compile(r"\bos\.system\s*\("),
        SeverityLevel.HIGH,
        "Direct invocation of os.system() detected.",
        "Use controlled tools or safe subprocess with argument arrays instead of shell execution.",
    ),
    (
        re.compile(r"shell\s*=\s*True"),
        SeverityLevel.HIGH,
        "Subprocess execution with shell=True detected.",
        "Avoid shell=True to prevent command injection vulnerabilities.",
    ),
    (
        re.compile(r"\b(?:breakpoint|pdb\.set_trace)\s*\("),
        SeverityLevel.MEDIUM,
        "Debugging breakpoint left in code.",
        "Remove debugging breakpoint before committing or merging.",
    ),
]


class ReviewAgent(BaseAgent):
    """Independent Review Agent evaluating workspace diffs, tests, and security."""

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        metadata: Optional[AgentMetadata] = None,
        custom_inspector: Optional[Callable[[OrchestratorState, str], List[ReviewIssue]]] = None,
    ):
        if metadata is None:
            metadata = AgentMetadata(
                name="ReviewAgent",
                role="review",
                description="Independently inspects diffs, tests, security, and criteria satisfaction.",
                allowed_tools=list(DEFAULT_REVIEW_TOOLS),
            )
        super().__init__(metadata=metadata)
        self.tool_registry = tool_registry or get_default_tool_registry()
        self.custom_inspector = custom_inspector

    def _extract_added_lines_and_files(self, diff_text: str) -> Dict[str, List[tuple[int, str]]]:
        """Parses unified diff text into a mapping of file_path -> list of (line_no, line_content)."""
        file_diffs: Dict[str, List[tuple[int, str]]] = {}
        current_file: Optional[str] = None
        current_line_no = 0

        for raw_line in diff_text.splitlines():
            if raw_line.startswith("+++ b/"):
                current_file = raw_line[6:].strip()
                if current_file not in file_diffs:
                    file_diffs[current_file] = []
                current_line_no = 0
            elif raw_line.startswith("@@"):
                # Parse chunk header @@ -l,s +L,S @@
                match = re.search(r"\+(\d+)", raw_line)
                if match:
                    current_line_no = int(match.group(1))
            elif current_file is not None:
                if raw_line.startswith("+") and not raw_line.startswith("+++"):
                    line_content = raw_line[1:]
                    file_diffs[current_file].append((current_line_no, line_content))
                    current_line_no += 1
                elif raw_line.startswith(" "):
                    current_line_no += 1

        return file_diffs

    def _check_security_patterns(
        self, added_lines_by_file: Dict[str, List[tuple[int, str]]]
    ) -> List[ReviewIssue]:
        """Scans added diff lines for secrets, hardcoded keys, and dangerous invocations."""
        issues: List[ReviewIssue] = []

        for file_path, lines in added_lines_by_file.items():
            for line_no, content in lines:
                # Check for secrets
                for pattern, severity, problem, recommendation in SECRET_PATTERNS:
                    if pattern.search(content):
                        issues.append(
                            ReviewIssue(
                                file=file_path,
                                line=line_no if line_no > 0 else None,
                                severity=severity,
                                problem=problem,
                                recommendation=recommendation,
                            )
                        )

                # Check for dangerous calls
                for pattern, severity, problem, recommendation in DANGEROUS_CALL_PATTERNS:
                    if pattern.search(content):
                        issues.append(
                            ReviewIssue(
                                file=file_path,
                                line=line_no if line_no > 0 else None,
                                severity=severity,
                                problem=problem,
                                recommendation=recommendation,
                            )
                        )

        return issues

    def _check_python_syntax(
        self, file_paths: Set[str], workspace: WorkspaceManager, task_id: str
    ) -> List[ReviewIssue]:
        """Verifies that all modified or created Python files parse without SyntaxError."""
        issues: List[ReviewIssue] = []

        for path in file_paths:
            if not path.endswith(".py"):
                continue

            # Safely fetch file content via ToolRegistry
            res = self.tool_registry.execute(
                tool_name="read_file",
                raw_input={"file_path": path},
                workspace=workspace,
                agent=self,
                task_id=task_id,
            )

            if not res.success or not res.data:
                # File might have been deleted in git diff
                continue

            content = getattr(res.data, "content", "")
            try:
                ast.parse(content, filename=path)
            except SyntaxError as syn_err:
                issues.append(
                    ReviewIssue(
                        file=path,
                        line=syn_err.lineno,
                        severity=SeverityLevel.CRITICAL,
                        problem=f"Python syntax error: {syn_err.msg}",
                        recommendation="Fix Python syntax error so code can be parsed and executed.",
                    )
                )

        return issues

    def _check_target_file_boundaries(
        self, modified_files: Set[str], expected_files: Optional[List[str]]
    ) -> List[ReviewIssue]:
        """Ensures the changes respect target_files boundaries from TaskSpecification."""
        if not expected_files:
            return []

        issues: List[ReviewIssue] = []
        expected_set = set(expected_files)

        for file_path in modified_files:
            # Normalize path separators
            norm_path = file_path.replace("\\", "/")
            # Allow common test files or config if justified, otherwise report
            if norm_path not in expected_set:
                issues.append(
                    ReviewIssue(
                        file=file_path,
                        line=None,
                        severity=SeverityLevel.MEDIUM,
                        problem=f"File '{file_path}' was modified but is not listed in target_files for this task.",
                        recommendation="Verify if this modification is strictly necessary or revert files outside the task scope.",
                    )
                )

        return issues

    def _evaluate_execution_results(self, state: OrchestratorState) -> List[ReviewIssue]:
        """Evaluates whether the last execution run succeeded and whether tests passed."""
        issues: List[ReviewIssue] = []
        if not state.execution_results:
            return issues

        last_exec = state.execution_results[-1]

        if not last_exec.success:
            issues.append(
                ReviewIssue(
                    file="execution",
                    line=None,
                    severity=SeverityLevel.HIGH,
                    problem=f"Execution failed: {last_exec.error_message or 'Unknown execution failure'}",
                    recommendation="Review execution errors and rerun the execution plan.",
                )
            )

        if last_exec.test_results:
            test_res = last_exec.test_results
            if test_res.exit_code != 0:
                summary_err = test_res.stderr.strip() or test_res.stdout.strip()
                preview = summary_err[-300:] if len(summary_err) > 300 else summary_err
                issues.append(
                    ReviewIssue(
                        file="tests",
                        line=None,
                        severity=SeverityLevel.HIGH,
                        problem=f"Automated test command '{test_res.command}' failed with exit code {test_res.exit_code}. Details: {preview}",
                        recommendation="Fix failing tests before submitting code for review approval.",
                    )
                )

        return issues

    def _assess_criteria_satisfaction(
        self, state: OrchestratorState, issues: List[ReviewIssue]
    ) -> str:
        """Constructs an evaluation note for acceptance criteria."""
        if not state.task_spec or not state.task_spec.acceptance_criteria:
            return "No formal acceptance criteria specified in task."

        total = len(state.task_spec.acceptance_criteria)
        has_blocking_issues = any(
            issue.severity in (SeverityLevel.CRITICAL, SeverityLevel.HIGH) for issue in issues
        )

        if has_blocking_issues:
            return (
                f"Evaluation found {len(issues)} issue(s) preventing full satisfaction "
                f"of the {total} acceptance criteria."
            )

        return f"All {total} acceptance criteria appear addressed with no blocking critical/high issues detected."

    async def run(
        self,
        state: OrchestratorState,
        workspace: WorkspaceManager,
        **kwargs: Any,
    ) -> ReviewReport:
        """Independently evaluates changes in workspace against task specification.

        Args:
            state: Current pipeline orchestrator state.
            workspace: WorkspaceManager tracking the repository.
            **kwargs: Extra parameters (e.g. custom inspect rules).

        Returns:
            ReviewReport containing status (APPROVED/NEEDS_CHANGES) and issue list.
        """
        task_id = state.task_id
        iteration = state.current_iteration

        # Record agent started event
        start_event = self.create_audit_event(
            task_id=task_id,
            action_type=ActionType.AGENT_STARTED,
            description=f"ReviewAgent started evaluation for task '{task_id}' (iteration {iteration})",
        )
        workspace.record_audit(
            action_type=start_event.action_type,
            description=start_event.description,
            status=start_event.status,
            metadata=start_event.metadata,
            actor=start_event.actor,
        )

        all_issues: List[ReviewIssue] = []

        # 1. Fetch cumulative git diff against base_commit via ToolRegistry
        diff_res = self.tool_registry.execute(
            tool_name="git_diff",
            raw_input={"against_base": True},
            workspace=workspace,
            agent=self,
            task_id=task_id,
        )

        diff_text = getattr(diff_res.data, "diff", "") if diff_res.success and diff_res.data else ""
        added_lines_by_file = self._extract_added_lines_and_files(diff_text)
        modified_files = set(added_lines_by_file.keys())

        # Also incorporate modified files reported by execution if diff is empty
        if not modified_files and state.execution_results:
            last_exec = state.execution_results[-1]
            modified_files.update(last_exec.modified_files)

        # 2. Syntax check on all modified Python files
        syntax_issues = self._check_python_syntax(
            file_paths=modified_files,
            workspace=workspace,
            task_id=task_id,
        )
        all_issues.extend(syntax_issues)

        # 3. Security pattern checks on diff
        security_issues = self._check_security_patterns(added_lines_by_file)
        all_issues.extend(security_issues)

        # 4. Scope and boundary checks against target_files
        target_files = state.task_spec.target_files if state.task_spec else []
        boundary_issues = self._check_target_file_boundaries(
            modified_files=modified_files,
            expected_files=target_files,
        )
        all_issues.extend(boundary_issues)

        # 5. Execution & test results check
        execution_issues = self._evaluate_execution_results(state)
        all_issues.extend(execution_issues)

        # 6. Custom / pluggable inspector hook if provided
        if self.custom_inspector:
            try:
                custom_issues = self.custom_inspector(state, diff_text)
                if custom_issues:
                    all_issues.extend(custom_issues)
            except Exception as exc:
                all_issues.append(
                    ReviewIssue(
                        file="custom_inspector",
                        line=None,
                        severity=SeverityLevel.HIGH,
                        problem=f"Custom inspector raised error: {str(exc)}",
                        recommendation="Fix custom inspector exception.",
                    )
                )

        # 7. Criteria satisfaction assessment
        criteria_notes = self._assess_criteria_satisfaction(state, all_issues)

        # 8. Determine final verdict
        # CRITICAL or HIGH severity issues block approval
        has_blocking_defects = any(
            issue.severity in (SeverityLevel.CRITICAL, SeverityLevel.HIGH)
            for issue in all_issues
        )

        review_status = (
            ReviewStatus.NEEDS_CHANGES if has_blocking_defects else ReviewStatus.APPROVED
        )

        critical_count = sum(1 for i in all_issues if i.severity == SeverityLevel.CRITICAL)
        high_count = sum(1 for i in all_issues if i.severity == SeverityLevel.HIGH)
        medium_count = sum(1 for i in all_issues if i.severity == SeverityLevel.MEDIUM)
        low_count = sum(1 for i in all_issues if i.severity == SeverityLevel.LOW)

        if review_status == ReviewStatus.APPROVED:
            summary = (
                f"Review passed: Code changes approved with {len(all_issues)} non-blocking issue(s)."
            )
        else:
            summary = (
                f"Review rejected: Code changes require fixes. "
                f"Found {critical_count} critical, {high_count} high, "
                f"{medium_count} medium, {low_count} low issue(s)."
            )

        report = ReviewReport(
            task_id=task_id,
            iteration=iteration,
            status=review_status,
            summary=summary,
            issues=all_issues,
            criteria_satisfaction_notes=criteria_notes,
        )

        # Record review submission audit event
        review_event = self.create_audit_event(
            task_id=task_id,
            action_type=ActionType.REVIEW_SUBMITTED,
            description=f"ReviewReport submitted with status '{review_status.value}' ({len(all_issues)} issue(s))",
            status="success",
            metadata={
                "review_status": review_status.value,
                "issues_count": len(all_issues),
                "critical_count": critical_count,
                "high_count": high_count,
                "medium_count": medium_count,
                "low_count": low_count,
            },
        )
        workspace.record_audit(
            action_type=review_event.action_type,
            description=review_event.description,
            status=review_event.status,
            metadata=review_event.metadata,
            actor=review_event.actor,
        )

        # Record agent completed event
        end_event = self.create_audit_event(
            task_id=task_id,
            action_type=ActionType.AGENT_COMPLETED,
            description=f"ReviewAgent completed review with status '{review_status.value}'",
            status="success",
        )
        workspace.record_audit(
            action_type=end_event.action_type,
            description=end_event.description,
            status=end_event.status,
            metadata=end_event.metadata,
            actor=end_event.actor,
        )

        state.review_reports.append(report)
        return report
