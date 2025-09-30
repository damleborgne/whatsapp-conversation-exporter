"""
Participant and contact management for WhatsApp export.
"""

from .utils import clean_contact_name, extract_phone_number, format_phone_number, get_initials


class ParticipantManager:
    """Manages conversation participants and contacts."""
    
    def __init__(self, db_manager):
        """Initialize with database manager."""
        self.db_manager = db_manager
        self.contact_cache = {}
    
    def get_contact_name(self, jid):
        """Get contact name from JID, with caching."""
        if jid in self.contact_cache:
            return self.contact_cache[jid]
        
        try:
            result = self.db_manager.fetch_one(
                "SELECT ZPARTNERNAME FROM ZWACHATSESSION WHERE ZCONTACTJID = ?", 
                (jid,)
            )
            
            if result and result[0]:
                name = clean_contact_name(result[0])
            else:
                name = f"Contact ({jid.split('@')[0]})" if '@' in jid else jid
            
            self.contact_cache[jid] = name
            return name
        except Exception as e:
            print(f"⚠️ Error getting contact name for {jid}: {e}")
            return jid
    
    def get_conversation_participants(self, contact_jid):
        """Get all participants in a conversation with their names and phone numbers."""
        participants = []
        is_group = contact_jid.endswith('@g.us')
        my_phone_number = None  # To store your own phone number
        
        try:
            if is_group:
                # For groups, get all members
                members = self.db_manager.fetch_all("""
                    SELECT gm.ZMEMBERJID, cs.ZPARTNERNAME
                    FROM ZWAGROUPMEMBER gm
                    LEFT JOIN ZWACHATSESSION cs ON gm.ZMEMBERJID = cs.ZCONTACTJID
                    LEFT JOIN ZWACHATSESSION gs ON gs.ZCONTACTJID = ?
                    WHERE gm.ZCHATSESSION = gs.Z_PK
                    ORDER BY cs.ZPARTNERNAME
                """, (contact_jid,))
                
                for member_jid, member_name in members:
                    if member_jid:
                        phone = extract_phone_number(member_jid)
                        formatted_phone = format_phone_number(phone) if phone else "Numéro inconnu"
                        
                        # Check if this is "you" (your own contact)
                        cleaned_name = clean_contact_name(member_name) if member_name and member_name.strip() else None
                        
                        if cleaned_name and cleaned_name.lower() in ['vous', 'you']:
                            # This is your own contact - store the phone number for later
                            my_phone_number = formatted_phone
                            continue  # Skip adding this to participants list
                        
                        # Use provided name or fallback to phone/formatted phone
                        if cleaned_name:
                            display_name = cleaned_name
                        elif formatted_phone != "Numéro inconnu":
                            display_name = "Inconnu"
                        else:
                            display_name = "Inconnu"
                        
                        participants.append({
                            'jid': member_jid,
                            'name': display_name,
                            'phone': phone,
                            'formatted_phone': formatted_phone
                        })
                
                # Add "me" to the group participants with the detected phone number
                participants.append({
                    'jid': 'me',
                    'name': 'Moi',
                    'phone': None,
                    'formatted_phone': my_phone_number if my_phone_number else 'Mon numéro'
                })
                
            else:
                # For individual conversations, get both participants
                # Get the contact
                contact_name = self.get_contact_name(contact_jid)
                phone = extract_phone_number(contact_jid)
                formatted_phone = format_phone_number(phone) if phone else "Numéro inconnu"
                
                participants.append({
                    'jid': contact_jid,
                    'name': contact_name if contact_name != contact_jid else "Inconnu",
                    'phone': phone,
                    'formatted_phone': formatted_phone
                })
                
                # Add "me"
                participants.append({
                    'jid': 'me',
                    'name': 'Moi',
                    'phone': None,
                    'formatted_phone': 'Moi'
                })
            
            return participants
            
        except Exception as e:
            print(f"⚠️ Error getting conversation participants: {e}")
            return []
    
    def get_group_unique_initials(self, group_jid):
        """Get unique initials for all group members."""
        try:
            members = self.db_manager.fetch_all("""
                SELECT DISTINCT gm.ZMEMBERJID, cs.ZPARTNERNAME
                FROM ZWAGROUPMEMBER gm
                LEFT JOIN ZWACHATSESSION cs ON gm.ZMEMBERJID = cs.ZCONTACTJID
                LEFT JOIN ZWACHATSESSION gs ON gs.ZCONTACTJID = ?
                WHERE gm.ZCHATSESSION = gs.Z_PK
            """, (group_jid,))
            
            # Collect all names
            member_names = {}
            for jid, name in members:
                if jid and name:
                    member_names[jid] = clean_contact_name(name)
            
            # Generate initials, handling conflicts
            initials_map = {}
            used_initials = set()
            
            for jid, name in member_names.items():
                basic_initials = get_initials(name)
                
                # Handle conflicts by adding numbers
                final_initials = basic_initials
                counter = 1
                while final_initials in used_initials:
                    final_initials = f"{basic_initials}{counter}"
                    counter += 1
                
                initials_map[jid] = final_initials
                used_initials.add(final_initials)
            
            return initials_map
            
        except Exception as e:
            print(f"⚠️ Error getting group initials: {e}")
            return {}
    
    def get_group_initials_for_jid(self, group_jid, member_jid):
        """Get unique initials for a specific member in a group."""
        # Cache group initials to avoid recalculating
        cache_key = f"group_initials_{group_jid}"
        if not hasattr(self, '_group_initials_cache'):
            self._group_initials_cache = {}
        
        if cache_key not in self._group_initials_cache:
            self._group_initials_cache[cache_key] = self.get_group_unique_initials(group_jid)
        
        return self._group_initials_cache[cache_key].get(member_jid, "?")