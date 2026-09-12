"""Tests verifying that the AgentForge Web UI Dashboard is served correctly."""

import asyncio
import httpx
import pytest

from agentforge.api import create_app


def test_ui_dashboard_index_served():
    """Verifies that GET / serves the HTML dashboard with expected title and elements."""
    app = create_app()

    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.get("/")
            assert res.status_code == 200
            assert "text/html" in res.headers.get("content-type", "")
            text = res.text
            assert "AgentForge" in text
            assert "Multi-Agent Verification Pipeline" in text
            assert "Zero-Trust Proof Certificate" in text
            assert "nodeIdentity" in text
            assert "nodeMergeGate" in text

    asyncio.run(_test())


def test_ui_static_assets_served():
    """Verifies that CSS and JS assets are served with proper content types."""
    app = create_app()

    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            css_res = await client.get("/style.css")
            assert css_res.status_code == 200
            assert "--bg-base" in css_res.text
            assert "--cyan" in css_res.text

            js_res = await client.get("/app.js")
            assert js_res.status_code == 200
            assert "AgentForge Web UI" in js_res.text
            assert "EventSource" in js_res.text

    asyncio.run(_test())
