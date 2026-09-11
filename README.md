# AgentForge

> **Zero-Trust Multi-Agent Software Engineering Studio with Cryptographic Attestation & GitHub Integration**

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-REST%20%26%20SSE-009688.svg)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev/)
[![Tailwind CSS v4](https://img.shields.io/badge/Tailwind-v4-38B2AC.svg)](https://tailwindcss.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Core Principle

> ***"The agent that performs the work should not be the sole authority that decides whether the work was successful."***

Most autonomous coding systems allow a single model to write code, test its own work, and declare victory. **AgentForge** implements an adversarial, zero-trust verification pipeline with strict separation of concerns across four specialized autonomous agents and a mandatory human merge gate.

---

## Architecture Overview

```
[ User Objective / Prompt ]
             │
             ▼
┌───────────────────────────┐
│     01. SPECIFY           │
│    Identity Agent         │ ──▶ AST Context & Requirement Contract
└───────────────────────────┘
             │
             ▼
┌───────────────────────────┐
│     02. EXECUTE           │
│   Execution Agent         │ ──▶ Sandboxed Tool Runtime & Unified Git Diff
└───────────────────────────┘
             │
             ▼
┌───────────────────────────┐
│     03. INSPECT           │
│    Review Agent           │ ──▶ Adversarial AST Audit & Test Validation
└───────────────────────────┘
             │
             ▼
┌───────────────────────────┐
│     04. ATTEST            │
│  Proof-of-Work Agent      │ ──▶ Cryptographic SHA-256 State Seal & Rating
└───────────────────────────┘
             │
             ▼
┌───────────────────────────┐
│     05. GATE              │
│   Human Merge Gate        │ ──▶ Verified Pull Request & Human Sign-Off
└───────────────────────────┘
```

### The 4 Agents & Human Gate

1. **Identity Agent (`agentforge/agents/identity.py`)**
   - Ingests repository AST symbols and requirements to construct an immutable `TaskSpecification` contract.
   - Defines strict file boundaries, acceptance criteria, and whitelisted tools.

2. **Execution Agent (`agentforge/agents/execution.py`)**
   - Applies code modifications within a controlled, least-privilege tool execution environment.
   - Captures isolated git diff blocks and manages dedicated feature branches.

3. **Review Agent (`agentforge/agents/review.py`)**
   - Operates independently without trusting execution logs.
   - Runs automated pytest test suites, inspects AST modifications, and identifies policy or security regressions.

4. **Proof-of-Work Agent (`agentforge/agents/proof.py`)**
   - Synthesizes objective evidence (test exit codes, AST diff checksums, review reports).
   - Generates a tamper-evident **SHA-256 cryptographic attestation certificate** and a confidence rating score.

5. **Human Merge Gate (`agentforge/api.py`)**
   - Code cannot merge into `main` autonomously.
   - Generates an authorized GitHub Pull Request with embedded verification proofs, awaiting explicit human engineer approval.

---

## Web UI: Multi-Page Editorial Studio

AgentForge includes a React web studio built with **React 19**, **Vite**, **Tailwind CSS v4**, **Framer Motion**, and **Lenis** smooth scrolling:

- **Dual-Theme Studio Engine**: Seamless toggle between warm porcelain daylight (`#FAFAF8`) and an editorial carbon darkroom (`#0B0C10` canvas with `#12141C` muted obsidian cards). Zero harsh neon blowouts.
- **Global State Persistence**: SSE event streams, live diffs, and demo simulation loops persist in the background across navigation via `AgentForgeContext`.
- **Dedicated Route Views**:
  - `/` (**Overview & Mission Studio**): Architectural hero lockup, live 5-stage preview track, and task directive composer.
  - `/pipeline` (**Verification Pipeline**): Cinematic inspection view with oversized stage indices (`01`–`05`) and input/output invariant contracts.
  - `/diff` (**Code Review & Diff Workspace**): Daylight/carbon diff with line-by-line syntax coloring, addition/deletion metrics, and review findings.
  - `/attestation` (**Zero-Trust Proof Vault**): Museum exhibition gallery with circular SVG confidence rating gauge (**96%**), AST verified symbols cloud, and copyable SHA-256 seal.
  - `/telemetry` (**Live Telemetry Console**): Real-time telemetry paper with agent tag filters (`[ALL]`, `[ORCHESTRATOR]`, `[IDENTITY]`, `[EXECUTION]`, `[REVIEW]`, `[PROOF]`), search, and CSV/JSON log export.
  - **Human Merge Gate Modal**: Accessible globally across all views when clearance is ready.

---

## Quick Start

### 1. Prerequisites
- **Python**: 3.12+
- **Node.js**: v18+ & npm

### 2. Backend Installation & Run
```bash
# Clone repository
git clone https://github.com/vansh070605/AgentForge.git
cd AgentForge

# Install dependencies (or in a virtual environment)
pip install -e .

# Run the FastAPI REST & SSE backend
uvicorn agentforge.api:app --reload --port 8000
```
API Documentation will be available at: `http://localhost:8000/docs`.

### 3. Frontend Installation & Run
```bash
# In a new terminal tab
cd frontend

# Install packages
npm install

# Start Vite React Dev Server
npm run dev
```
Open **`http://localhost:5173/`** to explore the studio!

---

## REST & SSE API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `POST /api/tasks` | POST | Register and dispatch a multi-agent engineering task |
| `GET /api/tasks` | GET | List all active and historical tasks |
| `GET /api/tasks/{id}` | GET | Retrieve task state, unified diff, and proof certificate |
| `GET /api/tasks/{id}/events` | GET (SSE) | Real-time Server-Sent Events stream for logs and state transitions |
| `POST /api/tasks/{id}/approve` | POST | Human merge gate clearance: approves and generates GitHub PR |

---

## Running the Automated Test Suite

AgentForge maintains strict test coverage across all domain models, agents, workspace sandboxes, and UI endpoints:

```bash
# Run pytest across the entire workspace
pytest tests/
```
All **60 tests** execute and pass deterministically.

---

## Security & Sandboxing Policies
- **Least-Privilege Execution**: Tool invocations run within isolated workspace directories with path traversal safeguards.
- **AST Scope Bounds**: Files cannot have out-of-scope modifications without failing the Review Agent stage.
- **Cryptographic Attestation**: Tamper-evident SHA-256 proof hashes prevent author self-certification.

---

## License
MIT License. Created by [Vansh Agrawal](https://github.com/vansh070605).
