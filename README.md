# WhatsApp Conversation Exporter

Export your WhatsApp conversations with emoji reactions, message citations, and media files to readable Markdown files with clickable links.

## Features

- ✅ **Complete conversation export** with message history and media
- ✅ **Emoji reactions** support with full color/modifier display (👍 🏻 ❤️ etc.)
- ✅ **Message citations** extraction from quoted messages with improved formatting
- ✅ **Media file export** with automatic copying and VS Code-compatible links
- ✅ **Dual data source support**: Local WhatsApp client OR iOS backup extraction
- ✅ **Interactive mode** with user-friendly prompts and intelligent defaults
- ✅ **Per-contact exports** or bulk export of all conversations
- ✅ **Clean Markdown formatting** with timestamps, reactions, and proper indentation

## Data Sources

Makes use of:

**WhatsApp Client data** (incomplete because old messages and some media are not synced)

OR

**wtsexport data** (`pip install whatsapp-chat-exporter`, from https://github.com/KnugiHK/WhatsApp-Chat-Exporter)
(example usage: `wtsexporter -i -b ~/Library/Application\ Support/MobileSync/Backup/00008110-00026C512233801E`, on a non-encrypted iOS backup)

## Requirements

- macOS with WhatsApp Desktop installed (for local mode) OR iOS backup extracted with wtsexporter
- Python 3.7+
- For backup mode: `whatsapp-chat-exporter` package if you need to extract data from iOS backup (see above)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/whatsapp-conversation-exporter.git
cd whatsapp-conversation-exporter
```

2. For backup mode support, install wtsexporter:
```bash
pip install whatsapp-chat-exporter
```

3. No additional dependencies required - uses only Python standard library!

## Usage

### Interactive Mode (Recommended)
Simply run the script without arguments for guided setup:
```bash
python whatsapp_conversation_exporter.py
```
The interactive mode will:
1. Ask you to choose between local WhatsApp data or iOS backup
2. Prompt for backup path (if using backup mode)
3. Let you select a specific contact or export all
4. Allow you to limit message count and choose display order

### Command Line Options

#### Using Local WhatsApp Data
```bash
# Export a specific contact
python whatsapp_conversation_exporter.py --contact "Contact Name"

# Export all conversations
python whatsapp_conversation_exporter.py --all

# Limit number of messages (recent first)
python whatsapp_conversation_exporter.py --contact "Contact Name" --limit 100 --recent
```

#### Using iOS Backup Data
```bash
# Export from backup (default path: ../wtsexport)
python whatsapp_conversation_exporter.py --backup --contact "Contact Name"

# Export from custom backup path
python whatsapp_conversation_exporter.py --backup --backup-path "/path/to/backup" --contact "Contact Name"
```

### Preparing iOS Backup Data
1. Create an unencrypted iOS backup
2. Extract WhatsApp data using wtsexporter:
```bash
wtsexporter -i -b ~/Library/Application\ Support/MobileSync/Backup/YOUR_BACKUP_ID
```
3. Use the exported data with this tool

## Output Format

The exporter creates clean, readable Markdown files with:

```markdown
================================================================================
WhatsApp Conversation Export
Contact: Contact Name
Messages: 332
Date Range: 2023-05-17 18:58:20 to 2025-08-10 19:11:16
Exported: 2025-08-10 19:11:16
================================================================================

--- 2023-05-17 ---

[18:58:20] > Hello! How are you? [👍🏻]
[18:59:15] < I'm good, thanks for asking! 😊
[19:00:22] > ↳ I'm good, thanks for asking!
           < That's great to hear!
[19:01:05] < 📎 Image: [photo.jpg](./media/Contact_Name/photo.jpg) (156 KB) - Beautiful sunset!
[19:02:30] > [DeLB:❤️] Nice photo!
```

### Media Files
- **Automatic copying**: Media files are copied to `conversations/media/{contact_name}/`
- **VS Code integration**: Clickable links in Markdown format
- **File information**: Size and type displayed with each media item
- **Captions**: Media captions preserved and displayed

## Technical Details

### Database Access
The exporter supports two data sources:

#### Local WhatsApp Client Data
- Location: `~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite`
- Media: `~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/Message/Media/`
- **Limitation**: Incomplete data (old messages and media not always synced)

#### iOS Backup Data (via wtsexporter)
- Database: Extracted from iOS backup using `whatsapp-chat-exporter`
- Media: Full media archive from backup
- **Advantage**: Complete conversation history and all media files

### Tables Used
- `ZWAMESSAGE`: Message content, timestamps, sender information
- `ZWAMEDIAITEM`: Media file references and metadata
- `ZWAMESSAGEINFO`: Emoji reactions and message status

### Citation Extraction
Citations are extracted using systematic parsing:
- **Local mode**: protobuf parsing from `ZWAMEDIAITEM.ZMETADATA`
- **Backup mode**: Direct access to citation data in message structure
- **Formatting**: Compact display with timestamp and proper indentation

### Media Processing
- **Type detection**: Images (1), Videos (2), Audio (3), Documents (9), GIFs (13), Stickers (14)
- **File copying**: Automatic copying to organized directory structure
- **Link generation**: VS Code-compatible relative paths
- **Size calculation**: File size display in human-readable format

### Emoji and Reaction Processing
- **Full Unicode support**: Including skin tone modifiers and regional indicators
- **Reaction parsing**: From `ZWAMESSAGEINFO` table with proper emoji rendering
- **Format preservation**: Maintains original emoji appearance and colors

## Safety & Privacy

- ⚠️ **Read-only access**: The script only reads data, never modifies your WhatsApp database
- 🔒 **Local processing**: All data stays on your machine
- 📁 **Export location**: Creates `conversations/` directory with organized subdirectories
- 🚫 **No cloud upload**: No data is sent anywhere
- 🛡️ **Privacy protection**: `.gitignore` prevents accidental upload of conversations
- 📱 **Backup safety**: iOS backup mode works with extracted data, not live backups

## Command Line Reference

```bash
# Interactive mode (recommended)
python whatsapp_conversation_exporter.py

# Local WhatsApp data
python whatsapp_conversation_exporter.py --contact "Name" [--limit N] [--recent]
python whatsapp_conversation_exporter.py --all [--limit N] [--recent]

# iOS backup data
python whatsapp_conversation_exporter.py --backup [--backup-path PATH] --contact "Name"
python whatsapp_conversation_exporter.py --backup [--backup-path PATH] --all

# Options:
#   --contact NAME    Export specific contact
#   --all            Export all contacts
#   --limit N        Limit to N messages
#   --recent         Show most recent messages first
#   --backup         Use iOS backup data (requires wtsexporter)
#   --backup-path    Custom backup path (default: ../wtsexport)
```

## Limitations

- **Platform**: macOS only (WhatsApp Desktop database structure)
- **Local mode**: Requires WhatsApp Desktop installed, incomplete message history
- **Backup mode**: Requires iOS backup and wtsexporter tool
- **Group conversations**: Supported but may have different formatting
- **Large exports**: Very large conversations may take time to process

## Contributing

Contributions welcome! Please feel free to submit issues and pull requests.

## License

MIT License - see LICENSE file for details.

## Disclaimer

This tool is for personal use only. Ensure you comply with WhatsApp's Terms of Service and applicable data protection laws. The authors are not responsible for any misuse of this software.
