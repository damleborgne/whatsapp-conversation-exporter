"""
Database operations for WhatsApp export.
"""

import sqlite3
import os


class DatabaseManager:
    """Manages database connections and operations."""
    
    def __init__(self, db_path=None, backup_mode=False, backup_base_path=None):
        """Initialize database manager."""
        self.db_path = db_path
        self.backup_mode = backup_mode
        self.backup_base_path = backup_base_path
        self.connection = None
        
        if not db_path:
            self._find_database()
    
    def _find_database(self):
        """Find WhatsApp database automatically."""
        if self.backup_mode:
            self._find_backup_database()
        else:
            self._find_local_database()
    
    def _find_local_database(self):
        """Find local WhatsApp database."""
        possible_paths = [
            os.path.expanduser("~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite"),
            os.path.expanduser("~/Library/Containers/net.whatsapp.WhatsApp/Data/Library/ChatStorage.sqlite"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                self.db_path = path
                print(f"✅ Found database: {path}")
                return
        
        raise FileNotFoundError("❌ WhatsApp database not found")
    
    def _find_backup_database(self):
        """Find backup database from wtsexporter."""
        if not self.backup_base_path:
            raise ValueError("❌ Backup base path required for backup mode")
        
        chat_db_path = os.path.join(self.backup_base_path, "ChatStorage.sqlite")
        if os.path.exists(chat_db_path):
            self.db_path = chat_db_path
            print(f"✅ Found backup database: {chat_db_path}")
        else:
            raise FileNotFoundError(f"❌ Backup database not found at {chat_db_path}")
    
    def get_connection(self):
        """Get database connection (create if needed)."""
        if not self.connection:
            try:
                self.connection = sqlite3.connect(self.db_path)
                self.connection.row_factory = sqlite3.Row
            except Exception as e:
                raise Exception(f"❌ Error connecting to database: {e}")
        return self.connection
    
    def close_connection(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def execute_query(self, query, params=None):
        """Execute a query and return cursor."""
        conn = self.get_connection()
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor
    
    def fetch_all(self, query, params=None):
        """Execute query and fetch all results."""
        cursor = self.execute_query(query, params)
        return cursor.fetchall()
    
    def fetch_one(self, query, params=None):
        """Execute query and fetch one result."""
        cursor = self.execute_query(query, params)
        return cursor.fetchone()