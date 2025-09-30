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
    
    def format_conversation(self, messages, contact_name, contact_jid=None):
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
        
        # Add mood timeline analysis
        mood_analysis = self.mood_analyzer.analyze_mood_timeline(messages)
        if mood_analysis and mood_analysis.get('weekly_timeline'):
            output.append("")
            output.append("MOOD TIMELINE:")
            output.append("-" * 40)
            for timeline_line in mood_analysis['weekly_timeline']:
                output.append(timeline_line)
            output.append("Legend: 💬=messages, ·=no activity, emoji=dominant mood")
            if mood_analysis['total_reactions'] > 0:
                output.append(f"Total reactions: {mood_analysis['total_reactions']}")
        
        # Add participants list if we have the contact_jid
        if contact_jid:
            participants = self.participant_manager.get_conversation_participants(contact_jid)
            if participants:
                output.append("")
                output.append("PARTICIPANTS:")
                output.append("-" * 40)
                
                # Sort participants: "Moi" first, then alphabetically by name
                participants_sorted = sorted(participants, key=lambda p: (p['name'] != 'Moi', p['name'].lower()))
                
                for participant in participants_sorted:
                    if participant['name'] == 'Moi':
                        # Show "Moi" with phone number if available
                        if participant['formatted_phone'] and participant['formatted_phone'] not in ['Moi', 'Mon numéro']:
                            output.append(f"• {participant['name']} ({participant['formatted_phone']})")
                        else:
                            output.append(f"• {participant['name']}")
                    else:
                        # For unknown names, show the phone number as the main identifier
                        if participant['name'] == "Inconnu" and participant['formatted_phone'] != "Numéro inconnu":
                            output.append(f"• {participant['formatted_phone']}")
                        else:
                            # Show name with phone number
                            phone_display = participant['formatted_phone'] if participant['formatted_phone'] != "Numéro inconnu" else "Numéro inconnu"
                            output.append(f"• {participant['name']} ({phone_display})")
        
        output.append("=" * 80)
        output.append("")
        
        # Format message content
        self._format_messages(output, messages, contact_name)
        
        # Stats
        output.append("")
        output.append("=" * 80)
        output.append(f"📊 Total messages: {len(messages)}")
        output.append("=" * 80)
        return "\n".join(output)
    
    def _format_messages(self, output, messages, contact_name):
        """Format the actual message content."""
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
            
            # Add indentation for non-user messages for better readability
            indent = "" if msg['is_from_me'] else "  "
            
            # For group messages, add sender name
            sender_prefix = ""
            if msg.get('sender_name') and not msg['is_from_me']:
                sender_prefix = f"{msg['sender_name']}: "
            
            # Handle quoted messages
            if msg.get('quoted_text'):
                self._format_quoted_message(output, msg, time_part, prefix, indent, sender_prefix, contact_name)
            else:
                self._format_regular_message(output, msg, time_part, prefix, indent, sender_prefix, contact_name)
    
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
            message_line = f"{indent}           {prefix} {sender_prefix}{reply_content}"
            if msg['reaction_emoji']:
                message_line += f" {msg['reaction_emoji']}"
            output.append(message_line)
    
    def _format_regular_message(self, output, msg, time_part, prefix, indent, sender_prefix, contact_name):
        """Format a regular message (no citation)."""
        # Regular message - handle media first, then text
        if msg.get('media_info'):
            self._format_media_message(output, msg, time_part, prefix, indent, sender_prefix, contact_name)
        elif msg['content'] and msg['content'].strip():
            # Text-only message (no media)
            content = msg['content']
            if msg.get('is_forwarded'):
                content = f"(forward) {content}"
            message_line = f"[{time_part}]{indent} {prefix} {sender_prefix}{content}"
            if msg['reaction_emoji']:
                message_line += f" {msg['reaction_emoji']}"
            output.append(message_line)
        else:
            # This should never happen - warn about completely empty messages
            if not msg.get('media_info') and not (msg['content'] and msg['content'].strip()):
                print(f"⚠️ Warning: Empty message found (ID: {msg.get('message_id')}, Type: {msg.get('message_type')})")
                # Still show it with a placeholder to avoid losing data
                output.append(f"[{time_part}]{indent} {prefix} {sender_prefix}[Empty message - Type {msg.get('message_type', '?')}]")
    
    def _format_media_message(self, output, msg, time_part, prefix, indent, sender_prefix, contact_name):
        """Format a message with media."""
        from .utils import get_media_type_name
        
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
            message_line += f" {msg['reaction_emoji']}"
        
        output.append(message_line)
        
        # Add content as separate comment line if it exists
        content = msg['content'] or ''
        if msg.get('is_forwarded'):
            content = f"(forward) {content}"
        
        if content.strip():
            comment_line = f"{indent}    💬 {content}"
            output.append(comment_line)
    
    def _format_media_in_quote(self, output, msg, indent, contact_name):
        """Format media within a quoted message."""
        from .utils import get_media_type_name
        
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
        output.append(media_line)
    
    def _prepare_media_path(self, contact_name, media_info):
        """Prepare media path and copy file if needed - matches original logic."""
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
            full_source_path = self._get_backup_media_path(original_path, contact_name)
        else:
            # Local WhatsApp mode
            full_source_path = os.path.join(self.media_base_path, original_path) if self.media_base_path else None
        
        try:
            if full_source_path and os.path.exists(full_source_path) and not os.path.exists(full_target_path):
                shutil.copy2(full_source_path, full_target_path)
                print(f"   📎 Copied media: {filename}")
            elif os.path.exists(full_target_path):
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
        
        # Find contact JID by name
        if self.db_manager:
            try:
                result = self.db_manager.fetch_one(
                    "SELECT ZCONTACTJID FROM ZWACHATSESSION WHERE ZPARTNERNAME = ?", 
                    (contact_name,)
                )
                if result:
                    contact_jid = result[0]
                    # Try to find the file in the backup media structure
                    possible_paths = [
                        os.path.join(self.media_base_path, contact_jid, filename),
                        os.path.join(self.media_base_path, contact_jid.replace('@s.whatsapp.net', ''), filename),
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
        if not self.media_base_path or not os.path.exists(self.media_base_path):
            return None
        
        try:
            for root, dirs, files in os.walk(self.media_base_path):
                if filename in files:
                    return os.path.join(root, filename)
        except Exception:
            pass
        
        return None