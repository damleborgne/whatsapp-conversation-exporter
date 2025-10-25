"""
Conversation formatting for WhatsApp export.
"""

import os
import shutil
from datetime import datetime


class ForwardInfo:
    """Information about forwarded messages."""
    def __init__(self, hash_id):
        self.hash_id = hash_id


class ConversationFormatter:
    """Formats conversations for markdown export."""
    
    def __init__(self, participant_manager, mood_analyzer, media_base_path=None, backup_mode=False, db_manager=None):
        """Initialize with participant manager and mood analyzer."""
        self.participant_manager = participant_manager
        self.mood_analyzer = mood_analyzer
        self.media_base_path = media_base_path
        self.backup_mode = backup_mode
        self.db_manager = db_manager
        # Cache for os.path.exists() calls to speed up media processing
        self._path_exists_cache = {}
        # Cache for contact name -> JID lookups
        self._contact_jid_cache = {}
        # Media file index: built once, used many times
        self._media_file_index = None
    
    def _cached_path_exists(self, path):
        """Cached version of os.path.exists() to avoid repeated filesystem checks."""
        if path not in self._path_exists_cache:
            self._path_exists_cache[path] = os.path.exists(path)
        return self._path_exists_cache[path]

    def _build_media_index(self):
        """Build an index of all media files in backup (done once for performance)."""
        if self._media_file_index is not None:
            return  # Already built
        
        print("   📑 Building media file index...")
        import time
        start = time.time()
        
        self._media_file_index = {}
        
        if not self.media_base_path or not os.path.exists(self.media_base_path):
            print(f"   ⚠️ Media base path not found: {self.media_base_path}")
            return
        
        try:
            for root, dirs, files in os.walk(self.media_base_path):
                for filename in files:
                    # Store the full path for each filename
                    # If multiple files have same name, keep the first one found
                    if filename not in self._media_file_index:
                        self._media_file_index[filename] = os.path.join(root, filename)
            
            elapsed = time.time() - start
            print(f"   ✅ Media index built: {len(self._media_file_index)} files in {elapsed:.2f}s")
        except Exception as e:
            print(f"   ⚠️ Error building media index: {e}")
            self._media_file_index = {}
    
    def _format_reaction(self, reaction_emoji):
        """Format reaction emoji - add brackets only if not already present."""
        if not reaction_emoji:
            return ""
        # If reaction already has brackets (group reactions with initials), don't add more
        if reaction_emoji.startswith('['):
            return f" {reaction_emoji}"
        # For simple emojis, add brackets
        return f" [{reaction_emoji}]"
    
    def format_conversation(self, messages, contact_name, contact_jid=None):
        """Format conversation for export."""
        import time
        start_time = time.time()
        if not messages:
            return "No messages found."
        
        output = []
        output.append("=" * 80)
        output.append(f"WhatsApp Conversation Export")
        output.append(f"Contact: {contact_name}")
        output.append(f"Messages: {len(messages)}")
        output.append(f"Date Range: {messages[0]['date']} to {messages[-1]['date']}")
        output.append(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Add mood timeline analysis
        t1 = time.time()
        mood_analysis = self.mood_analyzer.analyze_mood_timeline(messages)
        print(f"    ⏱️  Mood analysis: {time.time() - t1:.2f}s")
        if mood_analysis and mood_analysis.get('weekly_timeline'):
            output.append("")
            output.append("MOOD TIMELINE:")
            output.append("-" * 40)
            for timeline_line in mood_analysis['weekly_timeline']:
                output.append(timeline_line)
            output.append("Legend: _=messages, (space)=no activity, emoji=dominant mood")
            if mood_analysis['total_reactions'] > 0:
                output.append(f"Total reactions: {mood_analysis['total_reactions']}")
        
        # Add participants list if we have the contact_jid
        t2 = time.time()
        if contact_jid:
            participants = self.participant_manager.get_conversation_participants(contact_jid)
            print(f"    ⏱️  Get participants: {time.time() - t2:.2f}s")
            if participants:
                output.append("")
                output.append("PARTICIPANTS:")
                output.append("-" * 40)
                
                # Sort participants: "Moi" first, then alphabetically by name
                participants_sorted = sorted(participants, key=lambda p: (p['name'] != 'Moi', p['name'].lower()))
                
                for participant in participants_sorted:
                    if participant['name'] == 'Moi':
                        # Show "Moi" with phone number and initials if available
                        phone_display = None
                        if participant['formatted_phone'] and participant['formatted_phone'] not in ['Moi', 'Mon numéro']:
                            phone_display = participant['formatted_phone']
                        
                        # Build display string
                        if phone_display and participant.get('initials'):
                            output.append(f"• {participant['name']} ({phone_display}) [{participant['initials']}]")
                        elif phone_display:
                            output.append(f"• {participant['name']} ({phone_display})")
                        elif participant.get('initials'):
                            output.append(f"• {participant['name']} [{participant['initials']}]")
                        else:
                            output.append(f"• {participant['name']}")
                    else:
                        # For unknown names, show the phone number as the main identifier
                        if participant['name'] == "Inconnu" and participant['formatted_phone'] != "Numéro inconnu":
                            output.append(f"• {participant['formatted_phone']}")
                        else:
                            # Show name with phone number and initials
                            phone_display = participant['formatted_phone'] if participant['formatted_phone'] != "Numéro inconnu" else "Numéro inconnu"
                            
                            # Add initials if available
                            if participant.get('initials'):
                                output.append(f"• {participant['name']} ({phone_display}) [{participant['initials']}]")
                            else:
                                output.append(f"• {participant['name']} ({phone_display})")
        
        output.append("=" * 80)
        output.append("")
        
        # Format messages
        t3 = time.time()
        self._format_messages(output, messages, contact_name)
        print(f"    ⏱️  Format messages: {time.time() - t3:.2f}s")
        print(f"    ⏱️  Format TOTAL: {time.time() - start_time:.2f}s")
        
        # Stats
        output.append("")
        output.append("=" * 80)
        output.append(f"📊 Total messages: {len(messages)}")
        output.append("=" * 80)
        
        return "\n".join(output)
    
    def _format_messages(self, output, messages, contact_name):
        """Format the actual message content."""
        import time
        current_date = None
        slow_messages = []
        for i, msg in enumerate(messages):
            msg_start = time.time()
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
            
            prefix = ">>" if msg['is_from_me'] else "<"
            
            # Remove indentation for better readability - all messages aligned to left
            indent = ""
            
            # For group messages, add sender name
            sender_prefix = ""
            if msg.get('sender_name') and not msg['is_from_me']:
                sender_prefix = f"{msg['sender_name']}: "
            
            # Handle quoted messages
            if msg.get('quoted_text'):
                self._format_quoted_message(output, msg, time_part, prefix, indent, sender_prefix, contact_name)
            else:
                self._format_regular_message(output, msg, time_part, prefix, indent, sender_prefix, contact_name)
            
            # Track slow messages
            msg_time = time.time() - msg_start
            if msg_time > 0.01:  # More than 10ms
                slow_messages.append((i, msg['message_id'], msg_time))
        
        # Show slowest messages
        if slow_messages:
            slow_messages.sort(key=lambda x: x[2], reverse=True)
            print(f"      ⚠️  {len(slow_messages)} slow messages (>10ms), top 5:")
            for idx, msg_id, duration in slow_messages[:5]:
                print(f"         Message {idx} (ID:{msg_id}): {duration*1000:.1f}ms")
    
    def _format_quoted_message(self, output, msg, time_part, prefix, indent, sender_prefix, contact_name):
        """Format a message with citation/quote."""
        citation = msg.get('quoted_text')
        
        # Format citation directly after timestamp
        if isinstance(citation, ForwardInfo):
            citation_line = f"{indent}[{time_part}] ↳ (forwarded id {citation.hash_id})"
        else:
            lines = citation.split('\n')
            citation_line = f"{indent}[{time_part}] ↳ {lines[0]}"
            
        output.append(citation_line)
        
        # Add additional citation lines if multi-line
        if not isinstance(citation, ForwardInfo):
            lines = citation.split('\n')
            if len(lines) > 1:
                for extra in lines[1:]:
                    # Indent to align with the arrow
                    output.append(f"{indent}           {extra}")
        
        # Handle media in quoted messages
        if msg.get('media_info'):
            self._format_media_in_quote(output, msg, indent, contact_name)
        
        # Add the reply message below with proper indentation and sender prefix
        reply_content = msg['content'] or ''
        if reply_content.strip():
            # Handle multi-line replies
            lines = reply_content.split('\n')
            message_line = f"{indent}           {prefix} {sender_prefix}{lines[0]}"
            if len(lines) == 1 and msg['reaction_emoji']:
                # Single line: add reaction immediately
                message_line += self._format_reaction(msg['reaction_emoji'])
            output.append(message_line)
            
            # Add continuation lines
            for i, extra_line in enumerate(lines[1:], 1):
                is_last = (i == len(lines) - 1)
                continuation = f"{indent}           {prefix} {extra_line}"
                if is_last and msg['reaction_emoji']:
                    # Add reaction to last line
                    continuation += self._format_reaction(msg['reaction_emoji'])
                output.append(continuation)
    
    def _format_regular_message(self, output, msg, time_part, prefix, indent, sender_prefix, contact_name):
        """Format a regular message (no citation)."""
        # Handle voice/video calls (type 59)
        if msg.get('message_type') == 59:
            direction = "📞 Appel sortant" if msg.get('is_from_me') else "📞 Appel entrant"
            message_line = f"[{time_part}]{indent} {prefix} {sender_prefix}{direction}"
            if msg['reaction_emoji']:
                message_line += self._format_reaction(msg['reaction_emoji'])
            output.append(message_line)
            return
        
        # Regular message - handle media first, then text
        if msg.get('media_info'):
            self._format_media_message(output, msg, time_part, prefix, indent, sender_prefix, contact_name)
        elif msg['content'] and msg['content'].strip():
            # Text-only message (no media)
            content = msg['content']
            if msg.get('is_forwarded'):
                content = f"(forward) {content}"
            
            # Handle multi-line messages: split and indent continuation lines
            lines = content.split('\n')
            message_line = f"[{time_part}]{indent} {prefix} {sender_prefix}{lines[0]}"
            if len(lines) == 1 and msg['reaction_emoji']:
                # Single line: add reaction immediately
                message_line += self._format_reaction(msg['reaction_emoji'])
            output.append(message_line)
            
            # Add continuation lines with proper indentation
            for i, extra_line in enumerate(lines[1:], 1):
                is_last = (i == len(lines) - 1)
                continuation = f"           {prefix} {extra_line}"
                if is_last and msg['reaction_emoji']:
                    # Add reaction to last line
                    continuation += self._format_reaction(msg['reaction_emoji'])
                output.append(continuation)
        else:
            # This should never happen - warn about completely empty messages
            if not msg.get('media_info') and not (msg['content'] and msg['content'].strip()):
                msg_date = msg.get('date', 'Date inconnue')
                print(f"⚠️ Warning: Empty message found")
                print(f"   ID: {msg.get('message_id')}, Type: {msg.get('message_type')}")
                print(f"   Date/Time: {msg_date}")
                print(f"   Content: '{msg.get('content', '')}'")
                print(f"   Media item ID: {msg.get('media_item_id')}")
                print(f"   Media info: {msg.get('media_info')}")
                print(f"   Is from me: {msg.get('is_from_me')}")
                # Still show it with a placeholder to avoid losing data
                output.append(f"[{time_part}]{indent} {prefix} {sender_prefix}[Empty message - Type {msg.get('message_type', '?')}]")
    
    def _format_media_message(self, output, msg, time_part, prefix, indent, sender_prefix, contact_name):
        """Format a message with media."""
        from .utils import get_media_type_name
        
        # Check if media_info is None - shouldn't happen but handle gracefully
        if msg.get('media_info') is None:
            # Treat as empty message
            output.append(f"[{time_part}]{indent} {prefix} {sender_prefix}[Empty media message - Type {msg.get('message_type', '?')}]")
            return
        
        # Handle location messages (type 5)
        if msg.get('message_type') == 5:
            media_info = msg.get('media_info') or {}
            lat = media_info.get('latitude')
            lon = media_info.get('longitude')
            
            if lat and lon and lat != 0 and lon != 0:
                # Create Apple Maps link
                maps_url = f"https://maps.apple.com/?ll={lat},{lon}&q={lat},{lon}"
                title = (media_info.get('title') or '').strip()
                
                if title:
                    message_line = f"[{time_part}]{indent} {prefix} {sender_prefix}📍 Position: {title} - [Voir sur Apple Maps]({maps_url})"
                else:
                    message_line = f"[{time_part}]{indent} {prefix} {sender_prefix}📍 Position partagée - [Voir sur Apple Maps]({maps_url})"
            else:
                message_line = f"[{time_part}]{indent} {prefix} {sender_prefix}📍 Position partagée"
            
            if msg['reaction_emoji']:
                message_line += self._format_reaction(msg['reaction_emoji'])
            output.append(message_line)
            return
        
        # Handle deleted messages (type 14)
        if msg.get('message_type') == 14:
            message_line = f"[{time_part}]{indent} {prefix} {sender_prefix}🗑️ [Message supprimé]"
            if msg['reaction_emoji']:
                message_line += self._format_reaction(msg['reaction_emoji'])
            output.append(message_line)
            return
        
        # Handle voice/video calls (type 59)
        if msg.get('message_type') == 59:
            direction = "📞 Appel sortant" if msg.get('is_from_me') else "📞 Appel entrant"
            message_line = f"[{time_part}]{indent} {prefix} {sender_prefix}{direction}"
            if msg['reaction_emoji']:
                message_line += self._format_reaction(msg['reaction_emoji'])
            output.append(message_line)
            return
        
        # Always show media with its filename
        media_type = get_media_type_name(msg['media_info'].get('message_type', 0))
        size_kb = msg['media_info'].get('file_size', 0) // 1024 if msg['media_info'].get('file_size') else 0
        
        # Check if media file exists locally
        media_path = self._prepare_media_path(contact_name, msg['media_info'])
        
        # Use markdown link format for better VS Code support
        if media_path:
            # Media downloaded and available
            filename = os.path.basename(media_path)
            message_line = f"[{time_part}]{indent} {prefix} {sender_prefix}📎 {media_type}: [{filename}](./{media_path})"
        else:
            # Media not downloaded locally
            message_line = f"[{time_part}]{indent} {prefix} {sender_prefix}📎 {media_type}: [Not downloaded]"
        
        if size_kb > 0:
            message_line += f" ({size_kb} KB)"
        if msg['media_info'].get('title'):
            message_line += f" - {msg['media_info']['title']}"
        if msg['reaction_emoji']:
            message_line += self._format_reaction(msg['reaction_emoji'])
        
        output.append(message_line)
        
        # Add content as separate comment line if it exists
        content = msg['content'] or ''
        if msg.get('is_forwarded'):
            content = f"(forward) {content}"
        
        if content.strip():
            # Handle multi-line content for media captions
            lines = content.split('\n')
            comment_line = f"{indent}    💬 {lines[0]}"
            output.append(comment_line)
            # Add continuation lines
            for extra_line in lines[1:]:
                output.append(f"{indent}       {extra_line}")
    
    def _format_media_in_quote(self, output, msg, indent, contact_name):
        """Format media within a quoted message."""
        from .utils import get_media_type_name
        
        # Handle voice/video calls (type 59) - special case
        if msg.get('message_type') == 59:
            direction = "📞 Appel sortant" if msg.get('is_from_me') else "📞 Appel entrant"
            call_line = f"{indent}           {direction}"
            if msg.get('reaction_emoji'):
                call_line += self._format_reaction(msg['reaction_emoji'])
            output.append(call_line)
            return
        
        media_type = get_media_type_name(msg['media_info'].get('message_type', 0))
        size_kb = msg['media_info'].get('file_size', 0) // 1024 if msg['media_info'].get('file_size') else 0
        
        # Check if media file exists locally
        media_path = self._prepare_media_path(contact_name, msg['media_info'])
        
        # Use markdown link format for better VS Code support
        if media_path:
            filename = os.path.basename(media_path)
            media_line = f"{indent}           📎 {media_type}: [{filename}](./{media_path})"
        else:
            media_line = f"{indent}           📎 {media_type}: [Not downloaded]"
        
        if size_kb > 0:
            media_line += f" ({size_kb} KB)"
        if msg['media_info'].get('title'):
            media_line += f" - {msg['media_info']['title']}"
        if msg.get('reaction_emoji'):
            media_line += self._format_reaction(msg['reaction_emoji'])
        output.append(media_line)
    
    def _prepare_media_path(self, contact_name, media_info):
        """Prepare media path and copy file if needed - matches original logic."""
        if not media_info or not media_info.get('local_path'):
            return None
            
        original_path = media_info['local_path']
        
        # Create media directory structure
        safe_contact_name = "".join(c for c in contact_name if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
        media_dir = f"conversations/media/{safe_contact_name}"
        
        if not self._cached_path_exists(media_dir):
            os.makedirs(media_dir, exist_ok=True)
            # Mark as existing in cache after creation
            self._path_exists_cache[media_dir] = True
        
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
            full_source_path = self._get_backup_media_path(original_path, contact_name)
        else:
            # Local WhatsApp mode
            full_source_path = os.path.join(self.media_base_path, original_path) if self.media_base_path else None
        
        try:
            if full_source_path and self._cached_path_exists(full_source_path) and not self._cached_path_exists(full_target_path):
                shutil.copy2(full_source_path, full_target_path)
                self._path_exists_cache[full_target_path] = True  # Mark as existing
                print(f"   📎 Copied media: {filename}")
            elif self._cached_path_exists(full_target_path):
                pass  # Media already exists
            else:
                pass  # Media not found - will show [Not downloaded]
        except Exception as e:
            print(f"   ⚠️ Could not copy media {filename}: {e}")
        
        return relative_path
    
    def _get_backup_media_path(self, original_path, contact_name):
        """Get backup media path for wtsexporter extracted files."""
        # Extract filename from original path
        filename = os.path.basename(original_path)
        if not filename:
            return None
        
        # Find contact JID by name (with caching!)
        if self.db_manager:
            try:
                # Check cache first
                if contact_name not in self._contact_jid_cache:
                    result = self.db_manager.fetch_one(
                        "SELECT ZCONTACTJID FROM ZWACHATSESSION WHERE ZPARTNERNAME = ?", 
                        (contact_name,)
                    )
                    if result:
                        self._contact_jid_cache[contact_name] = result[0]
                    else:
                        self._contact_jid_cache[contact_name] = None
                
                contact_jid = self._contact_jid_cache.get(contact_name)
                if contact_jid:
                    # Try to find the file in the backup media structure
                    possible_paths = [
                        os.path.join(self.media_base_path, contact_jid, filename),
                        os.path.join(self.media_base_path, contact_jid.replace('@s.whatsapp.net', ''), filename),
                    ]
                    
                    for path in possible_paths:
                        if self._cached_path_exists(path):
                            return path
                    
                    # Last resort: look up in pre-built index (fast!)
                    return self._find_media_in_backup(filename)
            except Exception:
                pass
        
        return None
    
    def _find_media_in_backup(self, filename):
        """Find media file in backup directory using pre-built index."""
        # Build index on first call
        if self._media_file_index is None:
            self._build_media_index()
        
        # Look up in index (O(1) instead of scanning entire tree)
        return self._media_file_index.get(filename)