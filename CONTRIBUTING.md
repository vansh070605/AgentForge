# Contributing to AgentForge

Thank you for your interest in contributing! Here's how to get started.

## Getting Started

```bash
git clone https://github.com/vansh070605/AgentForge.git
cd AgentForge
pip install -e ".[dev]"
```

## Running Tests

```bash
# Unit tests (no Docker required)
pytest tests/ -m "not requires_docker"

# Docker integration tests (requires Docker daemon)
pytest tests/test_sandbox_docker.py -m requires_docker
```

## Submitting Changes

1. Fork the repo and create a branch: `git checkout -b feature/your-feature`
2. Make your changes and add tests
3. Run the test suite and ensure it passes
4. Open a Pull Request — fill in the PR template fully

## Security Changes

Any PR touching `agentforge/sandbox/` requires extra care:
- Document security implications in the PR template's **Sandbox Impact** section
- Verify `--network none`, `--read-only`, and resource limits remain intact
- Do not add `subprocess`, `os`, or `shutil` imports to `agentforge/agents/`

## Code Style

```bash
ruff check agentforge/ tests/
ruff format agentforge/ tests/
```

## Reporting Bugs

Use the [bug report template](https://github.com/vansh070605/AgentForge/issues/new?template=bug_report.yml).  
For security vulnerabilities, use [GitHub private advisories](https://github.com/vansh070605/AgentForge/security/advisories/new) — **never file a public issue**.
