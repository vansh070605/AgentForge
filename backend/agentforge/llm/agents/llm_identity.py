"""LLM-powered Identity Agent callable.

Implements the ``custom_generator`` hook expected by IdentityAgent:
    Callable[[OrchestratorState, WorkspaceManager], TaskSpecification]

When an LLMClient is available, this reads the workspace file layout, sends
the user prompt + context to the LLM, and returns a richly structured
TaskSpecification. On any LLM failure it falls back to the IdentityAgent's
built-in heuristic generator so the pipeline never hard-fails.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from agentforge.llm.base import LLMClient, LLMError
from agentforge.llm.prompts import IDENTITY_SYSTEM, IDENTITY_USER_TEMPLATE
from agentforge.llm.base import ChatMessage
from agentforge.models.state import OrchestratorState
from agentforge.models.task import AcceptanceCriterion, TaskSpecification
from agentforge.workspace.manager import WorkspaceManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schema the LLM must output (mirrors TaskSpecification fields)
# ---------------------------------------------------------------------------


class _LLMAcceptanceCriterion(BaseModel):
    id: str
    description: str
    verification_method: str = "unit_test"


class _LLMTaskSpec(BaseModel):
    title: str = Field(..., max_length=120)
    description: str
    target_files: List[str] = Field(default_factory=list)
    acceptance_criteria: List[_LLMAcceptanceCriterion] = Field(default_factory=list)
    suggested_test_command: Optional[str] = None
    constraints: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# LLMIdentityGenerator
# ---------------------------------------------------------------------------


class LLMIdentityGenerator:
    """Callable that generates TaskSpecification using an LLM.

    Usage (wire into IdentityAgent):
        from agentforge.llm import get_llm_client
        from agentforge.llm.agents.llm_identity import LLMIdentityGenerator
        from agentforge.agents.identity import IdentityAgent

        llm = get_llm_client()
        agent = IdentityAgent(custom_generator=LLMIdentityGenerator(llm))
    """

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    # ------------------------------------------------------------------
    # Public callable — matches IdentityAgent.custom_generator signature
    # ------------------------------------------------------------------

    def __call__(
        self,
        state: OrchestratorState,
        workspace: WorkspaceManager,
    ) -> TaskSpecification:
        """Synchronous wrapper — runs the async LLM call.

        When called from within an already-running async context (the orchestrator's
        event loop), we schedule the coroutine via run_coroutine_threadsafe in a
        separate thread.  Outside of an async context, asyncio.run() is used.
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            # We're inside a running event loop — schedule on it from a thread
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(
                self._async_generate(state, workspace), loop
            )
            return future.result(timeout=120)
        except RuntimeError:
            # No running event loop — safe to use asyncio.run()
            return asyncio.run(self._async_generate(state, workspace))
        except Exception as exc:
            logger.warning(
                "LLMIdentityGenerator failed (%s), falling back to heuristics: %s",
                type(exc).__name__,
                exc,
            )
            return self._heuristic_fallback(state, workspace)


    # ------------------------------------------------------------------
    # Async implementation
    # ------------------------------------------------------------------

    async def _async_generate(
        self,
        state: OrchestratorState,
        workspace: WorkspaceManager,
    ) -> TaskSpecification:
        file_listing = _get_file_listing(workspace, state.task_id)
        user_content = IDENTITY_USER_TEMPLATE.format(
            user_prompt=state.user_prompt or "(no prompt provided)",
            file_listing=file_listing,
        )
        messages = [
            ChatMessage(role="system", content=IDENTITY_SYSTEM),
            ChatMessage(role="user", content=user_content),
        ]

        llm_spec: _LLMTaskSpec = await self._llm.complete_with_json(
            messages=messages,
            schema=_LLMTaskSpec,
            temperature=0.1,
        )

        criteria = [
            AcceptanceCriterion(
                id=c.id,
                description=c.description,
                verification_method=c.verification_method,
            )
            for c in llm_spec.acceptance_criteria
        ]

        spec = TaskSpecification(
            task_id=state.task_id,
            title=llm_spec.title[:80],
            description=llm_spec.description,
            target_files=llm_spec.target_files,
            acceptance_criteria=criteria,
            suggested_test_command=llm_spec.suggested_test_command,
            constraints=llm_spec.constraints,
        )
        logger.info(
            "LLMIdentityGenerator produced spec '%s' with %d criteria, %d target files",
            spec.title,
            len(spec.acceptance_criteria),
            len(spec.target_files),
        )
        return spec

    def _heuristic_fallback(
        self,
        state: OrchestratorState,
        workspace: WorkspaceManager,
    ) -> TaskSpecification:
        """Minimal heuristic spec used when LLM fails."""
        prompt = state.user_prompt or "Implement requested functionality"
        return TaskSpecification(
            task_id=state.task_id,
            title=prompt[:80],
            description=prompt,
            target_files=[],
            acceptance_criteria=[
                AcceptanceCriterion(
                    id="AC-1",
                    description=f"Fulfill requirement: '{prompt[:120]}'.",
                    verification_method="unit_test",
                )
            ],
            suggested_test_command="pytest",
            constraints=["Do not modify files outside the stated scope."],
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_file_listing(workspace: WorkspaceManager, task_id: str) -> str:
    """Return a formatted string of workspace files (max 200 lines)."""
    try:
        files = workspace.list_files(rel_dir="")
        if not files:
            return "(workspace appears empty)"
        lines = [str(f) for f in files[:200]]
        listing = "\n".join(lines)
        if len(files) > 200:
            listing += f"\n... and {len(files) - 200} more files"
        return listing
    except Exception as exc:
        logger.debug("Could not list workspace files: %s", exc)
        return "(could not list workspace files)"
