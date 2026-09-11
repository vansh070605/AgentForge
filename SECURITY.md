# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| `main`  | ✅ Yes    |
| Others  | ❌ No     |

## Reporting a Vulnerability

**Do NOT file a public GitHub issue for security vulnerabilities.**

Report privately via [GitHub Security Advisories](https://github.com/vansh070605/AgentForge/security/advisories/new).

Include:
- Description of the vulnerability
- Steps to reproduce
- Affected component (`agentforge/sandbox/`, agent layer, API, etc.)
- Potential impact

You'll receive a response within **72 hours**.

## Scope

Areas of highest security sensitivity:
- **`agentforge/sandbox/`** — Docker isolation boundary, resource limits, network policy
- **`agentforge/agents/execution.py`** — tool permission gates, no direct subprocess access
- **`agentforge/workspace/manager.py`** — path traversal safeguards, env scrubbing
- **`.github/workflows/`** — CI secret handling

## Security Design

AgentForge's execution sandbox enforces:
- `--network none` — zero egress during task execution
- `--read-only` rootfs with `tmpfs /tmp`
- `--pids-limit 100`, `--memory 2g`, `--cpus 2`
- `--cap-drop ALL`, `--user nobody`, `--security-opt no-new-privileges`

Set `AGENTFORGE_SANDBOX_DRIVER=docker` in production.
