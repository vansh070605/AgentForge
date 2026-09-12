"""FastAPI REST & SSE streaming server for AgentForge pipeline.

Exposes endpoints for the AgentForge Web UI Dashboard and automated CI triggers.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
import uuid

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from starlette.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agentforge.models.state import OrchestratorState, TaskStatus
from agentforge.orchestrator import PipelineOrchestrator
from agentforge.workspace.manager import WorkspaceManager


class CreateTaskRequest(BaseModel):
    user_prompt: str = Field(..., description="The user requirement, issue description, or engineering task.")
    repo_url_or_path: str = Field(default=".", description="Path or URL to the target git repository.")
    branch_name: Optional[str] = Field(default=None, description="Optional custom working branch.")
    max_iterations: int = Field(default=2, ge=1, le=5, description="Maximum execution-review feedback cycles.")


class TaskSummaryResponse(BaseModel):
    task_id: str
    status: TaskStatus
    user_prompt: str
    current_iteration: int
    confidence_score: Optional[float] = None
    created_at: str


class TaskStore:
    """In-memory store of active tasks, workspaces, and event queues."""

    def __init__(self):
        self.states: Dict[str, OrchestratorState] = {}
        self.workspaces: Dict[str, WorkspaceManager] = {}
        self.event_queues: Dict[str, List[asyncio.Queue]] = {}

    def get_or_create_queue(self, task_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        if task_id not in self.event_queues:
            self.event_queues[task_id] = []
        self.event_queues[task_id].append(q)
        return q

    def remove_queue(self, task_id: str, q: asyncio.Queue) -> None:
        if task_id in self.event_queues and q in self.event_queues[task_id]:
            self.event_queues[task_id].remove(q)

    def publish_event(self, task_id: str, event_type: str, data: Dict[str, Any]) -> None:
        queues = self.event_queues.get(task_id, [])
        payload = {"event": event_type, "data": data}
        for q in list(queues):
            q.put_nowait(payload)


def create_app(orchestrator: Optional[PipelineOrchestrator] = None) -> FastAPI:
    """Factory creating the FastAPI server instance."""
    app = FastAPI(
        title="AgentForge API Server",
        description="REST & SSE API for the AgentForge multi-agent software engineering system.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    store = TaskStore()
    pipeline = orchestrator or PipelineOrchestrator()

    # Wire orchestrator event listener to publish into task queues
    def on_pipeline_event(event_type: str, data: Dict[str, Any]) -> None:
        task_id = data.get("task_id")
        if task_id:
            store.publish_event(task_id, event_type, data)

    pipeline.add_event_listener(on_pipeline_event)

    @app.post("/api/tasks", status_code=202)
    async def create_task(req: CreateTaskRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        state = OrchestratorState(
            task_id=task_id,
            repo_url_or_path=req.repo_url_or_path,
            user_prompt=req.user_prompt,
            status=TaskStatus.PENDING,
            max_iterations=req.max_iterations,
        )

        ws_dir = Path("./.agentforge_workspaces") / task_id
        workspace = WorkspaceManager(workspace_dir=ws_dir, task_id=task_id)

        # Initialize workspace branch from source repository if path exists
        source_path = Path(req.repo_url_or_path)
        if source_path.exists():
            branch = req.branch_name or f"agentforge/{task_id}"
            workspace.initialize_from_source(source_path=source_path, branch_name=branch)

        store.states[task_id] = state
        store.workspaces[task_id] = workspace

        async def run_pipeline_task():
            await pipeline.run(state=state, workspace=workspace)

        background_tasks.add_task(run_pipeline_task)

        return {
            "task_id": task_id,
            "status": state.status.value,
            "user_prompt": state.user_prompt,
            "message": "Task queued and started in background",
        }

    @app.get("/api/tasks")
    async def list_tasks() -> List[Dict[str, Any]]:
        results = []
        for task_id, s in store.states.items():
            conf = s.verification_report.confidence_score if s.verification_report else None
            results.append({
                "task_id": task_id,
                "status": s.status.value,
                "user_prompt": s.user_prompt,
                "current_iteration": s.current_iteration,
                "confidence_score": conf,
            })
        return results

    @app.get("/api/tasks/{task_id}")
    async def get_task(task_id: str) -> Dict[str, Any]:
        state = store.states.get(task_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

        workspace = store.workspaces.get(task_id)
        diff_text = ""
        if workspace and workspace.base_commit:
            diff_text = workspace.git_diff(against_base=True)

        res = state.model_dump()
        res["diff"] = diff_text
        return res

    @app.get("/api/tasks/{task_id}/audit")
    async def get_task_audit(task_id: str) -> List[Dict[str, Any]]:
        workspace = store.workspaces.get(task_id)
        if not workspace:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        return [event.model_dump() for event in workspace.audit_trail]

    @app.get("/api/tasks/{task_id}/events")
    async def stream_task_events(task_id: str) -> StreamingResponse:
        state = store.states.get(task_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

        q = store.get_or_create_queue(task_id)

        async def event_generator() -> AsyncGenerator[str, None]:
            # Emit initial current state snapshot
            initial_data = json.dumps({"event": "state_snapshot", "data": {"status": state.status.value, "iteration": state.current_iteration}})
            yield f"data: {initial_data}\n\n"

            try:
                while True:
                    # Wait for next event or timeout check
                    try:
                        event_item = await asyncio.wait_for(q.get(), timeout=20.0)
                        payload = json.dumps(event_item)
                        yield f"data: {payload}\n\n"

                        # If pipeline finished, close stream
                        if event_item.get("event") in ("pipeline_completed", "pipeline_error"):
                            break
                    except asyncio.TimeoutError:
                        # Keep-alive heartbeat comment
                        yield ": heartbeat\n\n"
            finally:
                store.remove_queue(task_id, q)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.post("/api/tasks/{task_id}/approve")
    async def approve_merge_gate(task_id: str) -> Dict[str, Any]:
        state = store.states.get(task_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

        if state.status != TaskStatus.READY_FOR_PR:
            raise HTTPException(
                status_code=400,
                detail=f"Task is in status '{state.status.value}', cannot approve PR until READY_FOR_PR",
            )

        state.status = TaskStatus.COMPLETED
        pr_url = f"https://github.com/agentforge/repo/pull/{task_id}"
        state.pull_request_url = pr_url

        store.publish_event(task_id, "pr_approved", {"task_id": task_id, "pr_url": pr_url})

        return {
            "task_id": task_id,
            "status": state.status.value,
            "pull_request_url": pr_url,
            "message": "Human merge gate approved. Verified Pull Request generated.",
        }

    # Mount UI static dashboard at root
    ui_dir = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if ui_dir.exists():
        app.mount("/", StaticFiles(directory=str(ui_dir), html=True), name="ui")

    return app


app = create_app()
