"""
Core WhatsApp Exporter functionality.
"""

import os
import sys
import re
from datetime import datetime

from .database import DatabaseManager
from .participants import ParticipantManager
from .mood_analyzer import MoodAnalyzer
from .formatter import ConversationFormatter, ForwardInfo


class WhatsAppExporter:
    """Main WhatsApp conversation exporter."""
    
    def __init__(self, db_path=None, backup_mode=False, backup_base_path=None):
        """Initialize with WhatsApp database."""
        self.db_manager = DatabaseManager(db_path, backup_mode, backup_base_path)
        self.participant_manager = ParticipantManager(self.db_manager)
        self.mood_analyzer = MoodAnalyzer()
        self.formatter = ConversationFormatter(self.participant_manager, self.mood_analyzer)
        
        # Message processing
        self.messages = []
        
        # Media handling
        self.media_base_path = self._get_media_base_path(backup_mode, backup_base_path)
        
        print(f"📁 Database: {self.db_manager.db_path}")
        if self.media_base_path:
            print(f"📂 Media base: {self.media_base_path}")
    
    def _get_media_base_path(self, backup_mode, backup_base_path):
        """Get media base path for file attachments."""
        if backup_mode and backup_base_path:
            return backup_base_path
        else:
            return os.path.expanduser("~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/Message")
    
    def get_all_contacts(self):
        """Get all contacts and groups with phone numbers."""
        try:
            contacts = self.db_manager.fetch_all("""
                SELECT ZCONTACTJID, ZPARTNERNAME
                FROM ZWACHATSESSION 
                WHERE ZCONTACTJID IS NOT NULL
                AND ZPARTNERNAME IS NOT NULL
                AND ZPARTNERNAME != ''
                ORDER BY ZPARTNERNAME
            """)
            
            contact_list = []
            for jid, name in contacts:
                if jid and name:
                    from .utils import extract_phone_number, format_phone_number
                    phone = extract_phone_number(jid)
                    formatted_phone = format_phone_number(phone) if phone else None
                    
                    contact_list.append({
                        'jid': jid,
                        'name': name,
                        'phone': phone,
                        'formatted_phone': formatted_phone,
                        'is_group': jid.endswith('@g.us'),
                        'reaction_count': 0  # Default value
                    })
            return contact_list
        except Exception as e:
            print(f"❌ Error getting all contacts: {e}")
            return []
    
    def get_contacts_with_reactions(self):
        """Get contacts with reactions and their phone numbers."""
        try:
            contacts = self.db_manager.fetch_all("""
                SELECT 
                    CASE WHEN m.ZISFROMME = 1 THEN m.ZTOJID ELSE m.ZFROMJID END as contact_jid,
                    COUNT(*) as reaction_count
                FROM ZWAMESSAGE m
                JOIN ZWAMESSAGEINFO i ON m.Z_PK = i.ZMESSAGE
                WHERE m.ZMESSAGETYPE = 0 
                AND i.ZRECEIPTINFO IS NOT NULL
                AND LENGTH(i.ZRECEIPTINFO) > 50
                AND (HEX(i.ZRECEIPTINFO) LIKE '%F09F%' OR HEX(i.ZRECEIPTINFO) LIKE '%E2%')
                AND (m.ZFROMJID LIKE '%@s.whatsapp.net' OR m.ZTOJID LIKE '%@s.whatsapp.net')
                GROUP BY contact_jid
                ORDER BY reaction_count DESC
            """)
            
            contact_list = []
            for jid, count in contacts:
                if jid:
                    from .utils import extract_phone_number, format_phone_number
                    phone = extract_phone_number(jid)
                    formatted_phone = format_phone_number(phone) if phone else None
                    
                    contact_list.append({
                        'jid': jid,
                        'name': self.participant_manager.get_contact_name(jid),
                        'phone': phone,
                        'formatted_phone': formatted_phone,
                        'is_group': jid.endswith('@g.us'),
                        'reaction_count': count
                    })
            return contact_list
        except Exception as e:
            print(f"❌ Error getting contacts: {e}")
            return []
    
    def export_conversation(self, contact_input, backup_mode=None, limit=None, recent=False):
        """Export a specific conversation."""
        try:
            # Find target contact
            target_contact = self._find_contact(contact_input)
            if not target_contact:
                return None
            
            # Get messages
            messages = self._get_conversation_messages(target_contact['jid'], limit, recent)
            if not messages:
                print(f"❌ No messages found for {target_contact['name']}")
                return None
            
            print(f"📋 Found {len(messages)} messages...")
            
            # Export
            formatted_text = self.formatter.format_conversation(messages, target_contact['name'], target_contact['jid'])
            
            # Save to file
            filename = self._generate_filename(target_contact['name'])
            filepath = os.path.join("conversations", filename)
            
            # Ensure directory exists
            os.makedirs("conversations", exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(formatted_text)
            
            print(f"✅ Conversation exported to: {filepath}")
            print(f"📄 File size: {os.path.getsize(filepath)} bytes")
            return filepath
            
        except Exception as e:
            print(f"❌ Error exporting conversation: {e}")
            return None
    
    def _find_contact(self, contact_input):
        """Find contact by name or JID."""
        # First try exact match
        contacts = self.db_manager.fetch_all("""
            SELECT ZCONTACTJID, ZPARTNERNAME 
            FROM ZWACHATSESSION 
            WHERE ZPARTNERNAME = ? OR ZCONTACTJID = ?
        """, (contact_input, contact_input))
        
        if contacts:
            jid, name = contacts[0]
            return {'jid': jid, 'name': name}
        
        # Try partial match
        contacts = self.db_manager.fetch_all("""
            SELECT ZCONTACTJID, ZPARTNERNAME 
            FROM ZWACHATSESSION 
            WHERE ZPARTNERNAME LIKE ? 
            ORDER BY ZPARTNERNAME
        """, (f"%{contact_input}%",))
        
        if contacts:
            jid, name = contacts[0]
            return {'jid': jid, 'name': name}
        
        print(f"❌ Contact '{contact_input}' not found.")
        return None
    
    def _get_conversation_messages(self, contact_jid, limit=None, recent=False):
        """Get messages for a conversation."""
        self.messages = []
        
        try:
            # Base query for messages
            query = """
                SELECT 
                    m.Z_PK as message_id,
                    datetime(m.ZMESSAGEDATE + 978307200, 'unixepoch') as date,
                    m.ZTEXT as content,
                    m.ZISFROMME as is_from_me,
                    m.ZMESSAGETYPE as message_type,
                    m.ZGROUPMEMBER as group_member_id,
                    m.ZFROMJID as from_jid,
                    m.ZTOJID as to_jid,
                    m.ZCHATSESSION as chat_session,
                    m.ZPARENTMESSAGE as parent_message_id
                FROM ZWAMESSAGE m
                WHERE (m.ZFROMJID = ? OR m.ZTOJID = ?)
                ORDER BY m.ZMESSAGEDATE {}
            """.format("DESC" if recent else "ASC")
            
            params = (contact_jid, contact_jid)
            
            if limit:
                query += f" LIMIT {limit}"
            
            rows = self.db_manager.fetch_all(query, params)
            
            if recent and rows:
                rows = list(reversed(rows))
            
            # Process each message
            for row in rows:
                self._process_message_row(row, contact_jid)
            
            # Post-process messages
            self._post_process_messages(contact_jid)
            
            return self.messages
            
        except Exception as e:
            print(f"❌ Error getting conversation messages: {e}")
            return []
    
    def _process_message_row(self, row, contact_jid):
        """Process a single message row."""
        # Convert row to dict
        message = {
            'message_id': row[0],
            'date': row[1],
            'content': row[2] or '',
            'is_from_me': bool(row[3]),
            'message_type': row[4],
            'group_member_id': row[5],
            'from_jid': row[6],
            'to_jid': row[7],
            'chat_session': row[8],
            'parent_message_id': row[9],
            'sender_name': None,
            'quoted_text': None,
            'reaction_emoji': None,
            'media_info': None,
            'is_forwarded': False
        }
        
        # Get sender name for group messages
        if contact_jid.endswith('@g.us') and message['group_member_id']:
            message['sender_name'] = self._get_group_member_name(contact_jid, message['group_member_id'])
        
        # Get reaction info
        self._get_message_reactions(message)
        
        # Get media info
        self._get_message_media(message)
        
        # Check for forwarded content
        self._check_forwarded_message(message)
        
        self.messages.append(message)
    
    def _get_group_member_name(self, group_jid, member_id):
        """Get group member name by ID."""
        try:
            result = self.db_manager.fetch_one("""
                SELECT gm.ZMEMBERJID
                FROM ZWAGROUPMEMBER gm
                LEFT JOIN ZWACHATSESSION gs ON gs.ZCONTACTJID = ?
                WHERE gm.ZCHATSESSION = gs.Z_PK AND gm.Z_PK = ?
            """, (group_jid, member_id))
            
            if result and result[0]:
                member_jid = result[0]
                name = self.participant_manager.get_contact_name(member_jid)
                if name != member_jid:
                    return name
                else:
                    # Use initials if no name found
                    return self.participant_manager.get_group_initials_for_jid(group_jid, member_jid)
            
            return f"Member {member_id}"
        except Exception:
            return f"Member {member_id}"
    
    def _get_message_reactions(self, message):
        """Get reaction information for a message."""
        try:
            result = self.db_manager.fetch_one("""
                SELECT i.ZRECEIPTINFO
                FROM ZWAMESSAGEINFO i
                WHERE i.ZMESSAGE = ?
            """, (message['message_id'],))
            
            if result and result[0]:
                receipt_info = result[0]
                emoji = self._extract_reaction_emoji(receipt_info)
                if emoji:
                    message['reaction_emoji'] = emoji
        except Exception:
            pass
    
    def _extract_reaction_emoji(self, receipt_info):
        """Extract reaction emoji from receipt info."""
        try:
            if isinstance(receipt_info, bytes):
                hex_data = receipt_info.hex().upper()
            else:
                hex_data = receipt_info
            
            # Look for emoji patterns in hex
            emoji_patterns = [
                'F09F988D',  # 😍
                'F09F9882',  # 😂
                'F09F98AE',  # 😮
                'F09F918D',  # 👍
                # Add more patterns as needed
            ]
            
            for pattern in emoji_patterns:
                if pattern in hex_data:
                    # Convert hex back to emoji
                    try:
                        emoji_bytes = bytes.fromhex(pattern)
                        return emoji_bytes.decode('utf-8')
                    except:
                        continue
            
            return None
        except:
            return None
    
    def _get_message_media(self, message):
        """Get media information for a message."""
        try:
            if message['message_type'] in [1, 2, 3, 5, 9, 13, 14]:  # Media types
                result = self.db_manager.fetch_one("""
                    SELECT 
                        mi.ZFILESIZE,
                        mi.ZMEDIAKEY,
                        mi.ZMEDIALOCALPATH,
                        mi.ZMEDIATITLE
                    FROM ZWAMEDIAITEM mi
                    WHERE mi.ZMESSAGE = ?
                """, (message['message_id'],))
                
                if result:
                    file_size, media_key, local_path, title = result
                    
                    # Construct full media path
                    full_path = None
                    if local_path and self.media_base_path:
                        full_path = os.path.join(self.media_base_path, local_path)
                        if not os.path.exists(full_path):
                            full_path = None
                    
                    message['media_info'] = {
                        'file_size': file_size,
                        'media_key': media_key,
                        'local_path': full_path,
                        'title': title,
                        'message_type': message['message_type'],
                        'file_id': media_key or f"media_{message['message_id']}"
                    }
        except Exception:
            pass
    
    def _check_forwarded_message(self, message):
        """Check if message is forwarded."""
        # Simple heuristic - look for forward indicators in content
        content = message.get('content', '').lower()
        if any(indicator in content for indicator in ['forwarded', 'transferred', '↪']):
            message['is_forwarded'] = True
    
    def _post_process_messages(self, contact_jid):
        """Post-process messages for citations and forwards."""
        # Create message lookup for parent references
        message_lookup = {msg['message_id']: msg for msg in self.messages}
        
        # Process citations/replies
        for message in self.messages:
            if (not message['quoted_text'] and message['parent_message_id'] 
                and message['parent_message_id'] in message_lookup):
                parent_msg = message_lookup[message['parent_message_id']]
                quoted_content = parent_msg['content'][:50]
                if len(parent_msg['content']) > 50:
                    quoted_content += "..."
                message['quoted_text'] = quoted_content
    
    def _generate_filename(self, contact_name):
        """Generate safe filename for export."""
        # Clean up contact name for filename
        safe_name = re.sub(r'[^\w\s-]', '', contact_name)
        safe_name = re.sub(r'[-\s]+', '_', safe_name)
        safe_name = safe_name.strip('_')
        
        # Add timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"whatsapp_conversation_{safe_name}_{timestamp}.md"
    
    def close(self):
        """Close database connection."""
        self.db_manager.close_connection()