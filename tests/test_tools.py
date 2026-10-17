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
