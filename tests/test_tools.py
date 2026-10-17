"""
Tests for OS Automation & Agent Tools (Tier 3).
"""

import pytest
from jarvis.tools.sys_info import get_system_summary, get_top_processes
from jarvis.tools.os_control import volume_up, volume_down, volume_mute_toggle
from jarvis.tools.registry import execute_tool, TOOLS_SCHEMA, TOOL_DISPATCH


def test_system_summary():
    summary = get_system_summary()
    assert "cpu_percent" in summary
    assert "ram_percent" in summary
    assert "disk_percent" in summary
    assert "battery" in summary
    assert summary["ram_percent"] >= 0.0


def test_top_processes():
    procs = get_top_processes(limit=3)
    assert isinstance(procs, list)
    assert len(procs) <= 3
    if procs:
        p = procs[0]
        assert "pid" in p
        assert "name" in p


def test_tools_schema_validity():
    assert len(TOOLS_SCHEMA) >= 10
    names = [t["function"]["name"] for t in TOOLS_SCHEMA]
    assert "volume_up" in names
    assert "launch_application" in names
    assert "get_system_summary" in names
    assert "get_weather" in names
    # All schemas must map to a callable in TOOL_DISPATCH
    for name in names:
        assert name in TOOL_DISPATCH


@pytest.mark.asyncio
async def test_execute_tool_dispatch():
    res = await execute_tool("get_system_summary")
    assert isinstance(res, dict)
    assert "cpu_percent" in res

    unknown = await execute_tool("non_existent_tool")
    assert "not recognized" in unknown


@pytest.mark.asyncio
async def test_search_duckduckgo():
    res = await execute_tool("search_duckduckgo", {"query": "latest tech news", "max_results": 2})
    assert isinstance(res, str)
    assert len(res) > 0
    # Must not contain raw status code 202 error
    assert "status code 202" not in res.lower()
    assert "•" in res


def test_launch_application(monkeypatch):
    from jarvis.tools.os_control import launch_application
    import webbrowser
    import subprocess

    opened_urls = []
    opened_cmds = []

    monkeypatch.setattr(webbrowser, "open", lambda url: opened_urls.append(url))
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kwargs: opened_cmds.append(cmd))

    # Known web streaming service
    res_cr = launch_application("crunchyroll")
    assert "Opening Crunchyroll" in res_cr
    assert "https://www.crunchyroll.com" in opened_urls

    # Known desktop app
    res_chrome = launch_application("chrome")
    assert "Opening Chrome" in res_chrome
    assert any("chrome" in cmd for cmd in opened_cmds)

    # Calculator
    res_calc = launch_application("calculator")
    assert "Opening Calculator" in res_calc
    assert any("calc" in cmd for cmd in opened_cmds)

    # Generic website fallback
    res_duo = launch_application("duolingo")
    assert "Opening Duolingo" in res_duo
    assert any("duolingo.com" in u for u in opened_urls)


@pytest.mark.asyncio
async def test_agent_direct_launcher(monkeypatch):
    from jarvis.brain.agent import JarvisAgent
    import webbrowser
    import subprocess

    opened_urls = []
    opened_cmds = []
    monkeypatch.setattr(webbrowser, "open", lambda url: opened_urls.append(url))
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kwargs: opened_cmds.append(cmd))

    agent = JarvisAgent()

    # Test "Open Crunchyroll"
    rep1 = await agent._handle_direct_os_command("Open Crunchyroll")
    assert rep1 == "Opening Crunchyroll for you now, sir."
    assert "https://www.crunchyroll.com" in opened_urls

    # Test "Open Chrome."
    rep2 = await agent._handle_direct_os_command("Open Chrome.")
    assert rep2 == "Opening Chrome for you now, sir."

    # Test "Open calculator"
    rep3 = await agent._handle_direct_os_command("Open calculator")
    assert rep3 == "Opening Calculator for you now, sir."

    # Test "Open YouTube"
    rep4 = await agent._handle_direct_os_command("Open YouTube")
    assert rep4 == "Opening Youtube for you now, sir."
    assert "https://www.youtube.com" in opened_urls
