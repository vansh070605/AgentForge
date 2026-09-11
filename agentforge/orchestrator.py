"""Pipeline Orchestrator coordinating the 4-agent software engineering lifecycle.

State Flow:
    PENDING -> SPECIFYING -> EXECUTING -> REVIEWING -> [FIXING -> EXECUTING] -> VERIFYING -> READY_FOR_PR / FAILED
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional

from agentforge.agents.execution import ExecutionAgent
from agentforge.agents.identity import IdentityAgent
from agentforge.agents.proof import ProofOfWorkAgent
from agentforge.agents.review import ReviewAgent
from agentforge.models.audit import ActionType
from agentforge.models.execution import ExecutionAction
from agentforge.models.review import ReviewStatus
from agentforge.models.state import OrchestratorState, TaskStatus
from agentforge.models.proof import VerificationStatus
from agentforge.tools.base import ToolRegistry
from agentforge.tools import get_default_tool_registry
from agentforge.workspace.manager import WorkspaceManager


EventListener = Callable[[str, Dict[str, Any]], Any]


class PipelineOrchestrator:
    """State machine coordinator managing Identity, Execution, Review, and Proof-of-Work agents."""

    def __init__(
        self,
        identity_agent: Optional[IdentityAgent] = None,
        execution_agent: Optional[ExecutionAgent] = None,
        review_agent: Optional[ReviewAgent] = None,
        proof_agent: Optional[ProofOfWorkAgent] = None,
        tool_registry: Optional[ToolRegistry] = None,
        execution_plan_generator: Optional[
            Callable[[OrchestratorState, WorkspaceManager], List[ExecutionAction]]
        ] = None,
    ):
        self.tool_registry = tool_registry or get_default_tool_registry()
        self.identity_agent = identity_agent or IdentityAgent(tool_registry=self.tool_registry)
        self.execution_agent = execution_agent or ExecutionAgent(tool_registry=self.tool_registry)
        self.review_agent = review_agent or ReviewAgent(tool_registry=self.tool_registry)
        self.proof_agent = proof_agent or ProofOfWorkAgent(tool_registry=self.tool_registry)
        self.execution_plan_generator = execution_plan_generator
        self._listeners: List[EventListener] = []

    def add_event_listener(self, listener: EventListener) -> None:
        """Subscribes an event listener to real-time pipeline transitions and agent outputs."""
        self._listeners.append(listener)

    def remove_event_listener(self, listener: EventListener) -> None:
        """Unsubscribes an event listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Dispatches an event to all registered listeners (sync or async)."""
        for listener in self._listeners:
            try:
                res = listener(event_type, data)
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception:
                pass

    def _default_plan_generator(
        self, state: OrchestratorState, workspace: WorkspaceManager
    ) -> List[ExecutionAction]:
        """Constructs a baseline execution plan based on task specification or review feedback."""
        actions: List[ExecutionAction] = []
        spec = state.task_spec

        if not spec:
            return actions

        # If in a fixing iteration, prioritize addressing review issues
        if state.status == TaskStatus.FIXING and state.review_reports:
            last_review = state.review_reports[-1]
            actions.append(
                ExecutionAction(
                    tool_name="git_status",
                    arguments={},
                    description="Inspect working tree status for fixing cycle",
                )
            )
            # Add action to review diff
            actions.append(
                ExecutionAction(
                    tool_name="git_diff",
                    arguments={"against_base": True},
                    description="Review current diff before applying fixes",
                )
            )
            if spec.suggested_test_command:
                actions.append(
                    ExecutionAction(
                        tool_name="run_tests",
                        arguments={"command": spec.suggested_test_command},
                        description="Run tests following fix modifications",
                    )
                )
            return actions

        # Initial execution plan
        actions.append(
            ExecutionAction(
                tool_name="list_files",
                arguments={"directory": ""},
                description="Explore existing workspace files",
            )
        )

        for target in spec.target_files:
            actions.append(
                ExecutionAction(
                    tool_name="read_file",
                    arguments={"file_path": target},
                    description=f"Read initial content of target file '{target}' if present",
                    critical=False,
                )
            )

        if spec.suggested_test_command:
            actions.append(
                ExecutionAction(
                    tool_name="run_tests",
                    arguments={"command": spec.suggested_test_command},
                    description=f"Execute test suite '{spec.suggested_test_command}'",
                    critical=False,
                )
            )

        return actions

    async def run(
        self, state: OrchestratorState, workspace: WorkspaceManager
    ) -> OrchestratorState:
        """Executes the full multi-agent engineering lifecycle end-to-end.

        Args:
            state: Pipeline orchestrator state.
            workspace: WorkspaceManager managing the working directory.

        Returns:
            Updated OrchestratorState with complete reports and final status.
        """
        task_id = state.task_id
        self._emit_event(
            "pipeline_started",
            {"task_id": task_id, "user_prompt": state.user_prompt, "status": state.status.value},
        )

        try:
            # -------------------------------------------------------------
            # Phase 1: Identity Specification
            # -------------------------------------------------------------
            if not state.task_spec:
                state.status = TaskStatus.SPECIFYING
                self._emit_event(
                    "state_transition",
                    {"task_id": task_id, "status": state.status.value, "iteration": state.current_iteration},
                )

                task_spec = await self.identity_agent.run(state=state, workspace=workspace)
                state.task_spec = task_spec
                self._emit_event(
                    "identity_completed",
                    {
                        "task_id": task_id,
                        "title": task_spec.title,
                        "target_files": task_spec.target_files,
                        "criteria_count": len(task_spec.acceptance_criteria),
                    },
                )

            # -------------------------------------------------------------
            # Phase 2: Execution & Review Iteration Loop
            # -------------------------------------------------------------
            while state.current_iteration <= state.max_iterations:
                iteration = state.current_iteration

                # Step 2A: Execution
                state.status = TaskStatus.EXECUTING
                self._emit_event(
                    "state_transition",
                    {"task_id": task_id, "status": state.status.value, "iteration": iteration},
                )

                if self.execution_plan_generator:
                    plan = self.execution_plan_generator(state, workspace)
                else:
                    plan = self._default_plan_generator(state, workspace)

                exec_result = await self.execution_agent.run(
                    state=state, workspace=workspace, plan=plan
                )
                self._emit_event(
                    "execution_completed",
                    {
                        "task_id": task_id,
                        "iteration": iteration,
                        "success": exec_result.success,
                        "modified_files": exec_result.modified_files,
                        "commits": exec_result.commits_created,
                    },
                )

                # Step 2B: Review
                state.status = TaskStatus.REVIEWING
                self._emit_event(
                    "state_transition",
                    {"task_id": task_id, "status": state.status.value, "iteration": iteration},
                )

                review_report = await self.review_agent.run(state=state, workspace=workspace)
                self._emit_event(
                    "review_completed",
                    {
                        "task_id": task_id,
                        "iteration": iteration,
                        "review_status": review_report.status.value,
                        "issues_count": len(review_report.issues),
                        "summary": review_report.summary,
                    },
                )

                # Check review verdict
                if review_report.status == ReviewStatus.APPROVED:
                    # Code review passed cleanly; break out to Proof-of-Work verification
                    break

                # If review needs changes and we have remaining iterations:
                if state.current_iteration < state.max_iterations:
                    state.status = TaskStatus.FIXING
                    state.current_iteration += 1
                    self._emit_event(
                        "state_transition",
                        {
                            "task_id": task_id,
                            "status": state.status.value,
                            "iteration": state.current_iteration,
                            "reason": "review_needs_changes",
                        },
                    )
                else:
                    # Max iterations reached, proceed to proof evaluation with current state
                    break

            # -------------------------------------------------------------
            # Phase 3: Zero-Trust Proof-of-Work Verification
            # -------------------------------------------------------------
            state.status = TaskStatus.VERIFYING
            self._emit_event(
                "state_transition",
                {"task_id": task_id, "status": state.status.value, "iteration": state.current_iteration},
            )

            verification_report = await self.proof_agent.run(
                state=state, workspace=workspace, execute_tests=True
            )
            state.verification_report = verification_report
            self._emit_event(
                "proof_completed",
                {
                    "task_id": task_id,
                    "verification_status": verification_report.status.value,
                    "confidence_score": verification_report.confidence_score,
                    "tests_passed": verification_report.tests_passed,
                    "tests_failed": verification_report.tests_failed,
                    "summary": verification_report.verification_summary,
                },
            )

            # -------------------------------------------------------------
            # Phase 4: Final Disposition
            # -------------------------------------------------------------
            if verification_report.status == VerificationStatus.VERIFIED:
                state.status = TaskStatus.READY_FOR_PR
            else:
                state.status = TaskStatus.FAILED
                state.error_message = verification_report.verification_summary

            self._emit_event(
                "pipeline_completed",
                {
                    "task_id": task_id,
                    "status": state.status.value,
                    "verified": verification_report.status == VerificationStatus.VERIFIED,
                    "confidence_score": verification_report.confidence_score,
                },
            )

        except Exception as exc:
            state.status = TaskStatus.FAILED
            state.error_message = f"Orchestrator error: {str(exc)}"
            self._emit_event(
                "pipeline_error",
                {"task_id": task_id, "error": str(exc), "status": state.status.value},
            )

        return state
