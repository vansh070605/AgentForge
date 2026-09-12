"""Tests verifying that the AgentForge Web UI Dashboard is served correctly."""

import asyncio
import re
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
            assert 'id="root"' in text

    asyncio.run(_test())


def test_ui_static_assets_served():
    """Verifies that CSS and JS assets are served with proper content types."""
    app = create_app()

    async def _test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.get("/")
            assert res.status_code == 200
            text = res.text

            # Find the JS and CSS assets in the HTML (e.g. src="/assets/index-DOhFG_8E.js")
            js_match = re.search(r'src="(/assets/[^"]+\.js)"', text)
            if js_match:
                js_path = js_match.group(1)
                js_res = await client.get(js_path)
                assert js_res.status_code == 200
                assert "text/javascript" in js_res.headers.get("content-type", "")

            css_match = re.search(r'href="(/assets/[^"]+\.css)"', text)
            if css_match:
                css_path = css_match.group(1)
                css_res = await client.get(css_path)
                assert css_res.status_code == 200
                assert "text/css" in css_res.headers.get("content-type", "")

    asyncio.run(_test())
