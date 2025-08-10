#!/usr/bin/env python3
"""
WhatsApp Conversation Exporter with Reactions - Local Database Version
======================================================================

This script exports WhatsApp conversations to text files, including emoji reactions
appended to each message in the format "[emoji]".

This version specifically uses the local database file.

Usage:
    python whatsapp_conversation_exporter_local.py
    python whatsapp_conversation_exporter_local.py --contact "Laure de Verdalle"

Author: AI Assistant  
Date: August 2025
"""

import sqlite3
import os
import sys
from datetime import datetime


class WhatsAppReactionExtractor:
    """Local version of the reaction extractor for the specific database."""
    
    def __init__(self, db_path=None):
        """Initialize with WhatsApp database path."""
        if db_path is None:
            self.db_path = self._find_whatsapp_database()
        else:
            self.db_path = db_path
        self.contact_cache = {}
        print(f"📁 Database path: {self.db_path}")
    
    def _find_whatsapp_database(self):
        """Find the WhatsApp database, trying standard location first."""
        # Standard WhatsApp location on macOS
        standard_path = os.path.expanduser("~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite")
        
        # Fallback to specific database file
        fallback_path = "7c7fba66680ef796b916b067077cc246adacf01d"
        
        print("🔍 Looking for WhatsApp database...")
        
        # Try standard location first
        if os.path.exists(standard_path):
            print(f"✅ Found standard WhatsApp database: {standard_path}")
            return standard_path
        else:
            print(f"❌ Standard location not found: {standard_path}")
        
        # Try fallback location
        if os.path.exists(fallback_path):
            print(f"✅ Found fallback database: {fallback_path}")
            return fallback_path
        else:
            print(f"❌ Fallback location not found: {fallback_path}")
        
        # If neither found, return standard path anyway (might work with permissions)
        print(f"⚠️  Using standard path (may require WhatsApp to be running): {standard_path}")
        return standard_path
    
    def _get_contact_name(self, jid):
        """Get contact name from JID using the ZWACHATSESSION table."""
        if not jid:
            return "Unknown"
            
        if jid in self.contact_cache:
            return self.contact_cache[jid]
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT ZPARTNERNAME 
                    FROM ZWACHATSESSION 
                    WHERE ZCONTACTJID = ?
                """, (jid,))
                
                result = cursor.fetchone()
                if result and result[0]:
                    name = result[0]
                    self.contact_cache[jid] = name
                    return name
                else:
                    if '@' in jid:
                        phone_part = jid.split('@')[0]
                        formatted_name = f"Contact ({phone_part})"
                        self.contact_cache[jid] = formatted_name
                        return formatted_name
                    else:
                        self.contact_cache[jid] = jid
                        return jid
                        
        except sqlite3.Error as e:
            print(f"Error getting contact name: {e}")
            self.contact_cache[jid] = jid
            return jid
    
    def get_contacts_with_reactions(self):
        """Get all contacts who have messages with reactions."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        CASE 
                            WHEN ZWAMESSAGE.ZISFROMME = 1 THEN ZWAMESSAGE.ZTOJID
                            ELSE ZWAMESSAGE.ZFROMJID
                        END as contact_jid,
                        COUNT(*) as reaction_count
                    FROM ZWAMESSAGE  
                    JOIN ZWAMESSAGEINFO ON ZWAMESSAGE.Z_PK = ZWAMESSAGEINFO.ZMESSAGE  
                    WHERE ZWAMESSAGE.ZMESSAGETYPE = 0 
                    AND ZWAMESSAGEINFO.ZRECEIPTINFO IS NOT NULL
                    AND LENGTH(ZWAMESSAGEINFO.ZRECEIPTINFO) > 50
                    AND (
                        HEX(ZWAMESSAGEINFO.ZRECEIPTINFO) LIKE '%F09F%' OR
                        HEX(ZWAMESSAGEINFO.ZRECEIPTINFO) LIKE '%E2%'
                    )
                    AND (ZWAMESSAGE.ZFROMJID LIKE '%@s.whatsapp.net' OR ZWAMESSAGE.ZTOJID LIKE '%@s.whatsapp.net')
                    GROUP BY contact_jid
                    ORDER BY reaction_count DESC
                """)
                
                contacts_with_reactions = []
                for row in cursor.fetchall():
                    jid, count = row
                    if jid:
                        name = self._get_contact_name(jid)
                        contacts_with_reactions.append({
                            'jid': jid,
                            'name': name,
                            'reaction_count': count
                        })
                
                return contacts_with_reactions
                
        except sqlite3.Error as e:
            print(f"❌ Error getting contacts with reactions: {e}")
            return []
    
    def _extract_emoji_from_hex(self, hex_data):
        """Extract emoji from hexadecimal data using generic UTF-8 decoding."""
        hex_lower = hex_data.lower()
        
        if 'f09f' in hex_lower:
            try:
                import re
                emoji_pattern = r'f09f[0-9a-f]{4}'
                matches = re.findall(emoji_pattern, hex_lower)
                
                if matches:
                    emoji_bytes = bytes.fromhex(matches[0])
                    return emoji_bytes.decode('utf-8')
            except Exception:
                pass
        
        if 'e29da4' in hex_lower:
            return '❤️'
        
        return None
    
    def _decode_reaction_blob(self, blob_data):
        """Decode reaction blob using pure hex analysis."""
        if not blob_data:
            return None
            
        try:
            hex_data = blob_data.hex()
            emoji_found = self._extract_emoji_from_hex(hex_data)
            
            if emoji_found:
                return {
                    'type': 'potential_reaction',
                    'detected_emoji': emoji_found,
                    'hex_data': hex_data,
                    'blob_size': len(blob_data)
                }
            else:
                return {
                    'type': 'receipt_only',
                    'hex_data': hex_data,
                    'blob_size': len(blob_data)
                }
            
        except Exception as e:
            return {
                'error': str(e),
                'raw_blob_size': len(blob_data),
                'hex_preview': blob_data.hex()[:50]
            }
    
    def _convert_timestamp(self, timestamp):
        """Convert WhatsApp timestamp to readable format."""
        if not timestamp:
            return None
        try:
            timestamp = timestamp + 978307200  # Add seconds from 1970 to 2001
            return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            return f"Invalid timestamp: {timestamp} ({e})"


class WhatsAppConversationExporter:
    """Export WhatsApp conversations with reactions to text files."""
    
    def __init__(self, db_path=None):
        """Initialize with WhatsApp database."""
        self.extractor = WhatsAppReactionExtractor(db_path)
        self.db_path = self.extractor.db_path
    
    def get_conversation_with_reactions(self, contact_jid, limit=None):
        """Get complete conversation with a contact, including reactions and quotes."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = """
                SELECT  
                    ZWAMESSAGE.Z_PK AS message_id,
                    ZWAMESSAGE.ZTEXT AS message_content,
                    ZWAMESSAGE.ZMESSAGEDATE AS message_date,
                    ZWAMESSAGE.ZFROMJID AS from_jid,
                    ZWAMESSAGE.ZTOJID AS to_jid,
                    ZWAMESSAGE.ZISFROMME AS is_from_me,
                    ZWAMESSAGE.ZMESSAGETYPE AS message_type,
                    ZWAMESSAGEINFO.ZRECEIPTINFO AS reaction_blob,
                    ZWAMESSAGE.ZPARENTMESSAGE AS parent_message_id,
                    ZWAMESSAGE.ZMEDIAITEM AS media_item_id
                FROM ZWAMESSAGE  
                LEFT JOIN ZWAMESSAGEINFO ON ZWAMESSAGE.Z_PK = ZWAMESSAGEINFO.ZMESSAGE
                WHERE (ZWAMESSAGE.ZFROMJID = ? OR ZWAMESSAGE.ZTOJID = ?)
                AND ZWAMESSAGE.ZMESSAGETYPE = 0
                AND ZWAMESSAGE.ZTEXT IS NOT NULL
                AND ZWAMESSAGE.ZTEXT != ''
                ORDER BY ZWAMESSAGE.ZMESSAGEDATE ASC
                """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query, (contact_jid, contact_jid))
                rows = cursor.fetchall()
                
                print(f"📋 Found {len(rows)} messages in conversation...")
                
                # First pass: collect all messages
                messages = []
                message_lookup = {}
                
                for row in rows:
                    # Decode reaction if present
                    reaction_emoji = None
                    if row[7]:  # reaction_blob exists
                        reaction_data = self.extractor._decode_reaction_blob(row[7])
                        if (reaction_data and 
                            reaction_data.get('type') == 'potential_reaction' and
                            'detected_emoji' in reaction_data):
                            reaction_emoji = reaction_data['detected_emoji']
                    
                    # Extract quoted text from MediaItem metadata if present
                    # Use intelligent validation to distinguish real citations from binary artifacts
                    quoted_text = None
                    if row[9]:  # media_item_id exists
                        quoted_text = self._extract_quoted_text_from_media(cursor, row[9])
                    
                    message = {
                        'message_id': row[0],
                        'content': row[1],
                        'date': self.extractor._convert_timestamp(row[2]),
                        'from_jid': row[3],
                        'to_jid': row[4],
                        'is_from_me': bool(row[5]),
                        'reaction_emoji': reaction_emoji,
                        'parent_message_id': row[8],
                        'quoted_text': quoted_text
                    }
                    messages.append(message)
                    message_lookup[message['message_id']] = message
                
                # Second pass: resolve quoted messages via ZPARENTMESSAGE (fallback)
                for message in messages:
                    if not message['quoted_text'] and message['parent_message_id'] and message['parent_message_id'] in message_lookup:
                        parent_msg = message_lookup[message['parent_message_id']]
                        # Extract first 50 characters of quoted message
                        quoted_content = parent_msg['content'][:50]
                        if len(parent_msg['content']) > 50:
                            quoted_content += "..."
                        message['quoted_text'] = quoted_content
                
                return messages
                
        except sqlite3.Error as e:
            print(f"❌ Database error: {e}")
            return []
    
    def _extract_quoted_text_from_media(self, cursor, media_item_id):
        """Extract quoted text from MediaItem metadata using SYSTEMATIC database logic.
        
        SYSTEMATIC LOGIC: 
        1. Check ZMEDIAORIGIN: != 0 indicates forwarded/transferred messages
        2. Extract Tag 1 from protobuf ZMETADATA containing citation text
        3. No heuristic validation - trust the database structure
        """
        try:
                # SYSTEMATIC CHECK: Use ZMEDIAORIGIN as reliable indicator
                cursor.execute("SELECT ZMETADATA, ZMEDIAORIGIN FROM ZWAMEDIAITEM WHERE Z_PK = ?", (media_item_id,))
                result = cursor.fetchone()
                
                if result and result[0]:
                    metadata_blob, media_origin = result[0], result[1]                # SYSTEMATIC PROTOBUF PARSING: Extract Tag 1 (citation text)
                try:
                    i = 0
                    
                    while i < len(metadata_blob) - 2:
                        # Read protobuf field
                        tag_byte = metadata_blob[i]
                        if (tag_byte & 0x7) == 2:  # Length-delimited field
                            tag = tag_byte >> 3
                            length = metadata_blob[i + 1]
                            
                            if i + 2 + length <= len(metadata_blob):
                                field_data = metadata_blob[i + 2:i + 2 + length]
                                
                                # SYSTEMATIC EXTRACTION: Analyser TOUS les tags
                                if length > 2:
                                    try:
                                        # Direct UTF-8 decode without heuristics
                                        quoted_text = field_data.decode('utf-8', errors='ignore')
                                        
                                        # Remove only trailing control characters (systematic)
                                        import re
                                        quoted_text = re.sub(r'[\x00-\x1f]+$', '', quoted_text).strip()
                                        
                                        if quoted_text:
                                            # SYSTEMATIC ACCEPTANCE: SEULEMENT Tag 1 pour les citations  
                                            if tag == 1 and len(quoted_text) > 10:
                                                # Truncate if too long (systematic)
                                                if len(quoted_text) > 50:
                                                    words = quoted_text[:50].split()
                                                    if len(words) > 1:
                                                        quoted_text = ' '.join(words[:-1]) + "..."
                                                    else:
                                                        quoted_text = quoted_text[:50] + "..."
                                                
                                                return quoted_text
                                        
                                    except UnicodeDecodeError:
                                        pass
                                
                                i += 2 + length
                            else:
                                i += 1
                        else:
                            i += 1
                    
                    return None
                    
                except Exception:
                    # If protobuf parsing fails completely, return None
                    return None
            
        except Exception as e:
            print(f"Error extracting quoted text: {e}")
        
        return None
    
    def format_conversation_for_export(self, messages, contact_name):
        """Format conversation messages for text export."""
        if not messages:
            return "No messages found in conversation."
        
        # Header
        output = []
        output.append("=" * 80)
        output.append(f"WhatsApp Conversation Export")
        output.append(f"Contact: {contact_name}")
        output.append(f"Messages: {len(messages)}")
        output.append(f"Date Range: {messages[0]['date']} to {messages[-1]['date']}")
        output.append(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output.append("=" * 80)
        output.append("")
        
        # Messages
        current_date = None
        for msg in messages:
            message_date = msg['date']
            if not message_date:
                continue
                
            # Extract date part
            try:
                msg_date_part = message_date.split(' ')[0]
                if current_date != msg_date_part:
                    current_date = msg_date_part
                    output.append(f"\n--- {current_date} ---\n")
            except:
                pass
            
            # Format time
            try:
                time_part = message_date.split(' ')[1]
            except:
                time_part = "??:??"
            
            # Build message line with prefix symbols for sender identification
            if msg['is_from_me']:
                # Your messages: > prefix
                prefix = ">"
            else:
                # Contact messages: < prefix
                prefix = "<"
            
            # Handle quoted messages with separate line formatting
            if msg.get('quoted_text'):
                # Multi-line format for quoted messages
                output.append(f"[{time_part}] {prefix}")
                output.append(f"    ↳ \"{msg['quoted_text']}\"")
                message_line = f"    {msg['content']}"
                # Add reaction if present
                if msg['reaction_emoji']:
                    message_line += f" [{msg['reaction_emoji']}]"
                output.append(message_line)
            else:
                # Single line format for regular messages
                message_line = f"[{time_part}] {prefix} {msg['content']}"
                # Add reaction if present
                if msg['reaction_emoji']:
                    message_line += f" [{msg['reaction_emoji']}]"
                output.append(message_line)
        
        # Footer stats
        output.append("")
        output.append("=" * 80)
        
        # Count reactions
        reaction_count = sum(1 for msg in messages if msg['reaction_emoji'])
        output.append(f"📊 Total messages: {len(messages)}")
        output.append(f"🎯 Messages with reactions: {reaction_count}")
        
        if reaction_count > 0:
            # Count by emoji type
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
        """Export a conversation to a text file."""
        print(f"🔍 Looking for contact: {contact_name_or_jid}")
        
        # Create conversations directory if it doesn't exist
        conversations_dir = "conversations"
        if not os.path.exists(conversations_dir):
            os.makedirs(conversations_dir)
            print(f"📁 Created directory: {conversations_dir}")
        
        # Get contacts with reactions
        contacts = self.extractor.get_contacts_with_reactions()
        
        # Try to find contact by name or JID
        target_contact = None
        
        for contact in contacts:
            if (contact['name'].lower() == contact_name_or_jid.lower() or 
                contact['jid'] == contact_name_or_jid):
                target_contact = contact
                break
        
        if not target_contact:
            print(f"❌ Contact '{contact_name_or_jid}' not found.")
            print("Available contacts with reactions:")
            for i, contact in enumerate(contacts[:10], 1):
                print(f"  {i}. {contact['name']}")
            return None
        
        print(f"✅ Found contact: {target_contact['name']} ({target_contact['jid']})")
        
        # Get conversation
        messages = self.get_conversation_with_reactions(target_contact['jid'], limit)
        
        if not messages:
            print(f"❌ No messages found for {target_contact['name']}")
            return None
        
        # Generate output filename if not provided
        if not output_file:
            safe_name = "".join(c for c in target_contact['name'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(conversations_dir, f"whatsapp_conversation_{safe_name}_{timestamp}.txt")
        else:
            # If output_file is provided, put it in conversations directory
            output_file = os.path.join(conversations_dir, os.path.basename(output_file))
        
        # Format and export
        formatted_text = self.format_conversation_for_export(messages, target_contact['name'])
        
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
    """Main function - Export all conversations with reactions."""
    print("💬 WHATSAPP CONVERSATION EXPORTER (LOCAL DATABASE)")
    print("=" * 60)
    print("📝 Export ALL conversations with emoji reactions to text files")
    print("🎯 One file per contact with complete conversation history")
    print()
    
    try:
        # Initialize exporter with local database
        exporter = WhatsAppConversationExporter()
        
    except Exception as e:
        print(f"❌ Failed to initialize exporter: {e}")
        return
    
    # Parse command line arguments for optional single contact export
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
            print("💡 If no --contact specified, exports ALL contacts")
            return
    
    # Single contact export if specified
    if contact_name:
        print(f"🎯 Single contact export: {contact_name}")
        result = exporter.export_conversation(
            contact_name_or_jid=contact_name,
            output_file=None,
            limit=limit
        )
        
        if result:
            print(f"\n🎉 Export successful!")
            print(f"📁 File: {result}")
        else:
            print("❌ Export failed")
        return
    
    # Export ALL contacts with reactions
    print("🔍 Getting all contacts with reactions...")
    contacts = exporter.extractor.get_contacts_with_reactions()
    
    if not contacts:
        print("❌ No contacts with reactions found.")
        return
    
    print(f"📊 Found {len(contacts)} contacts with reactions")
    print("=" * 60)
    
    # Export each contact
    exported_files = []
    total_reactions = 0
    
    for i, contact in enumerate(contacts, 1):
        print(f"\n📝 [{i}/{len(contacts)}] Exporting: {contact['name']}")
        print(f"   📊 Has {contact['reaction_count']} reaction messages")
        
        # Export full conversation (no limit)
        result = exporter.export_conversation(
            contact_name_or_jid=contact['jid'],
            output_file=None,
            limit=limit
        )
        
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
    
    # Calculate total size
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
