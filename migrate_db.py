import sqlite3
import os

def migrate_database():
    db_path = os.path.join(os.path.dirname(__file__), "chat_history.db")
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if we need to migrate
        cursor.execute("PRAGMA table_info(messages)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Backup the existing data
        cursor.execute("SELECT id, role, content, timestamp FROM messages")
        messages = cursor.fetchall()
        
        # Drop and recreate the table with the new schema
        cursor.execute("DROP TABLE IF EXISTS messages_backup")
        cursor.execute("ALTER TABLE messages RENAME TO messages_backup")
        
        # Create the new table with sub-second precision
        cursor.execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'now'))
            )
        """)
        
        # Copy the data back with the original timestamps
        cursor.executemany(
            """
            INSERT INTO messages (id, role, content, timestamp)
            VALUES (?, ?, ?, ? || '.000')
            """,
            [(id, role, content, ts) for id, role, content, ts in messages]
        )
        
        # Clean up
        cursor.execute("DROP TABLE messages_backup")
        conn.commit()
        print("Database migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()
