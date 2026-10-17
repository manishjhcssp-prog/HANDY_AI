"""
Unit tests for JARVIS Phase 5: Wake-Word Detection & Proactive Reminders.
"""

import pytest
import numpy as np
from pathlib import Path
from jarvis.audio.wake_word import WakeWordDetector, play_wake_chime
from jarvis.tools.reminders import ReminderScheduler, send_windows_notification
from jarvis.brain.agent import JarvisAgent


@pytest.fixture
def temp_scheduler(tmp_path):
    db_file = tmp_path / "test_reminders.db"
    return ReminderScheduler(db_path=db_file)


def test_wake_word_detector_vad_gating():
    detector = WakeWordDetector(threshold=0.5)

    # Empty chunk
    assert detector.process_chunk(np.array([], dtype=np.float32)) is False

    # Silent audio chunk (RMS near 0)
    silent_chunk = np.zeros(1280, dtype=np.float32)
    assert detector.process_chunk(silent_chunk) is False

    # Int16 silent chunk
    silent_int16 = np.zeros(1280, dtype=np.int16)
    assert detector.process_chunk(silent_int16) is False


def test_wake_chime_generation():
    # Verify chime synthesis executes cleanly without errors
    play_wake_chime()


def test_reminder_scheduler_crud(temp_scheduler):
    # Add reminder
    rem = temp_scheduler.add_reminder("Take medication", delay_seconds=120)
    assert rem["id"] is not None
    assert rem["message"] == "Take medication"
    assert rem["status"] == "pending"

    # List reminders
    pending = temp_scheduler.list_reminders(status="pending")
    assert len(pending) >= 1
    assert any(r["id"] == rem["id"] for r in pending)

    # Cancel reminder
    cancelled = temp_scheduler.cancel_reminder(rem["id"])
    assert cancelled is True

    # Verify no longer pending
    pending_after = temp_scheduler.list_reminders(status="pending")
    assert not any(r["id"] == rem["id"] for r in pending_after)


def test_windows_notification_wrapper():
    # Verify helper executes without crashing
    res = send_windows_notification("JARVIS Alert", "Test notification")
    assert isinstance(res, bool)


@pytest.mark.asyncio
async def test_agent_reminder_fastpath(monkeypatch, tmp_path):
    test_db = tmp_path / "agent_reminders.db"
    scheduler = ReminderScheduler(db_path=test_db)
    monkeypatch.setattr("jarvis.tools.reminders.get_reminder_scheduler", lambda: scheduler)

    agent = JarvisAgent()

    # Fast-path: set reminder
    set_resp = await agent._handle_direct_os_command("Remind me to check deployment in 5 minutes")
    assert set_resp is not None
    assert "reminder" in set_resp.lower()
    assert "check deployment" in set_resp.lower()

    # Fast-path: list reminders
    list_resp = await agent._handle_direct_os_command("List reminders")
    assert list_resp is not None
    assert "check deployment" in list_resp.lower()

    # Fast-path: cancel reminder
    cancel_resp = await agent._handle_direct_os_command("Cancel reminder 1")
    assert cancel_resp is not None
    assert "cancelled" in cancel_resp.lower()
