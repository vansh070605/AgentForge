# AgentForge Sandbox Base Image
#
# Minimal Python 3.12 Debian slim image for ephemeral task execution.
# This image is NOT installed with any packages beyond the Python stdlib —
# it relies on the workspace's own virtual environment or pre-installed deps.
#
# Security posture:
#   - Non-root user (nobody) enforced at runtime via DockerSandboxRuntime
#   - No shell history, no SSH keys, no credentials
#   - Read-only rootfs enforced by the runtime, not the image itself
#   - /tmp is mounted as tmpfs (noexec) by the runtime
#
# Build (only needed if you want to pre-cache the image locally):
#   docker build -t agentforge-sandbox:latest agentforge/sandbox/
#
# The DockerSandboxRuntime pulls python:3.12-slim directly from Docker Hub
# by default. Override with AGENTFORGE_SANDBOX_IMAGE env var (future).

FROM python:3.14-slim

LABEL org.opencontainers.image.title="AgentForge Sandbox"
LABEL org.opencontainers.image.description="Ephemeral Python execution sandbox for AgentForge task agents"
LABEL org.opencontainers.image.source="https://github.com/agentforge/agentforge"

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/workspace

# Working directory inside the container
WORKDIR /workspace

# Default to the nobody user — runtime enforces this via --user nobody,
# but set it here as a defence-in-depth measure.
USER nobody
