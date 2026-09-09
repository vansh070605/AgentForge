# AgentForge

An accountable, multi-agent software engineering system integrated with GitHub.

## Core Principle

> **The agent that performs the work should not be the sole authority that decides whether the work was successful.**

AgentForge implements a 4-agent pipeline with strict separation of concerns:
1. **Identity Agent**: Defines what *should* be done (Task Specification & Acceptance Criteria).
2. **Execution Agent**: Implements the changes, runs tests, and creates commits in a controlled branch.
3. **Review Agent**: Independently reviews diffs, tests, and security/architecture concerns.
4. **Proof-of-Work Agent**: Verifies objective evidence (git diffs, test exit codes, AST modifications) without trusting agent self-assertions.
5. **Human Merge Gate**: Produces a GitHub Pull Request with embedded verification proof; human approval is required to merge into `main`.
