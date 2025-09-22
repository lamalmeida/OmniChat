import sqlite3
from datetime import datetime, timedelta
from token import OP
from typing import List, Dict, Any, Optional
import os

class MemoryDB:
    """A simple SQLite-based memory database for storing conversation history."""
    
    def __init__(self, db_path: str = "chat_history.db"):
        """Initialize the memory database.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._init_db()
    
    def _get_connection(self):
        """Get a database connection."""
        return sqlite3.connect(self.db_path)
    
    def _init_db(self):
        """Initialize the database with the required tables and handle migrations."""
        with self._get_connection() as conn:
            # Enable foreign key constraints
            conn.execute("PRAGMA foreign_keys = ON")
            
            # Create messages table if it doesn't exist
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'now'))
                )
            """)
            
            # Create adapters table if it doesn't exist
            conn.execute("""
                CREATE TABLE IF NOT EXISTS adapters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    class_name TEXT NOT NULL,
                    description TEXT
                )
            """)
            
            # Create tools table if it doesn't exist
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tools (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    adapter_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    full_name TEXT UNIQUE NOT NULL,
                    short_desc TEXT,
                    example TEXT,
                    side_effects BOOLEAN,
                    FOREIGN KEY (adapter_id) REFERENCES adapters(id) ON DELETE CASCADE
                )
            """)
            
            # Migration: Check if old tools table exists and migrate if needed
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='tools' AND sql LIKE '%description TEXT%'
            """)
            needs_migration = cursor.fetchone() is not None
            
            if needs_migration:
                # Backup old tools data
                cursor.execute("SELECT * FROM tools")
                old_tools = cursor.fetchall()
                
                # Drop old table
                cursor.execute("DROP TABLE tools")
                
                # Recreate with new schema
                cursor.execute("""
                    CREATE TABLE tools (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        adapter_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        full_name TEXT UNIQUE NOT NULL,
                        short_desc TEXT,
                        example TEXT,
                        side_effects BOOLEAN,
                        FOREIGN KEY (adapter_id) REFERENCES adapters(id) ON DELETE CASCADE
                    )
                """)
                
                # Migrate data if needed
                if old_tools:
                    # Create a default adapter for existing tools
                    cursor.execute("""
                        INSERT OR IGNORE INTO adapters (name, class_name, description)
                        VALUES (?, ?, ?)
                    """, ("legacy_tools", "LegacyAdapter", "Legacy tools from previous version"))
                    
                    adapter_id = cursor.lastrowid
                    
                    # Migrate old tools to new schema
                    for tool in old_tools:
                        cursor.execute("""
                            INSERT INTO tools 
                            (adapter_id, name, full_name, short_desc, example, side_effects)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            adapter_id,
                            tool[1].split('.')[-1] if '.' in tool[1] else tool[1],
                            tool[1],  # full_name
                            tool[2],  # description as short_desc
                            tool[3],  # example
                            bool(tool[4]) if len(tool) > 4 else False  # side_effects
                        ))
            
            conn.commit()
    
    def add_message(self, role: str, content: str) -> int:
        """Add a message to the database.
        
        Args:
            role: 'user' or 'assistant'
            content: The message content
            
        Returns:
            The ID of the inserted message
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO messages (role, content, timestamp)
                VALUES (?, ?, STRFTIME('%Y-%m-%d %H:%M:%f', 'now'))
                """,
                (role, content)
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_recent_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the most recent messages from the database.
        
        Args:
            limit: Maximum number of messages to return
            
        Returns:
            List of message dictionaries with 'role' and 'content' keys
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content, timestamp FROM messages "
                "ORDER BY timestamp DESC, id DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            
            # Convert to list of dicts with role and content
            return [
                {"role": row[0], "content": row[1], "timestamp": row[2]}
                for row in reversed(rows)  # Return in chronological order
            ]
    
    def clear_messages(self) -> None:
        """Clear all messages from the database."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM messages")
            conn.commit()
    
    def clear_messages_by_role(self, role: str) -> int:
        """Delete messages by role (e.g., 'user' or 'assistant').
        
        Args:
            role: The role to filter messages by
            
        Returns:
            Number of messages deleted
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE role = ?", (role,))
            conn.commit()
            return cursor.rowcount
    
    def clear_messages_by_date_range(self, start_date: str, end_date: str) -> int:
        """Delete messages within a specific date range.
        
        Args:
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format (inclusive)
            
        Returns:
            Number of messages deleted
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM messages 
                WHERE date(timestamp) BETWEEN ? AND ?
                """,
                (start_date, end_date)
            )
            conn.commit()
            return cursor.rowcount
    
    def clear_message_by_id(self, message_id: int) -> bool:
        """Delete a specific message by its ID.
        
        Args:
            message_id: The ID of the message to delete
            
        Returns:
            True if a message was deleted, False otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
            conn.commit()
            return cursor.rowcount > 0

    def register_adapter(self, name: str, class_name: str, description: str = "") -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO adapters (name, class_name, description) VALUES (?, ?, ?)",
                (name, class_name, description)
            )
            conn.commit()
            cursor.execute("SELECT id FROM adapters WHERE name = ?", (name,))
            return cursor.fetchone()[0]

    def register_tool(self, adapter_id: int, name: str, short_desc: str,
                    example: str, side_effects: bool, full_name: Optional[str] = None) -> int:
        if full_name == None:
            full_name = f"{adapter_id}.{name}"  
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR IGNORE INTO tools (adapter_id, name, full_name, short_desc, example, side_effects)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (adapter_id, name, f"{full_name}", short_desc, example, side_effects)
            )
            conn.commit()
            cursor.execute("SELECT id FROM tools WHERE full_name = ?", (full_name,))
            return cursor.fetchone()[0]

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get all registered tools with their details.
        
        Returns:
            List of dictionaries containing tool information
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.full_name, t.short_desc, t.example, t.side_effects, a.name as adapter_name
                FROM tools t
                JOIN adapters a ON t.adapter_id = a.id
            """)
            rows = cursor.fetchall()
            return [
                {
                    "name": row[0],  # full_name
                    "description": row[1] or "",  # short_desc
                    "example": row[2] or "",  # example
                    "side_effects": bool(row[3]) if row[3] is not None else False,
                    "adapter": row[4]  # adapter_name
                }
                for row in rows
            ]

    
