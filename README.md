# WhatsApp Conversation Exporter

Export your WhatsApp conversations with emoji reactions and message citations to readable text files.

## Features

- ✅ **Complete conversation export** with message history
- ✅ **Emoji reactions** support (👍 �� ❤️ etc.)
- ✅ **Message citations** extraction from quoted messages
- ✅ **Systematic database parsing** using WhatsApp's SQLite structure
- ✅ **Per-contact exports** or bulk export of all conversations
- ✅ **Clean formatting** with timestamps and reaction indicators

## Requirements

- macOS with WhatsApp Desktop installed
- Python 3.7+
- Direct access to WhatsApp's local database

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/whatsapp-conversation-exporter.git
cd whatsapp-conversation-exporter
```

2. No additional dependencies required - uses only Python standard library!

## Usage

### Export a specific contact
```bash
python whatsapp_conversation_exporter.py --contact "Contact Name"
```

### Export all conversations
```bash
python whatsapp_conversation_exporter.py
```

### Limit number of messages
```bash
python whatsapp_conversation_exporter.py --contact "Contact Name" --limit 100
```

## Output Format

The exporter creates clean, readable text files with:

```
💬 WHATSAPP CONVERSATION: Contact Name
📅 Export date: 2025-08-10 23:45:12
📊 Total messages: 332 | With reactions: 45 | Citations: 12

[2025-01-15 14:30:22] < Hello! How are you?
[2025-01-15 14:31:05] > I'm good, thanks for asking! 😊 [👍]
[2025-01-15 14:32:10] < > I'm good, thanks for asking!
                         That's great to hear!
```

## Technical Details

### Database Access
The exporter directly reads WhatsApp's local SQLite database:
- Location: `~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite`
- Tables used: `ZWAMESSAGE`, `ZWAMEDIAITEM`, `ZWAMESSAGEINFO`

### Citation Extraction
Citations are extracted using systematic protobuf parsing from `ZWAMEDIAITEM.ZMETADATA`:
- **Tag 1**: Contains quoted message text
- **Validation**: Length > 10 characters, UTF-8 decoded
- **No heuristics**: Pure database structure analysis

### Reaction Processing
Emoji reactions are parsed from `ZWAMESSAGEINFO` table with proper Unicode handling.

## Safety & Privacy

- ⚠️ **Read-only access**: The script only reads data, never modifies your WhatsApp database
- 🔒 **Local processing**: All data stays on your machine
- 📁 **Export location**: Creates `conversations/` directory in script location
- 🚫 **No cloud upload**: No data is sent anywhere
- 🛡️ **Privacy protection**: `.gitignore` prevents accidental upload of conversations

## Limitations

- macOS only (WhatsApp Desktop database structure)
- Requires WhatsApp Desktop to be installed
- Media files (images, videos) are not exported, only text content
- Group conversations supported but may have different formatting

## Contributing

Contributions welcome! Please feel free to submit issues and pull requests.

## License

MIT License - see LICENSE file for details.

## Disclaimer

This tool is for personal use only. Ensure you comply with WhatsApp's Terms of Service and applicable data protection laws. The authors are not responsible for any misuse of this software.
