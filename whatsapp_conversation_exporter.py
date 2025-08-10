#!/usr/bin/env python3
"""
WhatsApp Conversation Exporter - Simplified Version
==================================================

Exports WhatsApp conversations with citations, forwards, and reactions.

Usage:
    python whatsapp_conversation_exporter.py --contact "Name"
    python whatsapp_conversation_exporter.py --limit 100

Author: Damien Le Borgne & AI Assistant
Date: August 2025
"""

import sqlite3
import os
import sys
import re
from datetime import datetime


class ForwardInfo:
    def __init__(self, hash_id):
        self.hash_id = hash_id


class WhatsAppExporter:
    def __init__(self, db_path=None, backup_mode=False, backup_base_path=None):
        """Initialize with WhatsApp database.
        
        Args:
            db_path: Custom database path
            backup_mode: Use iOS backup extracted by wtsexporter instead of local WhatsApp
            backup_base_path: Base path for wtsexporter output (default: ../working_wts)
        """
        self.backup_mode = backup_mode
        self.backup_base_path = backup_base_path or "../working_wts"
        
        if backup_mode:
            self.db_path = db_path or self._find_backup_database()
            self.media_base_path = os.path.join(self.backup_base_path, "AppDomainGroup-group.net.whatsapp.WhatsApp.shared/Message/Media")
        else:
            self.db_path = db_path or self._find_database()
            self.media_base_path = os.path.expanduser("~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/Message")
            
        self.contact_cache = {}
        print(f"📁 Database: {self.db_path}")
        print(f"📂 Media base: {self.media_base_path}")
    
    def _find_backup_database(self):
        """Find wtsexporter database."""
        backup_db_path = os.path.join(self.backup_base_path, "7c7fba66680ef796b916b067077cc246adacf01d")
        
        print("🔍 Looking for wtsexporter database...")
        
        if os.path.exists(backup_db_path):
            print(f"✅ Found backup database: {backup_db_path}")
            return backup_db_path
        else:
            print(f"⚠️ Using backup path: {backup_db_path}")
            return backup_db_path
    
    def _find_database(self):
        """Find WhatsApp database."""
        standard_path = os.path.expanduser("~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite")
        fallback_path = "7c7fba66680ef796b916b067077cc246adacf01d"
        
        print("🔍 Looking for WhatsApp database...")
        
        if os.path.exists(standard_path):
            print(f"✅ Found database: {standard_path}")
            return standard_path
        elif os.path.exists(fallback_path):
            print(f"✅ Found database: {fallback_path}")
            return fallback_path
        else:
            print(f"⚠️ Using standard path: {standard_path}")
            return standard_path
    
    def _get_contact_name(self, jid):
        """Get contact name from JID."""
        if not jid or jid in self.contact_cache:
            return self.contact_cache.get(jid, "Unknown")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT ZPARTNERNAME FROM ZWACHATSESSION WHERE ZCONTACTJID = ?", (jid,))
                result = cursor.fetchone()
                
                if result and result[0]:
                    name = result[0]
                else:
                    name = f"Contact ({jid.split('@')[0]})" if '@' in jid else jid
                
                self.contact_cache[jid] = name
                return name
        except Exception:
            self.contact_cache[jid] = jid
            return jid
    
    def _convert_timestamp(self, timestamp):
        """Convert WhatsApp timestamp."""
        if not timestamp:
            return None
        try:
            return datetime.fromtimestamp(timestamp + 978307200).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return None
    
    def _decode_reaction(self, blob, is_group=False, group_jid=None):
        """Decode emoji reaction from blob."""
        if not blob:
            return None
        try:
            hex_data = blob.hex().upper()
            
            # Find emoji with automatic modifier detection
            emoji = None
            if 'F09F' in hex_data:
                # Modern emojis (F09F prefix) - may have skin tone modifiers
                base_matches = re.findall(r'F09F[0-9A-F]{4}', hex_data)
                if base_matches:
                    # Check for skin tone modifier after base emoji
                    base_emoji = base_matches[0]
                    base_pos = hex_data.find(base_emoji)
                    remaining = hex_data[base_pos + len(base_emoji):]
                    
                    # Look for skin tone modifier (F09F8F[BB-BF])
                    skin_modifier = re.match(r'F09F8F(BB|BC|BD|BE|BF)', remaining)
                    if skin_modifier:
                        full_sequence = base_emoji + skin_modifier.group(0)
                        emoji = bytes.fromhex(full_sequence).decode('utf-8')
                    else:
                        emoji = bytes.fromhex(base_emoji).decode('utf-8')
                        
            elif hex_data.startswith('E2') or 'E2' in hex_data:
                # Legacy Unicode symbols (E2xx prefix) - may have color modifiers
                base_matches = re.findall(r'E2[0-9A-F]{4}', hex_data)
                if base_matches:
                    base_emoji = base_matches[0]
                    base_pos = hex_data.find(base_emoji)
                    remaining = hex_data[base_pos + len(base_emoji):]
                    
                    # Look for color modifier (EFB8[8F-AB])
                    color_modifier = re.match(r'EFB8[8-9A-B][0-9A-F]', remaining)
                    if color_modifier:
                        full_sequence = base_emoji + color_modifier.group(0)
                        emoji = bytes.fromhex(full_sequence).decode('utf-8')
                    else:
                        emoji = bytes.fromhex(base_emoji).decode('utf-8')
            
            if not emoji:
                return None
            
            # For groups, try to extract who reacted
            if is_group:
                return self._decode_group_reactions(hex_data, emoji, group_jid)
            else:
                return emoji
                
        except Exception:
            pass
        return None
    
    def _decode_group_reactions(self, hex_data, emoji, group_jid=None):
        """Decode group reactions with person names."""
        try:
            # Find JID patterns in hex data
            jid_matches = re.findall(r'333[0-9A-F]+?40732E77686174736170702E6E6574', hex_data)
            
            if not jid_matches:
                return emoji
            
            reactors = []
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
                        
                        # Get name and create unique initials for this group
                        name = self._get_contact_name(clean_jid)
                        if name and name != clean_jid and 'Contact (' not in name:
                            if group_jid:
                                initials = self._get_group_initials_for_jid(group_jid, clean_jid)
                            else:
                                initials = self._get_initials(name)
                            reactors.append(initials)
                except:
                    continue
            
            if reactors:
                # Remove duplicates while preserving order
                unique_reactors = []
                for reactor in reactors:
                    if reactor not in unique_reactors:
                        unique_reactors.append(reactor)
                
                if len(unique_reactors) == 1:
                    return f"[{unique_reactors[0]}:{emoji}]"
                else:
                    reactor_list = ';'.join([f"{r}:{emoji}" for r in unique_reactors])
                    return f"[{reactor_list}]"
            
            return emoji
            
        except Exception:
            return emoji
    
    def _get_initials(self, name):
        """Generate initials from a name."""
        if not name:
            return "?"
        
        # Split name and take first letter of each word
        words = name.split()
        initials = ''.join([word[0].upper() for word in words if word])
        
        # Limit to 3 characters max
        return initials[:3] if initials else "?"
    
    def _get_group_unique_initials(self, group_jid):
        """Generate unique initials for all members of a group."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get all group members with their names
                cursor.execute("""
                    SELECT gm.ZMEMBERJID, cs.ZPARTNERNAME
                    FROM ZWAGROUPMEMBER gm
                    LEFT JOIN ZWACHATSESSION cs ON gm.ZMEMBERJID = cs.ZCONTACTJID
                    LEFT JOIN ZWACHATSESSION gs ON gs.ZCONTACTJID = ?
                    WHERE gm.ZCHATSESSION = gs.Z_PK
                    AND cs.ZPARTNERNAME IS NOT NULL
                    AND cs.ZPARTNERNAME != ''
                """, (group_jid,))
                
                members = cursor.fetchall()
                
                # Create mapping of JID to name
                jid_to_name = {}
                for jid, name in members:
                    if jid and name:
                        jid_to_name[jid] = name
                
                # Generate initial initials
                name_to_initials = {}
                initials_count = {}
                
                for jid, name in jid_to_name.items():
                    basic_initials = self._get_initials(name)
                    name_to_initials[name] = basic_initials
                    initials_count[basic_initials] = initials_count.get(basic_initials, 0) + 1
                
                # Resolve conflicts by using more letters from first names
                final_initials = {}
                for name, initials in name_to_initials.items():
                    if initials_count[initials] > 1:
                        # There's a conflict, need to make unique
                        words = name.split()
                        if len(words) >= 2:
                            # Use beginning of first name + initials of last names
                            first_name = words[0]
                            last_names = words[1:]  # All words after first name
                            
                            # Take first letter (uppercase) + rest lowercase from first name
                            # Then uppercase first letter of each last name
                            first_part = first_name[0].upper() + first_name[1:2].lower()
                            last_part = ''.join([word[0].upper() for word in last_names])
                            
                            unique_initials = first_part + last_part
                            
                            # If still conflict, add more characters from first name
                            counter = 3
                            base_unique = unique_initials
                            while unique_initials in final_initials.values():
                                if len(first_name) > counter - 1:
                                    first_part = first_name[0].upper() + first_name[1:counter].lower()
                                    unique_initials = first_part + last_part
                                    counter += 1
                                else:
                                    # Fallback: add numbers
                                    unique_initials = base_unique + str(counter-2)
                                    counter += 1
                            
                            final_initials[name] = unique_initials
                        else:
                            final_initials[name] = initials
                    else:
                        final_initials[name] = initials
                
                # Create reverse mapping: JID to unique initials
                jid_to_initials = {}
                for jid, name in jid_to_name.items():
                    jid_to_initials[jid] = final_initials.get(name, "?")
                
                return jid_to_initials
                
        except Exception as e:
            print(f"Error generating group initials: {e}")
            return {}
    
    def _get_group_initials_for_jid(self, group_jid, member_jid):
        """Get unique initials for a specific member in a group."""
        # Cache group initials to avoid recalculating
        cache_key = f"group_initials_{group_jid}"
        if not hasattr(self, '_group_initials_cache'):
            self._group_initials_cache = {}
        
        if cache_key not in self._group_initials_cache:
            self._group_initials_cache[cache_key] = self._get_group_unique_initials(group_jid)
        
        return self._group_initials_cache[cache_key].get(member_jid, "?")
    
    def _get_media_type_name(self, message_type):
        """Get human-readable media type name."""
        media_types = {
            1: "Image",
            2: "Video",  # MP4 files
            3: "Audio",  # Audio files
            5: "Location",
            9: "Document",
            13: "GIF",
            14: "Sticker"
        }
        return media_types.get(message_type, "Media")
    
    def _prepare_media_path(self, contact_name, media_info):
        """Prepare media path and copy file if needed."""
        if not media_info or not media_info.get('local_path'):
            return None
            
        original_path = media_info['local_path']
        
        # Create media directory structure
        safe_contact_name = "".join(c for c in contact_name if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
        media_dir = f"conversations/media/{safe_contact_name}"
        
        if not os.path.exists(media_dir):
            os.makedirs(media_dir, exist_ok=True)
        
        # Extract filename from original path
        filename = os.path.basename(original_path)
        if not filename:
            # Generate filename from UUID in path
            import re
            uuid_match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\.\w+)', original_path)
            if uuid_match:
                filename = uuid_match.group(1)
            else:
                filename = f"media_{media_info.get('message_type', 'unknown')}.unknown"
        
        relative_path = f"media/{safe_contact_name}/{filename}"
        full_target_path = f"conversations/{relative_path}"
        
        # Determine source path based on mode
        if self.backup_mode:
            # For backup mode, media are organized by contact JID
            # Extract contact JID from the path or use a mapping
            full_source_path = self._get_backup_media_path(original_path, contact_name)
        else:
            # Local WhatsApp mode
            full_source_path = os.path.join(self.media_base_path, original_path)
        
        try:
            if full_source_path and os.path.exists(full_source_path) and not os.path.exists(full_target_path):
                import shutil
                shutil.copy2(full_source_path, full_target_path)
                print(f"   📎 Copied media: {filename}")
            elif os.path.exists(full_target_path):
                print(f"   📎 Media exists: {filename}")
            else:
                print(f"   📎 Media not found: {filename}")
        except Exception as e:
            print(f"   ⚠️ Could not copy media {filename}: {e}")
        
        return relative_path
    
    def _get_backup_media_path(self, original_path, contact_name):
        """Get backup media path for wtsexporter extracted files."""
        # In backup mode, we need to find the contact JID and map it to the media path
        # The original_path might be like: "Media/33689523939-1443423912@g.us/b/3/filename.jpg"
        # But in backup extraction, it's organized by contact JID: "33614712671@s.whatsapp.net/filename.jpg"
        
        # Extract filename from original path
        filename = os.path.basename(original_path)
        if not filename:
            return None
        
        # We need to find the contact JID for this contact name
        # This is a simplified approach - in real usage, you might need a more sophisticated mapping
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Find contact JID by name
                cursor.execute("SELECT ZCONTACTJID FROM ZWACHATSESSION WHERE ZPARTNERNAME = ?", (contact_name,))
                result = cursor.fetchone()
                if result:
                    contact_jid = result[0]
                    # For groups, convert group JID to individual JID pattern
                    if '@g.us' in contact_jid:
                        # Group - use group JID as folder name
                        jid_folder = contact_jid
                    else:
                        # Individual contact - use contact JID
                        jid_folder = contact_jid
                    
                    # Try to find the file in the backup media structure
                    possible_paths = [
                        os.path.join(self.media_base_path, jid_folder, filename),
                        os.path.join(self.media_base_path, contact_jid, filename),
                        # If direct mapping fails, try to find it by scanning
                    ]
                    
                    for path in possible_paths:
                        if os.path.exists(path):
                            return path
                    
                    # Last resort: scan the media directory for the filename
                    return self._find_media_in_backup(filename)
        except Exception:
            pass
        
        return None
    
    def _find_media_in_backup(self, filename):
        """Find media file in backup directory by scanning."""
        if not os.path.exists(self.media_base_path):
            return None
        
        try:
            for root, dirs, files in os.walk(self.media_base_path):
                if filename in files:
                    return os.path.join(root, filename)
        except Exception:
            pass
        
        return None
    
    def _extract_quoted_text(self, cursor, media_item_id):
        """Extract quoted text from media metadata."""
        try:
            # First, try to get the media info itself (for media quotes)
            cursor.execute("SELECT ZMEDIALOCALPATH, ZTITLE, ZMESSAGE FROM ZWAMEDIAITEM WHERE Z_PK = ?", (media_item_id,))
            media_result = cursor.fetchone()
            
            if media_result and media_result[0]:  # Has media path
                media_path = media_result[0]
                media_title = media_result[1]
                
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
            cursor.execute("SELECT ZMETADATA FROM ZWAMEDIAITEM WHERE Z_PK = ?", (media_item_id,))
            result = cursor.fetchone()
            if not result or not result[0]:
                return None
            
            blob = result[0]
            i = 0
            
            while i < len(blob) - 2:
                tag_byte = blob[i]
                if (tag_byte & 0x7) == 2:  # Length-delimited field
                    tag = tag_byte >> 3
                    length = blob[i + 1]
                    
                    if i + 2 + length <= len(blob) and length > 2 and tag == 1:
                        field_data = blob[i + 2:i + 2 + length]
                        try:
                            text = field_data.decode('utf-8', errors='ignore').strip()
                            text = re.sub(r'[\x00-\x1f]+', '', text)
                            
                            if len(text) > 3:
                                # Check for forward hash (only if it really looks like one)
                                sanitized = re.sub(r"[^A-Za-z0-9'`{}]", "", text)
                                if (len(sanitized) > 10 and 
                                    re.fullmatch(r"[A-Za-z0-9]{2,24}['`][A-Za-z0-9{}]{2,48}", sanitized) and
                                    any(c.isdigit() or c in '{}' or (c.isalpha() and c.isupper()) for c in sanitized)):
                                    return ForwardInfo(sanitized)
                                
                                # Regular quote - be more permissive
                                if len(text) > 3:  # Lower threshold
                                    if len(text) > 50:
                                        words = text[:50].split()
                                        text = ' '.join(words[:-1]) + "..." if len(words) > 1 else text[:50] + "..."
                                    return text
                        except Exception:
                            pass
                    
                    i += 2 + length if i + 2 + length <= len(blob) else i + 1
                else:
                    i += 1
            
            # Last resort: if we reach here, there's no actual quoted content
            return None
            
        except Exception:
            return None
    
    def _parse_metadata_replies(self, cursor, targets):
        """Parse metadata to find reply relationships."""
        if not targets:
            return
        
        # Get metadata
        media_ids = [m['_media_item_id'] for m in targets if m.get('_media_item_id')]
        if not media_ids:
            return
        
        placeholders = ','.join(['?'] * len(media_ids))
        cursor.execute(f"SELECT Z_PK,ZMETADATA FROM ZWAMEDIAITEM WHERE Z_PK IN ({placeholders})", media_ids)
        meta_map = {r[0]: r[1] for r in cursor.fetchall() if r[1]}
        
        # Index original messages
        originals = {}
        for m in self.messages:
            text = (m.get('content') or '').strip()
            if len(text) >= 40:
                originals.setdefault(text[:60], []).append(m)
        
        # Process targets
        for msg in targets:
            blob = meta_map.get(msg.get('_media_item_id'))
            if not blob:
                continue
            
            # Extract fragments from tags 5,6,9,13,14
            parts = []
            i = 0
            while i < len(blob) - 2:
                b = blob[i]
                if (b & 7) == 2 and i + 1 < len(blob):
                    tag = b >> 3
                    length = blob[i + 1]
                    data = blob[i + 2:i + 2 + length]
                    i += 2 + length
                    
                    if 10 < length < 130 and tag in (5, 6, 9, 13, 14):
                        try:
                            text = data.decode('utf-8', 'ignore').strip()
                            if text:
                                parts.append(text)
                        except:
                            pass
                else:
                    i += 1
            
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
    
                msg['quoted_text'] = content
    
    def get_contacts_with_reactions(self):
        """Get contacts with reactions."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
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
                
                contacts = []
                for jid, count in cursor.fetchall():
                    if jid:
                        contacts.append({
                            'jid': jid,
                            'name': self._get_contact_name(jid),
                            'reaction_count': count
                        })
                return contacts
        except Exception as e:
            print(f"❌ Error getting contacts: {e}")
            return []
    
    def get_all_contacts(self):
        """Get all contacts and groups."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT ZCONTACTJID, ZPARTNERNAME
                    FROM ZWACHATSESSION 
                    WHERE ZCONTACTJID IS NOT NULL
                    AND ZPARTNERNAME IS NOT NULL
                    AND ZPARTNERNAME != ''
                    ORDER BY ZPARTNERNAME
                """)
                
                contacts = []
                for jid, name in cursor.fetchall():
                    if jid and name:
                        contacts.append({
                            'jid': jid,
                            'name': name,
                            'reaction_count': 0  # Default value
                        })
                return contacts
        except Exception as e:
            print(f"❌ Error getting all contacts: {e}")
            return []
    
    def get_conversation(self, contact_jid, limit=None, recent=False):
        """Get conversation with all features including media."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if this is a group conversation
                is_group = contact_jid.endswith('@g.us')
                
                if is_group:
                    # Group conversation query with sender names and media
                    query = """
                        SELECT 
                            m.Z_PK, m.ZTEXT, m.ZMESSAGEDATE, m.ZFROMJID, m.ZTOJID,
                            m.ZISFROMME, m.ZFLAGS, i.ZRECEIPTINFO, m.ZPARENTMESSAGE, m.ZMEDIAITEM,
                            cs.ZPARTNERNAME, gm.ZMEMBERJID, m.ZMESSAGETYPE,
                            mi.ZMEDIALOCALPATH, mi.ZTITLE, mi.ZFILESIZE
                        FROM ZWAMESSAGE m
                        LEFT JOIN ZWAMESSAGEINFO i ON m.Z_PK = i.ZMESSAGE
                        LEFT JOIN ZWAGROUPMEMBER gm ON m.ZGROUPMEMBER = gm.Z_PK
                        LEFT JOIN ZWACHATSESSION cs ON gm.ZMEMBERJID = cs.ZCONTACTJID
                        LEFT JOIN ZWAMEDIAITEM mi ON m.ZMEDIAITEM = mi.Z_PK
                        WHERE (m.ZFROMJID = ? OR m.ZTOJID = ?)
                        AND m.ZMESSAGETYPE IN (0, 1, 2, 3, 5, 9, 13, 14)
                        AND (m.ZTEXT IS NOT NULL OR m.ZMEDIAITEM IS NOT NULL)
                        ORDER BY m.ZMESSAGEDATE {}
                    """.format("DESC" if recent else "ASC")
                else:
                    # Individual conversation query with media
                    query = """
                        SELECT 
                            m.Z_PK, m.ZTEXT, m.ZMESSAGEDATE, m.ZFROMJID, m.ZTOJID,
                            m.ZISFROMME, m.ZFLAGS, i.ZRECEIPTINFO, m.ZPARENTMESSAGE, m.ZMEDIAITEM,
                            NULL, NULL, m.ZMESSAGETYPE,
                            mi.ZMEDIALOCALPATH, mi.ZTITLE, mi.ZFILESIZE
                        FROM ZWAMESSAGE m
                        LEFT JOIN ZWAMESSAGEINFO i ON m.Z_PK = i.ZMESSAGE
                        LEFT JOIN ZWAMEDIAITEM mi ON m.ZMEDIAITEM = mi.Z_PK
                        WHERE (m.ZFROMJID = ? OR m.ZTOJID = ?)
                        AND m.ZMESSAGETYPE IN (0, 1, 2, 3, 5, 9, 13, 14)
                        AND (m.ZTEXT IS NOT NULL OR m.ZMEDIAITEM IS NOT NULL)
                        ORDER BY m.ZMESSAGEDATE {}
                    """.format("DESC" if recent else "ASC")
                
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query, (contact_jid, contact_jid))
                rows = cursor.fetchall()
                
                # If recent=True, reverse the order to maintain chronological display
                if recent:
                    rows = list(reversed(rows))
                
                print(f"📋 Found {len(rows)} messages...")
                
                # Collect all messages
                self.messages = []
                message_lookup = {}
                
                for row in rows:
                    # Decode reaction
                    reaction_emoji = None
                    if row[7]:
                        reaction_emoji = self._decode_reaction(row[7], is_group, contact_jid if is_group else None)
                    
                    # Extract quoted text - only for messages that are actually quotes/replies
                    quoted_text = None
                    if row[8]:  # parent_message_id exists - this is definitely a reply
                        if row[9]:  # has media_item_id, try to extract from metadata
                            quoted_text = self._extract_quoted_text(cursor, row[9])
                            if isinstance(quoted_text, ForwardInfo):
                                quoted_text = None  # Don't show forward hashes as quotes
                    
                    flags = row[6] or 0
                    is_forwarded = bool(flags & 0x180 == 0x180)
                    
                    # For groups, get sender name
                    sender_name = None
                    if is_group and not bool(row[5]):  # Not from me
                        sender_name = row[10]  # ZPARTNERNAME from the join
                    
                    # Handle media
                    media_info = None
                    if row[9]:  # has media_item_id
                        # Only create media_info if there's actual media content
                        # (local_path exists, or file_size > 0, or title exists)
                        if row[13] or (row[15] and row[15] > 0) or (row[14] and row[14].strip()):
                            media_info = {
                                'local_path': row[13],
                                'title': row[14],
                                'file_size': row[15],
                                'message_type': row[12]
                            }
                    
                    message = {
                        'message_id': row[0],
                        'content': row[1],
                        'date': self._convert_timestamp(row[2]),
                        'from_jid': row[3],
                        'to_jid': row[4],
                        'is_from_me': bool(row[5]),
                        'reaction_emoji': reaction_emoji,
                        'parent_message_id': row[8],
                        'quoted_text': quoted_text,
                        'is_forwarded': is_forwarded,
                        'sender_name': sender_name,
                        '_media_item_id': row[9],
                        'message_type': row[12],
                        'media_info': media_info
                    }
                    self.messages.append(message)
                    message_lookup[message['message_id']] = message
                
                # Resolve parent message quotes
                for message in self.messages:
                    if (not message['quoted_text'] and message['parent_message_id'] 
                        and message['parent_message_id'] in message_lookup):
                        parent_msg = message_lookup[message['parent_message_id']]
                        quoted_content = parent_msg['content'][:50]
                        if len(parent_msg['content']) > 50:
                            quoted_content += "..."
                        message['quoted_text'] = quoted_content
                
                # Parse metadata for replies
                reply_targets = [m for m in self.messages 
                               if not m.get('quoted_text') and not m.get('parent_message_id') and m.get('_media_item_id')]
                self._parse_metadata_replies(cursor, reply_targets)
                
                # Remove duplicate forwards
                seen_forwards = set()
                final_messages = []
                for msg in self.messages:
                    if msg.get('is_forwarded'):
                        forward_key = (msg['content'], msg['date'])
                        if forward_key in seen_forwards:
                            continue
                        seen_forwards.add(forward_key)
                    final_messages.append(msg)
                
                return final_messages
                
        except Exception as e:
            print(f"❌ Database error: {e}")
            return []
    
    def format_conversation(self, messages, contact_name):
        """Format conversation for export."""
        if not messages:
            return "No messages found."
        
        output = []
        output.append("=" * 80)
        output.append(f"WhatsApp Conversation Export")
        output.append(f"Contact: {contact_name}")
        output.append(f"Messages: {len(messages)}")
        output.append(f"Date Range: {messages[0]['date']} to {messages[-1]['date']}")
        output.append(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output.append("=" * 80)
        output.append("")
        
        current_date = None
        for msg in messages:
            message_date = msg['date']
            if not message_date:
                continue
                
            # Date separator
            try:
                msg_date_part = message_date.split(' ')[0]
                if current_date != msg_date_part:
                    current_date = msg_date_part
                    output.append(f"\n--- {current_date} ---\n")
            except:
                pass
            
            # Time and sender
            try:
                time_part = message_date.split(' ')[1]
            except:
                time_part = "??:??"
            
            prefix = ">" if msg['is_from_me'] else "<"
            
            # For group messages, add sender name
            sender_prefix = ""
            if msg.get('sender_name') and not msg['is_from_me']:
                sender_prefix = f"{msg['sender_name']}: "
            
            # Handle quoted messages
            if msg.get('quoted_text'):
                citation = msg.get('quoted_text')
                
                # Format citation directly after timestamp
                if isinstance(citation, ForwardInfo):
                    citation_line = f"[{time_part}] ↳ (forwarded id {citation.hash_id})"
                else:
                    lines = citation.split('\n')
                    citation_line = f"[{time_part}] ↳ {lines[0]}"
                    
                output.append(citation_line)
                
                # Add additional citation lines if multi-line
                if not isinstance(citation, ForwardInfo):
                    lines = citation.split('\n')
                    if len(lines) > 1:
                        for extra in lines[1:]:
                            # Indent to align with the arrow
                            output.append(f"           {extra}")
                
                # Handle media in quoted messages
                if msg.get('media_info'):
                    media_type = self._get_media_type_name(msg['media_info'].get('message_type', 0))
                    size_kb = msg['media_info'].get('file_size', 0) // 1024 if msg['media_info'].get('file_size') else 0
                    
                    # Check if media file exists locally
                    media_path = self._prepare_media_path(contact_name, msg['media_info'])
                    
                    # Use markdown link format for better VS Code support
                    if media_path:
                        filename = os.path.basename(media_path)
                        media_line = f"           📎 {media_type}: [{filename}](./{media_path})"
                    else:
                        media_line = f"           📎 {media_type}: [Not downloaded]"
                    
                    if size_kb > 0:
                        media_line += f" ({size_kb} KB)"
                    if msg['media_info'].get('title'):
                        media_line += f" - {msg['media_info']['title']}"
                    output.append(media_line)
                
                # Add the reply message below with proper indentation and sender prefix
                reply_content = msg['content'] or ''
                if reply_content.strip():
                    message_line = f"           {prefix} {sender_prefix}{reply_content}"
                    if msg['reaction_emoji']:
                        message_line += f" {msg['reaction_emoji']}"
                    output.append(message_line)
            else:
                # Regular message - handle media first, then text
                if msg.get('media_info'):
                    # Always show media with its filename
                    media_type = self._get_media_type_name(msg['media_info'].get('message_type', 0))
                    size_kb = msg['media_info'].get('file_size', 0) // 1024 if msg['media_info'].get('file_size') else 0
                    
                    # Check if media file exists locally
                    media_path = self._prepare_media_path(contact_name, msg['media_info'])
                    
                    # Use markdown link format for better VS Code support
                    if media_path:
                        # Media downloaded and available
                        filename = os.path.basename(media_path)
                        message_line = f"[{time_part}] {prefix} {sender_prefix}📎 {media_type}: [{filename}](./{media_path})"
                    else:
                        # Media not downloaded locally
                        message_line = f"[{time_part}] {prefix} {sender_prefix}📎 {media_type}: [Not downloaded]"
                    
                    if size_kb > 0:
                        message_line += f" ({size_kb} KB)"
                    if msg['media_info'].get('title'):
                        message_line += f" - {msg['media_info']['title']}"
                    if msg['reaction_emoji']:
                        message_line += f" {msg['reaction_emoji']}"
                    
                    output.append(message_line)
                    
                    # Add content as separate comment line if it exists
                    content = msg['content'] or ''
                    if msg.get('is_forwarded'):
                        content = f"(forward) {content}"
                    
                    if content.strip():
                        comment_line = f"    💬 {content}"
                        output.append(comment_line)
                        
                elif msg['content'] and msg['content'].strip():
                    # Text-only message (no media)
                    content = msg['content']
                    if msg.get('is_forwarded'):
                        content = f"(forward) {content}"
                    message_line = f"[{time_part}] {prefix} {sender_prefix}{content}"
                    if msg['reaction_emoji']:
                        message_line += f" {msg['reaction_emoji']}"
                    output.append(message_line)
                else:
                    # This should never happen - warn about completely empty messages
                    if not msg.get('media_info') and not (msg['content'] and msg['content'].strip()):
                        print(f"⚠️ Warning: Empty message found (ID: {msg.get('message_id')}, Type: {msg.get('message_type')})")
                        # Still show it with a placeholder to avoid losing data
                        output.append(f"[{time_part}] {prefix} {sender_prefix}[Empty message - Type {msg.get('message_type', '?')}]")
        
        # Stats
        output.append("")
        output.append("=" * 80)
        reaction_count = sum(1 for msg in messages if msg['reaction_emoji'])
        output.append(f"📊 Total messages: {len(messages)}")
        output.append(f"🎯 Messages with reactions: {reaction_count}")
        
        if reaction_count > 0:
            emoji_counts = {}
            for msg in messages:
                if msg['reaction_emoji']:
                    emoji = msg['reaction_emoji']
                    emoji_counts[emoji] = emoji_counts.get(emoji, 0) + 1
            
            output.append(f"😊 Unique emoji types: {len(emoji_counts)}")
            output.append("\nReaction breakdown:")
            for emoji, count in sorted(emoji_counts.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / reaction_count) * 100
                output.append(f"  {emoji}: {count} times ({percentage:.1f}%)")
        
        output.append("=" * 80)
        return "\n".join(output)
    
    def export_conversation(self, contact_name_or_jid, output_file=None, limit=None, recent=False):
        """Export conversation to file."""
        print(f"🔍 Looking for contact: {contact_name_or_jid}")
        
        # Create directory
        conversations_dir = "conversations"
        if not os.path.exists(conversations_dir):
            os.makedirs(conversations_dir)
            print(f"📁 Created directory: {conversations_dir}")
        
        # Find contact
        contacts = self.get_all_contacts()
        target_contact = None
        
        for contact in contacts:
            if (contact['name'].lower() == contact_name_or_jid.lower() or 
                contact['jid'] == contact_name_or_jid):
                target_contact = contact
                break
        
        if not target_contact:
            print(f"❌ Contact '{contact_name_or_jid}' not found.")
            print("Available contacts with reactions:")
            # Show contacts with reactions for fallback
            reaction_contacts = self.get_contacts_with_reactions()
            for i, contact in enumerate(reaction_contacts[:10], 1):
                print(f"  {i}. {contact['name']}")
            return None
        
        print(f"✅ Found contact: {target_contact['name']} ({target_contact['jid']})")
        
        # Get messages
        messages = self.get_conversation(target_contact['jid'], limit, recent)
        if not messages:
            print(f"❌ No messages found for {target_contact['name']}")
            return None
        
        # Generate filename
        if not output_file:
            safe_name = "".join(c for c in target_contact['name'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            suffix = "_recent" if recent else ""
            output_file = os.path.join(conversations_dir, f"whatsapp_conversation_{safe_name}{suffix}_{timestamp}.md")
        else:
            output_file = os.path.join(conversations_dir, os.path.basename(output_file))
        
        # Export
        formatted_text = self.format_conversation(messages, target_contact['name'])
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(formatted_text)
            
            print(f"✅ Conversation exported to: {output_file}")
            print(f"📄 File size: {os.path.getsize(output_file)} bytes")
            return output_file
            
        except Exception as e:
            print(f"❌ Error writing file: {e}")
            return None


def main():
    """Main function."""
    print("💬 WHATSAPP CONVERSATION EXPORTER")
    print("=" * 60)
    print("📝 Export conversations with citations, forwards, and reactions")
    print()
    
    # If no arguments provided, run interactive mode
    if len(sys.argv) == 1:
        print("🔧 INTERACTIVE MODE")
        print("=" * 40)
        print("Choose data source:")
        print("1. 📱 Local WhatsApp client data")
        print("2. 📦 iOS backup extracted by wtsexporter")
        print()
        
        while True:
            choice = input("Enter choice (1 or 2): ").strip()
            if choice == "1":
                backup_mode = False
                backup_path = None
                print("✅ Using local WhatsApp client data")
                break
            elif choice == "2":
                backup_mode = True
                default_path = "../wtsexport"
                print(f"📂 Default backup path: {default_path}")
                user_path = input(f"Enter backup path (or press Enter for default): ").strip()
                backup_path = user_path if user_path else default_path
                print(f"✅ Using backup data from: {backup_path}")
                break
            else:
                print("❌ Invalid choice. Please enter 1 or 2.")
        
        print()
        print("📋 Available options for contact export:")
        print("   • Leave empty to export all contacts")
        print("   • Enter contact name for specific export")
        print()
        
        contact_name = input("Enter contact name (or press Enter for all): ").strip()
        if not contact_name:
            contact_name = None
            limit = None
            recent = False
            print("✅ Will export all contacts")
        else:
            print(f"✅ Will export contact: {contact_name}")
            
            # Ask for additional options
            print()
            limit_input = input("Limit number of messages (or press Enter for all): ").strip()
            if limit_input and limit_input.isdigit():
                limit = int(limit_input)
                print(f"✅ Limiting to {limit} messages")
            else:
                limit = None
                
            recent_input = input("Show recent messages first? (y/N): ").strip().lower()
            if recent_input in ['y', 'yes']:
                recent = True
                print("✅ Will show recent messages first")
            else:
                recent = False
        
        print()
        print("🚀 Starting export...")
        print("=" * 40)
    else:
        # Parse command line arguments
        contact_name = None
        limit = None
        recent = False
        backup_mode = False
        backup_path = None
        
        i = 1
        while i < len(sys.argv):
            if sys.argv[i] == "--contact" and i + 1 < len(sys.argv):
                contact_name = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--limit" and i + 1 < len(sys.argv):
                limit = int(sys.argv[i + 1])
                i += 2
            elif sys.argv[i] == "--recent":
                recent = True
                i += 1
            elif sys.argv[i] == "--backup":
                backup_mode = True
                i += 1
            elif sys.argv[i] == "--backup-path" and i + 1 < len(sys.argv):
                backup_path = sys.argv[i + 1]
                backup_mode = True
                i += 2
            else:
                print(f"❌ Unknown argument: {sys.argv[i]}")
                print("💡 Usage: python script.py [--contact 'Name'] [--limit 100] [--recent] [--backup] [--backup-path 'path']")
                print("   --backup: Use wtsexporter backup instead of local WhatsApp")
                print("   --backup-path: Path to wtsexporter output directory (default: ../working_wts)")
                return
    
    # Display mode information
    if backup_mode:
        print(f"🔄 Using backup mode with wtsexporter data")
        if backup_path:
            print(f"📂 Backup path: {backup_path}")
    else:
        print(f"📱 Using local WhatsApp mode")
    
    try:
        exporter = WhatsAppExporter(backup_mode=backup_mode, backup_base_path=backup_path)
    except Exception as e:
        print(f"❌ Failed to initialize exporter: {e}")
        return
    
    # Single contact export
    if contact_name:
        print(f"🎯 Single contact export: {contact_name}")
        if recent:
            print("📅 Showing recent messages first")
        result = exporter.export_conversation(contact_name, None, limit, recent)
        
        if result:
            print(f"\n🎉 Export successful!")
            print(f"📁 File: {result}")
        else:
            print("❌ Export failed")
        return
    
    # Export all contacts and groups
    print("🔍 Getting all contacts and groups...")
    contacts = exporter.get_all_contacts()
    
    if not contacts:
        print("❌ No contacts found.")
        return
    
    print(f"📊 Found {len(contacts)} contacts and groups")
    print("=" * 60)
    
    # Export each contact
    exported_files = []
    total_reactions = 0
    
    for i, contact in enumerate(contacts, 1):
        print(f"\n📝 [{i}/{len(contacts)}] Exporting: {contact['name']}")
        print(f"   📊 Has {contact['reaction_count']} reaction messages")
        
        result = exporter.export_conversation(contact['jid'], None, limit, False)
        
        if result:
            exported_files.append({
                'contact': contact['name'],
                'file': result,
                'size': os.path.getsize(result),
                'reactions': contact['reaction_count']
            })
            total_reactions += contact['reaction_count']
            print(f"   ✅ Exported to: {os.path.basename(result)}")
        else:
            print(f"   ❌ Failed to export {contact['name']}")
    
    # Summary
    print("\n" + "=" * 80)
    print("🎉 EXPORT SUMMARY")
    print("=" * 80)
    print(f"📊 Total contacts processed: {len(contacts)}")
    print(f"✅ Successfully exported: {len(exported_files)}")
    print(f"🎯 Total reaction messages: {total_reactions}")
    
    total_size = sum(f['size'] for f in exported_files)
    print(f"📄 Total export size: {total_size:,} bytes ({total_size/1024/1024:.1f} MB)")
    
    print(f"\n📁 Exported files:")
    for exp in exported_files:
        size_kb = exp['size'] / 1024
        print(f"  • {exp['contact']}: {os.path.basename(exp['file'])} ({size_kb:.1f} KB, {exp['reactions']} reactions)")
    
    print(f"\n🎉 All conversations exported successfully!")
    print(f"📂 Files are saved in the 'conversations' directory.")


if __name__ == "__main__":
    main()
