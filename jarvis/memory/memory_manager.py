"""
JARVIS AI - Long-Term Episodic Memory & Knowledge Base (Tier 5)
Provides persistent storage for user preferences, project knowledge,
personal facts, and session transcripts using SQLite with WAL mode.
"""

import os
import sqlite3
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger("JARVIS.Memory")

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "jarvis_memory.db"


class MemoryManager:
    """
    Manages SQLite-backed long-term memory for user facts,
    preferences, custom instructions, and persistent notes.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns SQLite connection with WAL journal mode for high concurrency."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_database(self):
        """Initializes tables for facts, notes, and session logs."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS user_facts (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT DEFAULT '',
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_facts_category ON user_facts(category);
                CREATE INDEX IF NOT EXISTS idx_notes_title ON notes(title);
            """)

    def remember_fact(self, key: str, value: str, category: str = "general") -> str:
        """Stores or updates a persistent user preference or fact."""
        clean_key = key.strip().lower()
        clean_val = value.strip()
        now = time.time()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO user_facts (key, value, category, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    updated_at = excluded.updated_at
                """,
                (clean_key, clean_val, category.lower(), now),
            )
        logger.info(f"Memory stored: '{clean_key}' -> '{clean_val}'")
        return f"Understood, sir. I have committed to memory: {clean_key} = {clean_val}."

    def recall_fact(self, key: str) -> Optional[str]:
        """Recalls a specific fact by key."""
        clean_key = key.strip().lower()
        with self._get_connection() as conn:
            cur = conn.execute("SELECT value FROM user_facts WHERE key = ?", (clean_key,))
            row = cur.fetchone()
            if row:
                return row["value"]
        return None

    def search_memory(self, query: str) -> List[Dict[str, Any]]:
        """Performs keyword search across remembered facts and notes."""
        clean_query = f"%{query.strip().lower()}%"
        results = []
        with self._get_connection() as conn:
            # Search facts
            cur = conn.execute(
                "SELECT key, value, category FROM user_facts WHERE key LIKE ? OR value LIKE ?",
                (clean_query, clean_query),
            )
            for row in cur.fetchall():
                results.append({
                    "type": "fact",
                    "key": row["key"],
                    "value": row["value"],
                    "category": row["category"],
                })

            # Search notes
            cur = conn.execute(
                "SELECT title, content, tags FROM notes WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?",
                (clean_query, clean_query, clean_query),
            )
            for row in cur.fetchall():
                results.append({
                    "type": "note",
                    "title": row["title"],
                    "content": row["content"],
                    "tags": row["tags"],
                })

        return results

    def get_all_facts(self) -> Dict[str, str]:
        """Returns all stored facts as a key-value dictionary."""
        facts = {}
        with self._get_connection() as conn:
            cur = conn.execute("SELECT key, value FROM user_facts ORDER BY category, key")
            for row in cur.fetchall():
                facts[row["key"]] = row["value"]
        return facts

    def forget_fact(self, key: str) -> bool:
        """Removes a fact from long-term memory."""
        clean_key = key.strip().lower()
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM user_facts WHERE key = ?", (clean_key,))
            return cur.rowcount > 0

    def save_note(self, title: str, content: str, tags: str = "") -> str:
        """Saves a permanent reference note."""
        now = time.time()
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO notes (title, content, tags, created_at) VALUES (?, ?, ?, ?)",
                (title.strip(), content.strip(), tags.strip(), now),
            )
        return f"Note '{title}' saved securely in memory archives, sir."

    def list_notes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns recent notes."""
        notes = []
        with self._get_connection() as conn:
            cur = conn.execute("SELECT id, title, content, tags, created_at FROM notes ORDER BY id DESC LIMIT ?", (limit,))
            for row in cur.fetchall():
                notes.append(dict(row))
        return notes

    def get_context_for_prompt(self, max_items: int = 12) -> str:
        """
        Formats remembered user facts into a clean block suitable for
        dynamic injection into the JARVIS system prompt.
        """
        facts = self.get_all_facts()
        if not facts:
            return ""

        lines = ["\n[Long-Term User Memory & Workstation Context]:"]
        count = 0
        for k, v in facts.items():
            lines.append(f"• {k.replace('_', ' ').title()}: {v}")
            count += 1
            if count >= max_items:
                break
        return "\n".join(lines)


# Global singleton instance
_memory_instance: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Returns the shared MemoryManager singleton."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = MemoryManager()
    return _memory_instance
