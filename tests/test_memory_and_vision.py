"""
Unit tests for JARVIS Phase 4: Vision & Screen Understanding and Long-Term Memory.
"""

import pytest
from pathlib import Path
from jarvis.memory.memory_manager import MemoryManager
from jarvis.tools.vision_tools import capture_screen_image, get_active_window_title, analyze_screen
from jarvis.brain.agent import JarvisAgent
from jarvis.tools.registry import execute_tool


@pytest.fixture
def temp_memory(tmp_path):
    db_file = tmp_path / "test_memory.db"
    return MemoryManager(db_path=db_file)


def test_memory_store_and_recall(temp_memory):
    # Store user fact
    reply = temp_memory.remember_fact("user_name", "Manish", category="personal")
    assert "Manish" in reply

    # Recall fact
    val = temp_memory.recall_fact("user_name")
    assert val == "Manish"

    # Search fact
    results = temp_memory.search_memory("Manish")
    assert len(results) >= 1
    assert results[0]["key"] == "user_name"

    # Prompt context generation
    ctx = temp_memory.get_context_for_prompt()
    assert "User Name: Manish" in ctx

    # Forget fact
    deleted = temp_memory.forget_fact("user_name")
    assert deleted is True
    assert temp_memory.recall_fact("user_name") is None


def test_memory_notes(temp_memory):
    reply = temp_memory.save_note("Project Spec", "Building JARVIS Mark VII HUD with vision.", tags="ai,hud")
    assert "Project Spec" in reply

    notes = temp_memory.list_notes()
    assert len(notes) >= 1
    assert notes[0]["title"] == "Project Spec"

    search_res = temp_memory.search_memory("Mark VII")
    assert len(search_res) >= 1
    assert search_res[0]["title"] == "Project Spec"


def test_vision_capture_and_active_window():
    title = get_active_window_title()
    assert isinstance(title, str)

    jpeg_bytes, act_title, w, h = capture_screen_image(max_dimension=640)
    assert jpeg_bytes is not None
    assert len(jpeg_bytes) > 0
    assert w > 0 and h > 0
    assert isinstance(act_title, str)


@pytest.mark.asyncio
async def test_vision_analyze_screen():
    report = await analyze_screen(query="What is on my screen?")
    assert isinstance(report, str)
    assert len(report) > 0


@pytest.mark.asyncio
async def test_agent_memory_and_vision_fastpath(monkeypatch, tmp_path):
    test_db = tmp_path / "agent_memory.db"
    test_mm = MemoryManager(db_path=test_db)
    monkeypatch.setattr("jarvis.memory.memory_manager.get_memory_manager", lambda: test_mm)
    monkeypatch.setattr("jarvis.tools.registry.get_memory_manager", lambda: test_mm)

    agent = JarvisAgent()

    # Fast-path: remember command
    rem_resp = await agent._handle_direct_os_command("Remember that my favorite code language is Python")
    assert rem_resp is not None
    assert "favorite code language" in rem_resp.lower() or "python" in rem_resp.lower()

    # Fast-path: recall command
    rec_resp = await agent._handle_direct_os_command("Recall memories")
    assert "python" in rec_resp.lower()

    # Fast-path: active window
    win_resp = await agent._handle_direct_os_command("What window is this")
    assert win_resp is not None
    assert "active foreground window is" in win_resp.lower()

    # Fast-path: screen inspection
    scr_resp = await agent._handle_direct_os_command("Inspect screen")
    assert scr_resp is not None
    assert len(scr_resp) > 0
