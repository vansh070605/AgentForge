"""Deterministic Proof-of-Work Agent verifying objective evidence.

SECURITY NOTICE:
This agent does NOT have direct filesystem, git, or subprocess access.
All interactions with the workspace and repository MUST be dispatched through
the ToolRegistry, ensuring that BaseTool permissions and validation gates
are strictly enforced.
"""

import ast
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from agentforge.agents.base import AgentMetadata, BaseAgent
from agentforge.models.audit import ActionType
from agentforge.models.proof import (
    CriterionStatus,
    RequirementProof,
    VerificationReport,
    VerificationStatus,
)
from agentforge.models.state import OrchestratorState
from agentforge.tools.base import ToolRegistry
from agentforge.tools import get_default_tool_registry
from agentforge.workspace.manager import WorkspaceManager


DEFAULT_PROOF_TOOLS = [
    "read_file",
    "list_files",
    "search_code",
    "git_diff",
    "git_status",
    "run_tests",
]


class ProofOfWorkAgent(BaseAgent):
    """Independent zero-trust agent verifying objective implementation proof."""

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        metadata: Optional[AgentMetadata] = None,
    ):
        if metadata is None:
            metadata = AgentMetadata(
                name="ProofOfWorkAgent",
                role="proof",
                description="Verifies objective evidence (tests, AST symbols, diffs) without trusting self-claims.",
                allowed_tools=list(DEFAULT_PROOF_TOOLS),
            )
        super().__init__(metadata=metadata)
        self.tool_registry = tool_registry or get_default_tool_registry()

    def _parse_test_counts(self, stdout: str, stderr: str, exit_code: int) -> Tuple[int, int]:
        """Parses stdout/stderr from test runners (e.g. pytest, unittest) for passed/failed counts."""
        combined = f"{stdout}\n{stderr}"

        passed_match = re.search(r"(\d+)\s+passed", combined)
        failed_match = re.search(r"(\d+)\s+failed", combined)
        error_match = re.search(r"(\d+)\s+error", combined)

        passed = int(passed_match.group(1)) if passed_match else 0
        failed = int(failed_match.group(1)) if failed_match else 0
        if error_match:
            failed += int(error_match.group(1))

        # Fallback if pytest summary is not parsed but exit code is known
        if passed == 0 and failed == 0:
            if exit_code == 0 and ("passed" in combined.lower() or "ok" in combined.lower()):
                passed = 1
            elif exit_code != 0:
                failed = 1

        return passed, failed

    def _extract_ast_symbols(
        self, file_paths: Set[str], workspace: WorkspaceManager, task_id: str
    ) -> Dict[str, Set[str]]:
        """Reads Python files via ToolRegistry and extracts defined function, class, and method names."""
        symbols_by_file: Dict[str, Set[str]] = {}

        for path in file_paths:
            if not path.endswith(".py"):
                continue

            res = self.tool_registry.execute(
                tool_name="read_file",
                raw_input={"file_path": path},
                workspace=workspace,
                agent=self,
                task_id=task_id,
            )
            if not res.success or not res.data:
                continue

            content = getattr(res.data, "content", "")
            try:
                tree = ast.parse(content, filename=path)
            except SyntaxError:
                continue

            symbols: Set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.add(node.name)
                elif isinstance(node, ast.ClassDef):
                    symbols.add(node.name)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            symbols.add(target.id)

            symbols_by_file[path] = symbols

        return symbols_by_file

    def _extract_diff_hunks_by_file(self, diff_text: str) -> Dict[str, List[str]]:
        """Parses unified diff text into a mapping of file_path -> list of added lines."""
        file_additions: Dict[str, List[str]] = {}
        current_file: Optional[str] = None

        for line in diff_text.splitlines():
            if line.startswith("+++ b/"):
                current_file = line[6:].strip()
                if current_file not in file_additions:
                    file_additions[current_file] = []
            elif current_file is not None and line.startswith("+") and not line.startswith("+++"):
                file_additions[current_file].append(line[1:].strip())

        return file_additions

    async def run(
        self,
        state: OrchestratorState,
        workspace: WorkspaceManager,
        execute_tests: bool = True,
        **kwargs: Any,
    ) -> VerificationReport:
        """Executes the zero-trust proof-of-work verification on objective artifacts.

        Args:
            state: Pipeline orchestrator state.
            workspace: WorkspaceManager for the active branch.
            execute_tests: If True, independently executes tests using run_tests tool.
                          If False, inspects existing test results from ExecutionResult.
            **kwargs: Extra parameters.

        Returns:
            VerificationReport containing objective proofs and confidence score.
        """
        task_id = state.task_id

        # 1. Audit initiation
        start_event = self.create_audit_event(
            task_id=task_id,
            action_type=ActionType.AGENT_STARTED,
            description=f"ProofOfWorkAgent started zero-trust verification for task '{task_id}'",
        )
        workspace.record_audit(
            action_type=start_event.action_type,
            description=start_event.description,
            status=start_event.status,
            metadata=start_event.metadata,
            actor=start_event.actor,
        )

        task_spec = state.task_spec
        if not task_spec:
            report = VerificationReport(
                task_id=task_id,
                status=VerificationStatus.INDETERMINATE,
                confidence_score=0.0,
                verification_summary="Verification impossible: No TaskSpecification provided in state.",
            )
            state.verification_report = report
            return report

        # 2. Objective Git Diff Analysis
        diff_res = self.tool_registry.execute(
            tool_name="git_diff",
            raw_input={"against_base": True},
            workspace=workspace,
            agent=self,
            task_id=task_id,
        )
        diff_text = getattr(diff_res.data, "diff", "") if diff_res.success and diff_res.data else ""
        diff_additions = self._extract_diff_hunks_by_file(diff_text)
        modified_files = set(diff_additions.keys())

        # Check for unrelated/out-of-scope files
        expected_targets = set(p.replace("\\", "/") for p in task_spec.target_files)
        unrelated_files: List[str] = []
        for f in modified_files:
            norm_f = f.replace("\\", "/")
            if norm_f not in expected_targets:
                unrelated_files.append(f)
        unrelated_changes_detected = len(unrelated_files) > 0

        # 3. Independent Test Execution & Verification
        tests_passed = 0
        tests_failed = 0
        test_command = task_spec.suggested_test_command or "pytest"
        test_output_summary = ""

        if execute_tests:
            test_tool_res = self.tool_registry.execute(
                tool_name="run_tests",
                raw_input={"command": test_command},
                workspace=workspace,
                agent=self,
                task_id=task_id,
            )
            if test_tool_res.success and test_tool_res.data:
                cmd_data = test_tool_res.data
                stdout = getattr(cmd_data, "stdout", "")
                stderr = getattr(cmd_data, "stderr", "")
                exit_code = getattr(cmd_data, "exit_code", -1)
                tests_passed, tests_failed = self._parse_test_counts(stdout, stderr, exit_code)
                test_output_summary = f"Test command '{test_command}' exited with code {exit_code} ({tests_passed} passed, {tests_failed} failed)."
            else:
                tests_failed = 1
                test_output_summary = f"Execution of test command '{test_command}' failed: {test_tool_res.error}"
        else:
            # Fallback to test results in execution_results if test execution skipped
            if state.execution_results and state.execution_results[-1].test_results:
                tr = state.execution_results[-1].test_results
                tests_passed, tests_failed = self._parse_test_counts(tr.stdout, tr.stderr, tr.exit_code)
                test_output_summary = f"Evaluated existing test results: {tests_passed} passed, {tests_failed} failed (exit code {tr.exit_code})."
            else:
                test_output_summary = "No test execution run or results found in execution history."

        # 4. AST Symbol Extraction
        ast_symbols_by_file = self._extract_ast_symbols(modified_files, workspace, task_id)

        # 5. Criterion-by-Criterion Proof Generation
        requirements: List[RequirementProof] = []
        satisfied_criteria_count = 0

        for criterion in task_spec.acceptance_criteria:
            evidence_items: List[str] = []
            criterion_text_lower = criterion.description.lower()

            # A. Check for AST symbols in modified files matching words in criterion
            matched_ast_symbols = []
            for file_path, symbols in ast_symbols_by_file.items():
                for symbol in symbols:
                    # Match if symbol name or function appears in criterion text
                    if symbol.lower() in criterion_text_lower:
                        matched_ast_symbols.append((symbol, file_path))

            if matched_ast_symbols:
                for sym, file_path in matched_ast_symbols:
                    evidence_items.append(f"AST node verified: Symbol '{sym}' exists in '{file_path}'")

            # B. Check for diff additions in files
            stop_words = {
                "the", "this", "that", "defines", "function", "returning", "returns",
                "with", "from", "should", "must", "when", "into", "file", "files",
                "service", "test", "tests", "unit", "code"
            }
            # Extract distinct identifiers from criterion description
            criterion_identifiers = [
                w for w in re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b", criterion_text_lower)
                if w not in stop_words
            ]

            for file_path, lines in diff_additions.items():
                for line in lines:
                    line_lower = line.lower()
                    for ident in criterion_identifiers:
                        if ident in line_lower:
                            snippet = line[:80] + ("..." if len(line) > 80 else "")
                            evidence_items.append(f"Diff evidence in '{file_path}': +{snippet}")
                            break

            # C. Check test results if criterion demands testing
            requires_test = any(
                term in criterion.verification_method.lower() for term in ["test", "unit_test"]
            )
            test_verified = False
            if requires_test:
                if tests_passed > 0 and tests_failed == 0:
                    evidence_items.append(
                        f"Automated test verification passed ({tests_passed} test(s) succeeded)"
                    )
                    test_verified = True

            # Determine criterion status based on objective evidence
            if requires_test and not test_verified:
                crit_status = CriterionStatus.UNMET
                crit_notes = (
                    f"Automated test verification failed or missing "
                    f"({tests_passed} passed, {tests_failed} failed)."
                )
            elif evidence_items and (not requires_test or test_verified):
                crit_status = CriterionStatus.SATISFIED
                crit_notes = f"Verified with {len(evidence_items)} objective evidence item(s)."
                satisfied_criteria_count += 1
            elif evidence_items:
                crit_status = CriterionStatus.PARTIAL
                crit_notes = "Partial evidence found, but full verification criteria unmet."
            else:
                crit_status = CriterionStatus.UNMET
                crit_notes = "No objective diff, AST, or test evidence found."

            requirements.append(
                RequirementProof(
                    criterion_id=criterion.id,
                    description=criterion.description,
                    status=crit_status,
                    evidence_items=evidence_items,
                    notes=crit_notes,
                )
            )

        # 6. Confidence Score Calculation & Verdict Synthesis
        total_criteria = len(task_spec.acceptance_criteria)
        if total_criteria > 0:
            criteria_ratio = satisfied_criteria_count / total_criteria
        else:
            criteria_ratio = 1.0 if (tests_passed > 0 and tests_failed == 0) else 0.5

        # Deduct penalties for objective failures
        confidence = criteria_ratio
        if tests_failed > 0:
            confidence = max(0.0, confidence - 0.5)
        if unrelated_changes_detected:
            confidence = max(0.0, confidence - 0.2)

        confidence_score = round(max(0.0, min(1.0, confidence)), 2)

        # Status decision
        if tests_failed > 0 or any(r.status == CriterionStatus.UNMET for r in requirements):
            verdict_status = VerificationStatus.REJECTED
        elif confidence_score >= 0.8 and all(r.status == CriterionStatus.SATISFIED for r in requirements):
            verdict_status = VerificationStatus.VERIFIED
        else:
            verdict_status = VerificationStatus.INDETERMINATE

        summary = (
            f"Verification verdict: {verdict_status.value.upper()} "
            f"(Confidence: {confidence_score * 100:.0f}%). "
            f"{satisfied_criteria_count}/{total_criteria} criteria satisfied. "
            f"Tests: {tests_passed} passed, {tests_failed} failed. "
            f"{'Unrelated file modifications detected: ' + ', '.join(unrelated_files) if unrelated_changes_detected else 'No unrelated changes detected.'} "
            f"{test_output_summary}"
        )

        report = VerificationReport(
            task_id=task_id,
            status=verdict_status,
            confidence_score=confidence_score,
            requirements=requirements,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            unrelated_changes_detected=unrelated_changes_detected,
            unrelated_files=unrelated_files,
            verification_summary=summary,
        )

        # 7. Audit Logging & State Update
        proof_event = self.create_audit_event(
            task_id=task_id,
            action_type=ActionType.PROOF_EVALUATED,
            description=f"ProofOfWork report produced: status '{verdict_status.value}', confidence {confidence_score}",
            status="success",
            metadata={
                "verification_status": verdict_status.value,
                "confidence_score": confidence_score,
                "tests_passed": tests_passed,
                "tests_failed": tests_failed,
                "unrelated_changes": unrelated_changes_detected,
            },
        )
        workspace.record_audit(
            action_type=proof_event.action_type,
            description=proof_event.description,
            status=proof_event.status,
            metadata=proof_event.metadata,
            actor=proof_event.actor,
        )

        end_event = self.create_audit_event(
            task_id=task_id,
            action_type=ActionType.AGENT_COMPLETED,
            description=f"ProofOfWorkAgent completed with status '{verdict_status.value}'",
            status="success",
        )
        workspace.record_audit(
            action_type=end_event.action_type,
            description=end_event.description,
            status=end_event.status,
            metadata=end_event.metadata,
            actor=end_event.actor,
        )

        state.verification_report = report
        return report
