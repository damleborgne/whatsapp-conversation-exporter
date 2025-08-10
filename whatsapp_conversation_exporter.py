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
    def __init__(self, db_path=None):
        """Initialize with WhatsApp database."""
        self.db_path = db_path or self._find_database()
        self.contact_cache = {}
        print(f"📁 Database: {self.db_path}")
    
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
    
    def _extract_quoted_text(self, cursor, media_item_id):
        """Extract quoted text from media metadata."""
        try:
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
                                # Check for forward hash
                                sanitized = re.sub(r"[^A-Za-z0-9'`{}]", "", text)
                                if (re.fullmatch(r"[A-Za-z0-9]{2,24}['`][A-Za-z0-9{}]{2,48}", sanitized) and
                                    any(c.isdigit() or c in '{}' or (c.isalpha() and c.isupper()) for c in sanitized)):
                                    return ForwardInfo(sanitized)
                                
                                # Regular quote
                                if ' ' in text and len(text) > 10:
                                    if len(text) > 50:
                                        words = text[:50].split()
                                        text = ' '.join(words[:-1]) + "..." if len(words) > 1 else text[:50] + "..."
                                    return text
                        except Exception:
                            pass
                    
                    i += 2 + length if i + 2 + length <= len(blob) else i + 1
                else:
                    i += 1
            
            # Fallback: scan for forward hash
            try:
                raw_ascii = ''.join(chr(b) if 32 <= b < 127 else ' ' for b in blob)
                candidates = re.findall(r"[A-Za-z0-9]{2,24}['`][A-Za-z0-9{}]{2,48}", raw_ascii)
                for cand in candidates:
                    if any(c.isdigit() or c in '{}' or (c.isalpha() and c.isupper()) for c in cand):
                        return ForwardInfo(cand)
            except Exception:
                pass
            
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
    
    def get_conversation(self, contact_jid, limit=None):
        """Get conversation with all features."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if this is a group conversation
                is_group = contact_jid.endswith('@g.us')
                
                if is_group:
                    # Group conversation query with sender names
                    query = """
                        SELECT 
                            m.Z_PK, m.ZTEXT, m.ZMESSAGEDATE, m.ZFROMJID, m.ZTOJID,
                            m.ZISFROMME, m.ZFLAGS, i.ZRECEIPTINFO, m.ZPARENTMESSAGE, m.ZMEDIAITEM,
                            cs.ZPARTNERNAME, gm.ZMEMBERJID
                        FROM ZWAMESSAGE m
                        LEFT JOIN ZWAMESSAGEINFO i ON m.Z_PK = i.ZMESSAGE
                        LEFT JOIN ZWAGROUPMEMBER gm ON m.ZGROUPMEMBER = gm.Z_PK
                        LEFT JOIN ZWACHATSESSION cs ON gm.ZMEMBERJID = cs.ZCONTACTJID
                        WHERE (m.ZFROMJID = ? OR m.ZTOJID = ?)
                        AND m.ZMESSAGETYPE = 0 AND m.ZTEXT IS NOT NULL AND m.ZTEXT != ''
                        ORDER BY m.ZMESSAGEDATE ASC
                    """
                else:
                    # Individual conversation query
                    query = """
                        SELECT 
                            m.Z_PK, m.ZTEXT, m.ZMESSAGEDATE, m.ZFROMJID, m.ZTOJID,
                            m.ZISFROMME, m.ZFLAGS, i.ZRECEIPTINFO, m.ZPARENTMESSAGE, m.ZMEDIAITEM,
                            NULL, NULL
                        FROM ZWAMESSAGE m
                        LEFT JOIN ZWAMESSAGEINFO i ON m.Z_PK = i.ZMESSAGE
                        WHERE (m.ZFROMJID = ? OR m.ZTOJID = ?)
                        AND m.ZMESSAGETYPE = 0 AND m.ZTEXT IS NOT NULL AND m.ZTEXT != ''
                        ORDER BY m.ZMESSAGEDATE ASC
                    """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query, (contact_jid, contact_jid))
                rows = cursor.fetchall()
                
                print(f"📋 Found {len(rows)} messages...")
                
                # Collect all messages
                self.messages = []
                message_lookup = {}
                
                for row in rows:
                    # Decode reaction
                    reaction_emoji = None
                    if row[7]:
                        reaction_emoji = self._decode_reaction(row[7], is_group, contact_jid if is_group else None)
                    
                    # Extract quoted text
                    quoted_text = None
                    if row[9]:  # media_item_id
                        quoted_text = self._extract_quoted_text(cursor, row[9])
                        if isinstance(quoted_text, ForwardInfo) and row[8]:  # parent_message_id exists
                            quoted_text = None
                    
                    flags = row[6] or 0
                    is_forwarded = bool(flags & 0x180 == 0x180)
                    
                    # For groups, get sender name
                    sender_name = None
                    if is_group and not bool(row[5]):  # Not from me
                        sender_name = row[10]  # ZPARTNERNAME from the join
                    
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
                        '_media_item_id': row[9]
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
                output.append(f"[{time_part}] {prefix}")
                
                citation = msg.get('quoted_text')
                if isinstance(citation, ForwardInfo):
                    output.append(f"    ↳ (forwarded id {citation.hash_id})")
                else:
                    lines = citation.split('\n')
                    if len(lines) == 1:
                        output.append(f"    ↳ {lines[0]}")
                    else:
                        output.append(f"    ↳ {lines[0]}")
                        for extra in lines[1:]:
                            output.append(f"       {extra}")
                
                message_line = f"    {sender_prefix}{msg['content']}"
                if msg['reaction_emoji']:
                    message_line += f" {msg['reaction_emoji']}"
                output.append(message_line)
            else:
                # Regular message
                content = msg['content']
                if msg.get('is_forwarded'):
                    content = f"(forward) {content}"
                message_line = f"[{time_part}] {prefix} {sender_prefix}{content}"
                if msg['reaction_emoji']:
                    message_line += f" {msg['reaction_emoji']}"
                output.append(message_line)
        
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
    
    def export_conversation(self, contact_name_or_jid, output_file=None, limit=None):
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
        messages = self.get_conversation(target_contact['jid'], limit)
        if not messages:
            print(f"❌ No messages found for {target_contact['name']}")
            return None
        
        # Generate filename
        if not output_file:
            safe_name = "".join(c for c in target_contact['name'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(conversations_dir, f"whatsapp_conversation_{safe_name}_{timestamp}.txt")
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
    
    # Parse arguments
    contact_name = None
    limit = None
    
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--contact" and i + 1 < len(sys.argv):
            contact_name = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
            i += 2
        else:
            print(f"❌ Unknown argument: {sys.argv[i]}")
            print("💡 Usage: python script.py [--contact 'Name'] [--limit 100]")
            return
    
    try:
        exporter = WhatsAppExporter()
    except Exception as e:
        print(f"❌ Failed to initialize exporter: {e}")
        return
    
    # Single contact export
    if contact_name:
        print(f"🎯 Single contact export: {contact_name}")
        result = exporter.export_conversation(contact_name, None, limit)
        
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
        
        result = exporter.export_conversation(contact['jid'], None, limit)
        
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
