"""
JARVIS AI - Proactive Reminders & Windows Desktop Notification Engine (Tier 3 / Phase 5)
Schedules desktop alerts, manages timers, and broadcasts spoken reminders with Kokoro TTS.
"""

import asyncio
import logging
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

logger = logging.getLogger("JARVIS.Tools.Reminders")

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "jarvis_memory.db"


def send_windows_notification(title: str, message: str) -> bool:
    """Dispatches a native Windows 10/11 Toast Notification."""
    if sys.platform == "win32":
        try:
            # Escape quotes
            safe_title = title.replace('"', '\\"').replace("'", "''")
            safe_msg = message.replace('"', '\\"').replace("'", "''")
            ps_script = f"""
            try {{
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
                $template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
                $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
                $text = $xml.GetElementsByTagName("text")
                $text[0].AppendChild($xml.CreateTextNode("{safe_title}")) | Out-Null
                $text[1].AppendChild($xml.CreateTextNode("{safe_msg}")) | Out-Null
                $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("JARVIS AI").Show($toast)
            }} catch {{}}
            """
            subprocess.Popen(
                ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True,
            )
            return True
        except Exception as e:
            logger.debug(f"Windows notification error: {e}")
    return False


class ReminderScheduler:
    """Manages persistent scheduled reminders and background alerts."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._alert_callbacks: List[Callable[[Dict[str, Any]], None]] = []

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    due_timestamp REAL NOT NULL,
                    created_at REAL NOT NULL,
                    status TEXT DEFAULT 'pending'
                );
            """)

    def add_reminder(self, message: str, delay_seconds: int = 60) -> Dict[str, Any]:
        """Schedules a new reminder to trigger after delay_seconds."""
        now = time.time()
        due = now + max(1, delay_seconds)
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO reminders (message, due_timestamp, created_at, status) VALUES (?, ?, ?, 'pending')",
                (message.strip(), due, now),
            )
            rem_id = cur.lastrowid

        logger.info(f"Scheduled reminder #{rem_id} for {delay_seconds}s from now: '{message}'")
        return {
            "id": rem_id,
            "message": message.strip(),
            "due_timestamp": due,
            "delay_seconds": delay_seconds,
            "status": "pending",
        }

    def list_reminders(self, status: str = "pending") -> List[Dict[str, Any]]:
        """Lists active or past reminders."""
        with self._get_conn() as conn:
            cur = conn.execute(
                "SELECT id, message, due_timestamp, created_at, status FROM reminders WHERE status = ? ORDER BY due_timestamp ASC",
                (status,),
            )
            return [dict(r) for r in cur.fetchall()]

    def cancel_reminder(self, reminder_id: int) -> bool:
        """Cancels a pending reminder."""
        with self._get_conn() as conn:
            cur = conn.execute("UPDATE reminders SET status = 'cancelled' WHERE id = ? AND status = 'pending'", (reminder_id,))
            return cur.rowcount > 0

    def register_alert_callback(self, cb: Callable[[Dict[str, Any]], None]):
        """Registers a callback function invoked when a reminder triggers."""
        self._alert_callbacks.append(cb)

    async def _worker_loop(self):
        """Asynchronous monitor checking for due reminders every second."""
        while self._running:
            try:
                await asyncio.sleep(1.0)
                now = time.time()
                due_items = []
                with self._get_conn() as conn:
                    cur = conn.execute(
                        "SELECT id, message, due_timestamp FROM reminders WHERE status = 'pending' AND due_timestamp <= ?",
                        (now,),
                    )
                    due_items = [dict(r) for r in cur.fetchall()]
                    if due_items:
                        ids = [d["id"] for d in due_items]
                        conn.executemany("UPDATE reminders SET status = 'triggered' WHERE id = ?", [(i,) for i in ids])

                for item in due_items:
                    msg = item["message"]
                    logger.info(f"Triggering reminder #{item['id']}: {msg}")
                    send_windows_notification("JARVIS Directive Alert", msg)
                    for cb in self._alert_callbacks:
                        try:
                            if asyncio.iscoroutinefunction(cb):
                                await cb(item)
                            else:
                                cb(item)
                        except Exception as e:
                            logger.debug(f"Alert callback notice: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Reminder loop notice: {e}")

    def start(self):
        """Starts the background monitoring loop in the active asyncio event loop."""
        if not self._running:
            self._running = True
            try:
                loop = asyncio.get_running_loop()
                self._task = loop.create_task(self._worker_loop())
            except RuntimeError:
                pass

    def stop(self):
        """Stops the reminder monitor."""
        self._running = False
        if self._task:
            self._task.cancel()


# Global Singleton
_scheduler_instance: Optional[ReminderScheduler] = None


def get_reminder_scheduler() -> ReminderScheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = ReminderScheduler()
    return _scheduler_instance


# Tool Callables
def set_reminder_tool(message: str, delay_seconds: int = 60) -> str:
    """Sets a workstation reminder alert."""
    scheduler = get_reminder_scheduler()
    scheduler.start()
    res = scheduler.add_reminder(message=message, delay_seconds=delay_seconds)
    mins = round(delay_seconds / 60, 1)
    time_str = f"{delay_seconds} seconds" if delay_seconds < 60 else f"{mins} minutes"
    return f"Right away, sir. I have set a reminder for {time_str}: '{message}'."


def list_reminders_tool() -> str:
    """Lists all pending reminders."""
    scheduler = get_reminder_scheduler()
    items = scheduler.list_reminders(status="pending")
    if not items:
        return "You have no active pending reminders scheduled, sir."
    now = time.time()
    lines = ["Here are your pending reminders, sir:"]
    for r in items:
        remaining = max(0, int(r["due_timestamp"] - now))
        mins = remaining // 60
        secs = remaining % 60
        lines.append(f"• [ID #{r['id']}] '{r['message']}' (Due in {mins}m {secs}s)")
    return "\n".join(lines)


def cancel_reminder_tool(reminder_id: int) -> str:
    """Cancels a scheduled reminder."""
    scheduler = get_reminder_scheduler()
    success = scheduler.cancel_reminder(reminder_id)
    if success:
        return f"Reminder #{reminder_id} has been cancelled, sir."
    return f"I could not locate an active pending reminder with ID #{reminder_id}, sir."
