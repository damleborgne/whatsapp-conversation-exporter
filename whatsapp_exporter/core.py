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
        
        # Media handling setup
        self.media_base_path = self._get_media_base_path(backup_mode, backup_base_path)
        
        self.formatter = ConversationFormatter(
            self.participant_manager, 
            self.mood_analyzer,
            self.media_base_path,
            backup_mode,
            self.db_manager
        )
        
        # Message processing
        self.messages = []
        
        print(f"📁 Database: {self.db_manager.db_path}")
        if self.media_base_path:
            print(f"📂 Media base: {self.media_base_path}")
    
    def _get_media_base_path(self, backup_mode, backup_base_path):
        """Get media base path for file attachments."""
        if backup_mode and backup_base_path:
            # Try different possible locations for media files in wtsexporter backups
            possible_media_paths = [
                # Direct path  
                backup_base_path,
                # In AppDomainGroup folder (wtsexporter structure)
                os.path.join(backup_base_path, "AppDomainGroup-group.net.whatsapp.WhatsApp.shared"),
                # In result folder (alternative wtsexporter structure)
                os.path.join(backup_base_path, "result", "AppDomainGroup-group.net.whatsapp.WhatsApp.shared"),
            ]
            
            # Return the first path that exists and contains a Message directory
            for media_path in possible_media_paths:
                message_path = os.path.join(media_path, "Message")
                if os.path.exists(message_path):
                    return message_path
            
            # If no Message directory found, return the first existing path
            for media_path in possible_media_paths:
                if os.path.exists(media_path):
                    return media_path
                    
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
            # If multiple matches, prefer the one with more messages (likely more recent/active)
            if len(contacts) > 1:
                print(f"🔍 Found {len(contacts)} contacts matching '{contact_input}':")
                for i, (jid, name) in enumerate(contacts):
                    msg_count = self.db_manager.fetch_one(
                        "SELECT COUNT(*) FROM ZWAMESSAGE WHERE ZFROMJID = ? OR ZTOJID = ?", 
                        (jid, jid))[0]
                    print(f"   {i+1}. {name} ({msg_count} messages)")
                
                # Pick the one with most messages
                best_contact = max(contacts, key=lambda c: self.db_manager.fetch_one(
                    "SELECT COUNT(*) FROM ZWAMESSAGE WHERE ZFROMJID = ? OR ZTOJID = ?", 
                    (c[0], c[0]))[0])
                jid, name = best_contact
                print(f"💡 Auto-selected: {name}")
            else:
                jid, name = contacts[0]
            return {'jid': jid, 'name': name}
        
        print(f"❌ Contact '{contact_input}' not found.")
        return None
    
    def _get_conversation_messages(self, contact_jid, limit=None, recent=False):
        """Get messages for a conversation."""
        self.messages = []
        
        try:
            # Base query for messages - matches the working original code
            query = """
                SELECT 
                    m.Z_PK as message_id,
                    m.ZMESSAGEDATE as message_date,
                    m.ZTEXT as content,
                    m.ZISFROMME as is_from_me,
                    m.ZMESSAGETYPE as message_type,
                    m.ZGROUPMEMBER as group_member_id,
                    m.ZFROMJID as from_jid,
                    m.ZTOJID as to_jid,
                    m.ZCHATSESSION as chat_session,
                    m.ZPARENTMESSAGE as parent_message_id,
                    m.ZFLAGS as flags,
                    i.ZRECEIPTINFO as receipt_info,
                    m.ZMEDIAITEM as media_item_id,
                    mi.ZMEDIALOCALPATH as media_local_path,
                    mi.ZTITLE as media_title,
                    mi.ZFILESIZE as media_file_size
                FROM ZWAMESSAGE m
                LEFT JOIN ZWAMESSAGEINFO i ON m.Z_PK = i.ZMESSAGE
                LEFT JOIN ZWAMEDIAITEM mi ON m.ZMEDIAITEM = mi.Z_PK
                WHERE (m.ZFROMJID = ? OR m.ZTOJID = ?)
                -- Exclude system messages: 6, 10, 15 = empty system notifications (group changes, status updates, etc.)
                AND m.ZMESSAGETYPE NOT IN (6, 10, 15)
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
        # Convert row to dict - now handles all fields from the query including media
        message = {
            'message_id': row[0],
            'date': self._convert_timestamp(row[1]),  # Convert timestamp in Python like original
            'content': row[2] or '',
            'is_from_me': bool(row[3]),
            'message_type': row[4],
            'group_member_id': row[5],
            'from_jid': row[6],
            'to_jid': row[7],
            'chat_session': row[8],
            'parent_message_id': row[9],
            'flags': row[10] or 0,
            'receipt_info': row[11],
            'media_item_id': row[12],
            'media_local_path': row[13],
            'media_title': row[14],
            'media_file_size': row[15],
            'sender_name': None,
            'quoted_text': None,
            'reaction_emoji': None,
            'media_info': None,
            'is_forwarded': False
        }
        
        # Handle forwarded messages
        message['is_forwarded'] = bool(message['flags'] & 0x180 == 0x180)
        
        # Handle media info
        if message['media_item_id']:
            # Special case for voice/video calls (type 59)
            if message['message_type'] == 59:
                message['media_info'] = {
                    'local_path': None,
                    'title': 'Appel vocal/vidéo',
                    'file_size': 0,
                    'message_type': 59
                }
            # Only create media_info if there's actual media content
            elif (message['media_local_path'] or 
                (message['media_file_size'] and message['media_file_size'] > 0) or 
                (message['media_title'] and message['media_title'].strip())):
                message['media_info'] = {
                    'local_path': message['media_local_path'],
                    'title': message['media_title'],
                    'file_size': message['media_file_size'],
                    'message_type': message['message_type']
                }
        
        # Get sender name for group messages
        if contact_jid.endswith('@g.us') and message['group_member_id']:
            message['sender_name'] = self._get_group_member_name(contact_jid, message['group_member_id'])
        
        # Get reaction info - pass contact_jid for group reaction support
        self._get_message_reactions(message, contact_jid)
        
        # Extract quoted text from protobuf metadata (100% systematic extraction)
        # Citations can be stored either in the message's media_item or in the parent's media_item
        quoted_text = None
        
        # First, try extracting from message's own media_item
        if message['media_item_id']:
            quoted_text = self._extract_quoted_text(message['media_item_id'])
        
        # If no citation found and we have a parent_message_id, check parent's media_item
        if not quoted_text and message['parent_message_id']:
            parent_media_id = self._get_parent_message_media_id(message['parent_message_id'])
            if parent_media_id:
                quoted_text = self._extract_quoted_text(parent_media_id)
        
        # Store the citation if found
        if quoted_text and not isinstance(quoted_text, ForwardInfo):
            message['quoted_text'] = quoted_text
        
        # Get media info
        self._get_message_media(message)
        
        # Check for forwarded content
        self._check_forwarded_message(message)
        
        self.messages.append(message)
    
    def _convert_timestamp(self, timestamp):
        """Convert WhatsApp timestamp - matches original logic."""
        if not timestamp:
            return None
        try:
            from datetime import datetime
            return datetime.fromtimestamp(timestamp + 978307200).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return None
    
    def _decode_varint(self, blob, start_pos):
        """Decode a protobuf varint starting at start_pos. Returns (value, next_pos)."""
        value = 0
        shift = 0
        pos = start_pos
        
        while pos < len(blob):
            byte = blob[pos]
            value |= (byte & 0x7F) << shift
            pos += 1
            if (byte & 0x80) == 0:  # No continue bit
                break
            shift += 7
            if shift >= 64:  # Prevent infinite loop
                break
        
        return value, pos
    
    def _get_parent_message_media_id(self, parent_message_id):
        """Get the media_item_id from parent message (if it has one)."""
        try:
            result = self.db_manager.fetch_one(
                "SELECT ZMEDIAITEM FROM ZWAMESSAGE WHERE Z_PK = ?",
                (parent_message_id,)
            )
            return result[0] if result and result[0] else None
        except Exception:
            return None
    
    def _extract_quoted_text(self, media_item_id):
        """Extract quoted text from media metadata - 100% systematic extraction from protobuf."""
        try:
            # First, try to get the media info itself (for media quotes)
            result = self.db_manager.fetch_one(
                "SELECT ZMEDIALOCALPATH, ZTITLE, ZMESSAGE FROM ZWAMEDIAITEM WHERE Z_PK = ?", 
                (media_item_id,)
            )
            
            if result and result[0]:  # Has media path
                media_path = result[0]
                media_title = result[1]
                
                # Get media type from path extension
                if media_path:
                    ext = os.path.splitext(media_path)[1].lower()
                    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                        media_type = "Image"
                    elif ext in ['.mp4', '.mov', '.avi']:
                        media_type = "Video"
                    elif ext in ['.mp3', '.wav', '.m4a']:
                        media_type = "Audio"
                    else:
                        media_type = "Media"
                    
                    # If there's a title/comment with the media, include it
                    if media_title and media_title.strip():
                        return f"[{media_type}] {media_title.strip()}"
                    else:
                        return f"[{media_type}]"
            
            # If no direct media info, try to extract from metadata blob
            result = self.db_manager.fetch_one(
                "SELECT ZMETADATA FROM ZWAMEDIAITEM WHERE Z_PK = ?", 
                (media_item_id,)
            )
            if not result or not result[0]:
                return None

            blob = result[0]
            
            # Try to find tag 1 specifically (most reliable citation tag)
            # Tag 1 with wire type 2 = 0x0a
            i = 0
            while i < len(blob) - 3:
                if blob[i] == 0x0a and (blob[i] & 0x7) == 2:  # Tag 1, wire type 2
                    # Decode the length
                    length_byte = blob[i + 1]
                    if length_byte < 128:
                        length = length_byte
                        data_start = i + 2
                    else:
                        # Multi-byte varint
                        length, data_start = self._decode_varint(blob, i + 1)
                    
                    if data_start + length <= len(blob) and length > 10:
                        try:
                            text = blob[data_start:data_start + length].decode('utf-8', errors='ignore').strip()
                            text = re.sub(r'[\x00-\x1f]+', '', text)
                            
                            if len(text) > 3:
                                # Check for forward hash
                                sanitized = re.sub(r"[^A-Za-z0-9'`{}]", "", text)
                                if (len(sanitized) > 10 and 
                                    re.fullmatch(r"[A-Za-z0-9]{2,24}['`][A-Za-z0-9{}]{2,48}", sanitized) and
                                    any(c.isdigit() or c in '{}' or (c.isalpha() and c.isupper()) for c in sanitized)):
                                    from .formatter import ForwardInfo
                                    return ForwardInfo(sanitized)
                                
                                # Valid quote found
                                if len(text) > 50:
                                    words = text[:50].split()
                                    text = ' '.join(words[:-1]) + "..." if len(words) > 1 else text[:50] + "..."
                                return text
                        except:
                            pass
                i += 1
            
            # Fallback: look for other tags (0, 2, 3, 4) if tag 1 not found
            i = 0
            best_match = None
            while i < len(blob) - 2:
                tag_byte = blob[i]
                if (tag_byte & 0x7) == 2:  # Length-delimited field
                    tag = tag_byte >> 3
                    
                    if tag <= 4 and tag != 1:  # Skip tag 1 (already checked above)
                        length_byte = blob[i + 1]
                        if length_byte < 128:
                            length = length_byte
                            data_start = i + 2
                            
                            if data_start + length <= len(blob) and 10 < length < 500:
                                try:
                                    text = blob[data_start:data_start + length].decode('utf-8', errors='ignore').strip()
                                    text = re.sub(r'[\x00-\x1f]+', '', text)
                                    
                                    if len(text) > 3 and not best_match:
                                        best_match = text
                                except:
                                    pass
                            
                            i += data_start + length
                            continue
                i += 1
            
            if best_match:
                if len(best_match) > 50:
                    words = best_match[:50].split()
                    best_match = ' '.join(words[:-1]) + "..." if len(words) > 1 else best_match[:50] + "..."
                return best_match
            
            return None
            
        except Exception:
            return None
    
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
    
    def _get_message_reactions(self, message, contact_jid=None):
        """Get reaction information for a message."""
        try:
            result = self.db_manager.fetch_one("""
                SELECT i.ZRECEIPTINFO
                FROM ZWAMESSAGEINFO i
                WHERE i.ZMESSAGE = ?
            """, (message['message_id'],))
            
            if result and result[0]:
                receipt_info = result[0]
                is_group = contact_jid and contact_jid.endswith('@g.us')
                emoji = self._extract_reaction_emoji(receipt_info, is_group, contact_jid)
                if emoji:
                    message['reaction_emoji'] = emoji
        except Exception:
            pass
    
    def _extract_reaction_emoji(self, receipt_info, is_group=False, group_jid=None):
        """Extract reaction emoji from receipt info with group support."""
        if not receipt_info:
            return None
            
        try:
            if isinstance(receipt_info, bytes):
                hex_data = receipt_info.hex().upper()
            else:
                hex_data = str(receipt_info).upper()
            
            # Find emoji with automatic modifier detection
            emoji = None
            if 'F09F' in hex_data:
                # Modern emojis (F09F prefix) - may have skin tone modifiers
                base_matches = re.findall(r'F09F[0-9A-F]{4}', hex_data)
                if base_matches:
                    # Try each match until we find a valid emoji
                    for base_emoji in base_matches:
                        try:
                            base_pos = hex_data.find(base_emoji)
                            remaining = hex_data[base_pos + len(base_emoji):]
                            
                            # Look for skin tone modifier (F09F8F[BB-BF])
                            skin_modifier_match = re.match(r'F09F8F(BB|BC|BD|BE|BF)', remaining)
                            if skin_modifier_match:
                                full_sequence = base_emoji + skin_modifier_match.group(0)
                                emoji = bytes.fromhex(full_sequence).decode('utf-8')
                            else:
                                emoji = bytes.fromhex(base_emoji).decode('utf-8')
                            
                            # If we successfully decoded an emoji, break
                            if emoji:
                                break
                        except:
                            # This match wasn't a valid emoji, try next one
                            continue
                        
            elif 'E2' in hex_data:
                # Legacy Unicode symbols (E2xx prefix) - may have color modifiers
                # Match 6 hex chars (3 bytes): E2 + 2 more bytes
                # Valid ranges: E2[8-9A-B][0-9A-F]{3} (captures all E280-E2BF)
                base_matches = re.findall(r'E2[8-9A-B][0-9A-F][0-9A-F]{2}', hex_data)
                if base_matches:
                    # Try each match until we find a valid emoji
                    for base_emoji in base_matches:
                        try:
                            base_pos = hex_data.find(base_emoji)
                            remaining = hex_data[base_pos + len(base_emoji):]
                            
                            # Look for color modifier (EFB8[8F-AB])
                            color_modifier_match = re.match(r'EFB8[8-9A-B][0-9A-F]', remaining)
                            if color_modifier_match:
                                full_sequence = base_emoji + color_modifier_match.group(0)
                                emoji = bytes.fromhex(full_sequence).decode('utf-8')
                            else:
                                emoji = bytes.fromhex(base_emoji).decode('utf-8')
                            
                            # If we successfully decoded an emoji, break
                            if emoji:
                                break
                        except:
                            # This match wasn't a valid emoji, try next one
                            continue
            
            if not emoji:
                return None
            
            # For groups, try to extract who reacted
            if is_group and group_jid:
                return self._decode_group_reactions(hex_data, emoji, group_jid)
            else:
                return emoji
                
        except Exception:
            return None
    
    def _decode_group_reactions(self, hex_data, emoji, group_jid):
        """Decode group reactions with person initials."""
        try:
            # Find JID patterns in hex data
            jid_matches = re.findall(r'333[0-9A-F]+?40732E77686174736170702E6E6574', hex_data)
            
            reactors = []
            if jid_matches:
                for jid_hex in jid_matches:
                    try:
                        # Decode JID
                        jid_bytes = bytes.fromhex(jid_hex)
                        jid_raw = jid_bytes.decode('utf-8', errors='ignore')
                        
                        # Extract clean phone number
                        phone_match = re.search(r'(\d+)@s\.whatsapp\.net', jid_raw)
                        if phone_match:
                            phone = phone_match.group(1)
                            clean_jid = f'{phone}@s.whatsapp.net'
                            
                            # Get initials for this person in this group
                            initials = self.participant_manager.get_group_initials_for_jid(group_jid, clean_jid)
                            if initials and initials not in reactors:
                                reactors.append(initials)
                    except Exception as e:
                        continue
            
            # If no JID found in hex data, it means "I" (owner) reacted
            # Get owner's initials from the group
            if not reactors:
                # Extract owner phone from group JID
                if '-' in group_jid:
                    owner_phone = group_jid.split('-')[0]
                    owner_jid = f"{owner_phone}@s.whatsapp.net"
                    owner_initials = self.participant_manager.get_group_initials_for_jid(group_jid, owner_jid)
                    if owner_initials and owner_initials != "?":
                        return f"[{owner_initials}:{emoji}]"
                # Fallback if we can't find owner initials
                return emoji
            
            if reactors:
                if len(reactors) == 1:
                    return f"[{reactors[0]}:{emoji}]"
                else:
                    reactor_list = ';'.join([f"{r}:{emoji}" for r in reactors])
                    return f"[{reactor_list}]"
            
            return emoji
            
        except Exception as e:
            print(f"DEBUG: Exception in _decode_group_reactions: {e}")
            return emoji
    
    def _get_message_media(self, message):
        """Get media information for a message."""
        try:
            if message['message_type'] in [1, 2, 3, 5, 9, 13, 14]:  # Media types
                result = self.db_manager.fetch_one("""
                    SELECT 
                        mi.ZFILESIZE,
                        mi.ZMEDIAKEY,
                        mi.ZMEDIALOCALPATH,
                        mi.ZTITLE,
                        mi.ZLATITUDE,
                        mi.ZLONGITUDE
                    FROM ZWAMEDIAITEM mi
                    WHERE mi.ZMESSAGE = ?
                """, (message['message_id'],))
                
                if result:
                    file_size, media_key, local_path, title, latitude, longitude = result
                    
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
                        'file_id': media_key or f"media_{message['message_id']}",
                        'latitude': latitude,
                        'longitude': longitude
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
        
        # Step 1: Resolve parent message quotes (like the original code)
        for message in self.messages:
            if (not message.get('quoted_text') and message.get('parent_message_id') 
                and message['parent_message_id'] in message_lookup):
                parent_msg = message_lookup[message['parent_message_id']]
                quoted_content = parent_msg['content'][:50] if parent_msg.get('content') else ''
                if len(parent_msg.get('content', '')) > 50:
                    quoted_content += "..."
                message['quoted_text'] = quoted_content
        
        # Step 2: Parse metadata for replies (like the original code)
        reply_targets = [m for m in self.messages 
                        if not m.get('quoted_text') and not m.get('parent_message_id') and m.get('media_item_id')]
        self._parse_metadata_replies(reply_targets)
    
    def _parse_metadata_replies(self, targets):
        """Parse metadata to find reply relationships (from original code)."""
        if not targets:
            return
        
        # Get metadata
        media_ids = [m['media_item_id'] for m in targets if m.get('media_item_id')]
        if not media_ids:
            return
        
        placeholders = ','.join(['?'] * len(media_ids))
        query = f"SELECT Z_PK,ZMETADATA FROM ZWAMEDIAITEM WHERE Z_PK IN ({placeholders})"
        metadata_rows = self.db_manager.fetch_all(query, media_ids)
        meta_map = {r[0]: r[1] for r in metadata_rows if r[1]}
        
        # Index original messages
        originals = {}
        for m in self.messages:
            text = (m.get('content') or '').strip()
            if len(text) >= 40:
                originals.setdefault(text[:60], []).append(m)
        
        # Process targets
        for msg in targets:
            blob = meta_map.get(msg.get('media_item_id'))
            if not blob:
                continue
            
            # Enhanced extraction: analyze more tags and longer content
            parts = []
            quoted_content = None  # For longer content in specific tags
            i = 0
            while i < len(blob) - 2:
                b = blob[i]
                if (b & 7) == 2 and i + 1 < len(blob):
                    tag = b >> 3
                    length = blob[i + 1]
                    data = blob[i + 2:i + 2 + length]
                    i += 2 + length
                    
                    # Original algorithm: tags 5,6,9,13,14 with length 10-130
                    if 10 < length < 130 and tag in (5, 6, 9, 13, 14):
                        try:
                            text = data.decode('utf-8', 'ignore').strip()
                            if text:
                                parts.append(text)
                        except:
                            pass
                    # Enhanced: check tag 1 for longer quoted content (like "bons élèves" case)
                    elif tag == 1 and 50 < length < 500:  # Reasonable range for quoted messages
                        try:
                            text = data.decode('utf-8', 'ignore').strip()
                            # Look for quoted message patterns
                            if (text and len(text) > 20 and 
                                any(word in text.lower() for word in ['que', 'je', 'tu', 'il', 'elle', 'on', 'nous', 'vous', 'ils'])):
                                quoted_content = text[:200]  # Take first 200 chars
                        except:
                            pass
                    # Enhanced: check tags 1-4 for other potential content
                    elif tag in (2, 3, 4) and 15 < length < 200:
                        try:
                            text = data.decode('utf-8', 'ignore').strip()
                            if text and len(text) > 15:
                                parts.append(text)
                        except:
                            pass
                else:
                    i += 1
            
            # Enhanced matching logic
            if len(parts) >= 2 or quoted_content:
                # Use quoted_content if we have it and parts are insufficient
                if quoted_content and len(parts) < 2:
                    # Direct matching with quoted_content
                    best_match = self._find_matching_message_by_content(quoted_content, msg)
                    if best_match:
                        content = best_match['content']
                        if len(content) > 90:
                            words = content[:90].split()
                            content = ' '.join(words[:-1]) + '...' if len(words) > 1 else content[:85] + '...'
                        msg['quoted_text'] = content
                        continue
                
                # Original algorithm continues here if we have enough parts
                if len(parts) < 2:
                    continue
            
            # Find matching original
            reconstruction = ' '.join(parts)
            best_match = None
            best_delta = None
            
            for key, candidates in originals.items():
                match_found = any(len(part) > 15 and part in key for part in parts)
                if not match_found and key[:25] in reconstruction:
                    match_found = True
                
                if match_found:
                    for candidate in candidates:
                        if (candidate.get('is_from_me') == msg.get('is_from_me') or
                            not candidate.get('date') or not msg.get('date')):
                            continue
                        
                        try:
                            from datetime import datetime
                            t1 = datetime.strptime(candidate['date'], '%Y-%m-%d %H:%M:%S')
                            t2 = datetime.strptime(msg['date'], '%Y-%m-%d %H:%M:%S')
                            if t1 >= t2:
                                continue
                            
                            delta = (t2 - t1).total_seconds()
                            if delta > 48 * 3600:
                                continue
                            
                            if best_delta is None or delta < best_delta:
                                best_match = candidate
                                best_delta = delta
                        except:
                            continue
            
            # Apply quote
            if best_match and not msg.get('quoted_text'):
                content = best_match['content']
                if len(content) > 90:
                    words = content[:90].split()
                    content = ' '.join(words[:-1]) + '...' if len(words) > 1 else content[:85] + '...'
                msg['quoted_text'] = content
    
    def _find_matching_message_by_content(self, quoted_content, reply_msg):
        """Find a message that matches quoted content directly."""
        # Clean quoted content for matching
        clean_quoted = quoted_content.lower().strip()
        
        for candidate in self.messages:
            if not candidate.get('content'):
                continue
                
            # Skip if same author (can't quote yourself in this context)
            if candidate.get('is_from_me') == reply_msg.get('is_from_me'):
                continue
                
            # Check temporal ordering and proximity
            if not candidate.get('date') or not reply_msg.get('date'):
                continue
                
            try:
                from datetime import datetime
                t1 = datetime.strptime(candidate['date'], '%Y-%m-%d %H:%M:%S')
                t2 = datetime.strptime(reply_msg['date'], '%Y-%m-%d %H:%M:%S')
                
                # Candidate must be before reply
                if t1 >= t2:
                    continue
                    
                # Must be within reasonable time window (48 hours)
                delta = (t2 - t1).total_seconds()
                if delta > 48 * 3600:
                    continue
                    
                # Check content similarity
                candidate_content = candidate['content'].lower().strip()
                
                # Direct substring match (quoted content should be subset of original)
                if clean_quoted[:50] in candidate_content:
                    return candidate
                    
                # Fuzzy matching: check if significant words overlap
                quoted_words = set(clean_quoted.split())
                candidate_words = set(candidate_content.split())
                
                # Remove common words
                common_words = {'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'ou', 'que', 'qui', 'je', 'tu', 'il', 'elle', 'on', 'nous', 'vous', 'ils', 'elles', 'ce', 'ca', 'ça'}
                quoted_words -= common_words
                candidate_words -= common_words
                
                if len(quoted_words) > 3 and len(candidate_words) > 3:
                    overlap = len(quoted_words.intersection(candidate_words))
                    if overlap >= min(3, len(quoted_words) * 0.6):
                        return candidate
                        
            except Exception:
                continue
                
        return None
    
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