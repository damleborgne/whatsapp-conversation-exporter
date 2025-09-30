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
        """Find backup database from wtsexporter - uses same logic as original."""
        if not self.backup_base_path:
            raise ValueError("❌ Backup base path required for backup mode")
        
        print("🔍 Looking for wtsexporter database...")
        
        # Look for files with exactly 40 characters (typical iOS backup hash length)
        candidate_files = []
        
        try:
            for item in os.listdir(self.backup_base_path):
                item_path = os.path.join(self.backup_base_path, item)
                
                # Check if it's a file with exactly 40 characters and no extension
                if (os.path.isfile(item_path) and 
                    len(item) == 40 and 
                    '.' not in item and 
                    all(c in '0123456789abcdefABCDEF' for c in item)):
                    
                    file_size = os.path.getsize(item_path)
                    candidate_files.append((item, item_path, file_size))
                    print(f"   📱 Found candidate: {item} ({file_size:,} bytes)")
            
            if candidate_files:
                # Sort by size and select largest (matches original logic)
                candidate_files.sort(key=lambda x: x[2], reverse=True)
                
                if len(candidate_files) > 1:
                    print(f"\n📋 Found {len(candidate_files)} database candidates:")
                    for i, (filename, path, size) in enumerate(candidate_files[:5], 1):
                        size_mb = size / (1024 * 1024)
                        print(f"   {i}. {filename} ({size_mb:.1f} MB)")
                    
                    print(f"\n💡 Auto-selecting largest file: {candidate_files[0][0]}")
                
                chosen_file = candidate_files[0]
                self.db_path = chosen_file[1]
                print(f"✅ Using database: {chosen_file[0]} ({chosen_file[2]:,} bytes)")
                return
                
        except Exception as e:
            print(f"❌ Error scanning backup directory: {e}")
        
        # Fallback to ChatStorage.sqlite approach (original fallback logic)
        print("⚠️ No 40-character files found, trying ChatStorage.sqlite...")
        possible_paths = [
            # Direct path
            os.path.join(self.backup_base_path, "ChatStorage.sqlite"),
            # In AppDomainGroup folder (wtsexporter structure)
            os.path.join(self.backup_base_path, "AppDomainGroup-group.net.whatsapp.WhatsApp.shared", "ChatStorage.sqlite"),
            # In result folder (alternative wtsexporter structure)
            os.path.join(self.backup_base_path, "result", "AppDomainGroup-group.net.whatsapp.WhatsApp.shared", "ChatStorage.sqlite"),
        ]
        
        for chat_db_path in possible_paths:
            if os.path.exists(chat_db_path):
                self.db_path = chat_db_path
                print(f"✅ Found backup database: {chat_db_path}")
                return
        
        raise FileNotFoundError(f"❌ Backup database not found in {self.backup_base_path}. Searched paths:\n" + 
                               "\n".join(f"  - {path}" for path in possible_paths))
    
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