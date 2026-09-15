"""LLM-powered Review Inspector callable.

Implements the ``custom_inspector`` hook expected by ReviewAgent:
    Callable[[OrchestratorState, str], List[ReviewIssue]]

The LLM reviews the diff for logic/correctness issues that regex patterns
cannot catch. Its findings are appended to the deterministic checks already
performed by ReviewAgent. On any LLM failure an empty list is returned
(conservative — don't block approval due to LLM unavailability).
"""

from __future__ import annotations

import logging
from typing import List, Optional

from pydantic import BaseModel, Field

from agentforge.llm.base import LLMClient, ChatMessage
from agentforge.llm.prompts import REVIEWER_SYSTEM, REVIEWER_USER_TEMPLATE
from agentforge.models.review import ReviewIssue, SeverityLevel
from agentforge.models.state import OrchestratorState

logger = logging.getLogger(__name__)

# Diff size guard — very large diffs cause context overflow
MAX_DIFF_BYTES = 12_000


# ---------------------------------------------------------------------------
# Pydantic schema for the LLM's issue list output
# ---------------------------------------------------------------------------


class _LLMReviewIssue(BaseModel):
    file: str = "logic"
    line: Optional[int] = None
    severity: str = "medium"
    problem: str
    recommendation: str


class _LLMReviewReport(BaseModel):
    issues: List[_LLMReviewIssue] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# LLMReviewInspector
# ---------------------------------------------------------------------------


class LLMReviewInspector:
    """Callable that performs LLM-based code review on a diff.

    Usage (wire into ReviewAgent):
        from agentforge.llm import get_llm_client
        from agentforge.llm.agents.llm_reviewer import LLMReviewInspector
        from agentforge.agents.review import ReviewAgent

        llm = get_llm_client()
        agent = ReviewAgent(custom_inspector=LLMReviewInspector(llm))
    """

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    # ------------------------------------------------------------------
    # Public callable — matches ReviewAgent.custom_inspector signature
    # ------------------------------------------------------------------

    def __call__(
        self,
        state: OrchestratorState,
        diff_text: str,
    ) -> List[ReviewIssue]:
        """Synchronous wrapper over the async LLM call."""
        import asyncio

        if not diff_text or not diff_text.strip():
            logger.debug("LLMReviewInspector: empty diff, skipping LLM review")
            return []

        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(
                self._async_inspect(state, diff_text), loop
            )
            return future.result(timeout=90)
        except RuntimeError:
            return asyncio.run(self._async_inspect(state, diff_text))
        except Exception as exc:
            logger.warning(
                "LLMReviewInspector failed (%s), returning no additional issues: %s",
                type(exc).__name__,
                exc,
            )
            return []  # Conservative — don't block the pipeline

    # ------------------------------------------------------------------
    # Async implementation
    # ------------------------------------------------------------------

    async def _async_inspect(
        self,
        state: OrchestratorState,
        diff_text: str,
    ) -> List[ReviewIssue]:
        # Truncate very large diffs to avoid context overflow
        if len(diff_text) > MAX_DIFF_BYTES:
            diff_text = diff_text[:MAX_DIFF_BYTES] + "\n... (diff truncated)"

        spec = state.task_spec
        description = spec.description if spec else state.user_prompt or "(no description)"
        criteria_text = _format_criteria(spec.acceptance_criteria if spec else [])

        user_content = REVIEWER_USER_TEMPLATE.format(
            description=description,
            acceptance_criteria=criteria_text,
            diff_text=diff_text,
        )

        messages = [
            ChatMessage(role="system", content=REVIEWER_SYSTEM),
            ChatMessage(role="user", content=user_content),
            ChatMessage(
                role="user",
                content=(
                    'Respond with a JSON object with a single key "issues" containing the array. '
                    'Example: {"issues": [{"file": "src/auth.py", "line": 42, "severity": "HIGH", '
                    '"problem": "Off-by-one error in token expiry check.", '
                    '"recommendation": "Change > to >= on line 42."}]}'
                ),
            ),
        ]

        report: _LLMReviewReport = await self._llm.complete_with_json(
            messages=messages,
            schema=_LLMReviewReport,
            temperature=0.1,
        )

        issues = _convert_issues(report.issues)
        logger.info(
            "LLMReviewInspector found %d additional issue(s) in diff review",
            len(issues),
        )
        return issues


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _convert_issues(raw_issues: List[_LLMReviewIssue]) -> List[ReviewIssue]:
    """Convert LLM issue objects to ReviewIssue models with enum normalisation."""
    result: List[ReviewIssue] = []
    severity_map = {
        "critical": SeverityLevel.CRITICAL,
        "high": SeverityLevel.HIGH,
        "medium": SeverityLevel.MEDIUM,
        "low": SeverityLevel.LOW,
    }
    for raw in raw_issues:
        severity = severity_map.get(raw.severity.lower(), SeverityLevel.MEDIUM)
        result.append(ReviewIssue(
            file=raw.file or "logic",
            line=raw.line,
            severity=severity,
            problem=f"[LLM] {raw.problem}",
            recommendation=raw.recommendation,
        ))
    return result


def _format_criteria(criteria: list) -> str:
    if not criteria:
        return "(no formal acceptance criteria)"
    lines = [f"- {c.id}: {c.description}" for c in criteria]
    return "\n".join(lines)
