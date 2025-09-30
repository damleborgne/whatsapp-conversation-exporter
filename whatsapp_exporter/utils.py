"""
Utility functions for WhatsApp export processing.
"""

def clean_contact_name(name):
    """Clean contact name by removing invisible Unicode characters."""
    if not name:
        return name
    
    # Remove common invisible Unicode characters
    invisible_chars = [
        '\u200E',  # Left-to-Right Mark (LTR)
        '\u200F',  # Right-to-Left Mark (RTL)
        '\u202A',  # Left-to-Right Embedding
        '\u202B',  # Right-to-Left Embedding
        '\u202C',  # Pop Directional Formatting
        '\u202D',  # Left-to-Right Override
        '\u202E',  # Right-to-Left Override
        '\u2066',  # Left-to-Right Isolate
        '\u2067',  # Right-to-Left Isolate
        '\u2068',  # First Strong Isolate
        '\u2069',  # Pop Directional Isolate
        '\uFEFF',  # Zero Width No-Break Space (BOM)
        '\u200B',  # Zero Width Space
        '\u200C',  # Zero Width Non-Joiner
        '\u200D',  # Zero Width Joiner
    ]
    
    cleaned_name = name
    for char in invisible_chars:
        cleaned_name = cleaned_name.replace(char, '')
    
    # Remove leading/trailing whitespace
    cleaned_name = cleaned_name.strip()
    
    return cleaned_name if cleaned_name else name


def extract_phone_number(jid):
    """Extract phone number from JID."""
    if not jid:
        return None
    
    # For individual contacts: "33123456789@s.whatsapp.net"
    # For groups: "33123456789-1234567890@g.us"
    if '@s.whatsapp.net' in jid:
        return jid.split('@')[0]
    elif '@g.us' in jid:
        # For groups, extract the creator's number (before the dash)
        group_part = jid.split('@')[0]
        if '-' in group_part:
            return group_part.split('-')[0]
    
    return None


def format_phone_number(phone):
    """Format phone number for better readability."""
    if not phone or not phone.isdigit():
        return phone
    
    # French numbers (starting with 33)
    if phone.startswith('33') and len(phone) >= 11:
        # Format: +33 X XX XX XX XX
        formatted = f"+33 {phone[2]}"
        for i in range(3, len(phone), 2):
            if i + 1 < len(phone):
                formatted += f" {phone[i:i+2]}"
            else:
                formatted += f" {phone[i:]}"
        return formatted
    
    # US numbers (starting with 1)
    elif phone.startswith('1') and len(phone) == 11:
        # Format: +1 (XXX) XXX-XXXX
        return f"+1 ({phone[1:4]}) {phone[4:7]}-{phone[7:]}"
    
    # Other international numbers
    elif len(phone) > 7:
        return f"+{phone}"
    
    return phone


def get_initials(name):
    """Generate initials from a name."""
    if not name:
        return "?"
    
    # Split name and take first letter of each word
    words = name.split()
    initials = ''.join([word[0].upper() for word in words if word])
    
    # Limit to 3 characters max
    return initials[:3] if initials else "?"


def get_media_type_name(message_type):
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