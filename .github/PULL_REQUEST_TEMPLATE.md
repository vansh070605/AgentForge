## Summary

<!-- Provide a concise description of what this PR does and why. -->

## Type of Change

- [ ] 🐛 Bug fix (non-breaking change that fixes an issue)
- [ ] ✨ New feature (non-breaking change that adds functionality)
- [ ] 💥 Breaking change (fix or feature that changes existing behaviour)
- [ ] 🔒 Security improvement (hardens sandbox, removes attack surface)
- [ ] ♻️ Refactor (code restructure, no functional change)
- [ ] 📦 Dependency update
- [ ] 🧪 Test-only change
- [ ] 📄 Documentation / configuration

## Sandbox Impact

> Does this PR modify the sandbox layer (`agentforge/sandbox/`)?

- [ ] **No** — no changes to sandbox code
- [ ] **Yes** — changes to `SandboxRuntime` interface or implementations
  - Describe the security implications:
  - Have you verified `--network none` still enforced?
  - Have you verified resource limits (CPU / RAM / PIDs) unchanged or intentionally adjusted?

## Test Coverage

<!-- Which test files cover these changes? -->

- [ ] `tests/test_sandbox_base.py` — sandbox unit tests
- [ ] `tests/test_sandbox_docker.py` — Docker integration tests (`requires_docker`)
- [ ] `tests/test_execution_agent.py` — ExecutionAgent tests
- [ ] `tests/test_orchestrator.py` — Pipeline orchestrator tests
- [ ] Other: ___

**New test count added:** ___

## Security Checklist

- [ ] `agentforge/agents/execution.py` has **no new** `subprocess`, `os`, or `open()` calls
- [ ] No new network egress paths introduced in `agentforge/sandbox/docker_runtime.py`
- [ ] No new capabilities granted to the Docker sandbox (`cap_drop=ALL` preserved)
- [ ] Sensitive environment variables are still scrubbed before subprocess execution
- [ ] Path traversal safeguards in `WorkspaceManager.resolve_safe_path()` are intact
- [ ] `AGENTFORGE_SANDBOX_DRIVER=local` still passes all 60+ existing tests

## Reviewer Notes

<!-- Anything the reviewer should pay special attention to, gotchas, or tradeoffs made. -->

## Related Issues

Closes #___
