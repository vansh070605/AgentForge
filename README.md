# AgentForge

**Autonomous AI agent pipeline for isolated, auditable code execution.**

AgentForge orchestrates a multi-agent pipeline — Identity → Execution → Review → Proof — where every build and test command runs inside an ephemeral Docker sandbox with zero-trust network isolation.

## Features

- **Ephemeral Docker sandbox** — `--network none`, read-only rootfs, PID/CPU/RAM limits
- **Zero-trust egress** — containers cannot reach the internet during task execution
- **Multi-agent pipeline** — IdentityAgent → ExecutionAgent → ReviewAgent → ProofAgent
- **FastAPI + SSE** — real-time streaming of agent events
- **Audit trail** — every tool call and workspace mutation is recorded
- **Driver toggle** — `AGENTFORGE_SANDBOX_DRIVER=docker|local` for CI vs. production

## Quick Start

```bash
pip install -e ".[dev]"

# Run without Docker (CI / local dev)
AGENTFORGE_SANDBOX_DRIVER=local pytest tests/ -m "not requires_docker"

# Run with Docker sandbox
AGENTFORGE_SANDBOX_DRIVER=docker uvicorn agentforge.api:app --reload
```

## Sandbox Security

| Constraint | Value |
|---|---|
| Network | `--network none` (complete isolation) |
| Filesystem | `--read-only` + `tmpfs /tmp` |
| CPU | 2 cores max |
| Memory | 2 GB max |
| PIDs | 100 max |
| User | `nobody` |
| Capabilities | `--cap-drop ALL` |

## Project Structure

```
agentforge/
├── agents/          # IdentityAgent, ExecutionAgent, ReviewAgent, ProofAgent
├── sandbox/         # SandboxRuntime interface + Docker/Local implementations
├── workspace/       # WorkspaceManager (git, file ops, command execution)
├── tools/           # ToolRegistry + allowlisted tools
├── models/          # Pydantic schemas
└── api.py           # FastAPI + SSE endpoints
```

## License

[MIT](LICENSE) © 2026 Vansh Agrawal
