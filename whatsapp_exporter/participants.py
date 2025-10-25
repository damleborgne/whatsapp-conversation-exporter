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
        self._my_jid_cache = None  # Cache for "my" JID
    
    def _get_my_jid(self):
        """Get the JID of the database owner (the person running the export)."""
        if self._my_jid_cache:
            return self._my_jid_cache
        
        try:
            # Find JIDs that have "Vous" as name in group memberships
            result = self.db_manager.fetch_one("""
                SELECT DISTINCT gm.ZMEMBERJID 
                FROM ZWAGROUPMEMBER gm 
                LEFT JOIN ZWACHATSESSION cs ON gm.ZMEMBERJID = cs.ZCONTACTJID 
                WHERE cs.ZPARTNERNAME = 'Vous' OR cs.ZPARTNERNAME LIKE '%Vous%'
                LIMIT 1
            """)
            
            if result and result[0]:
                self._my_jid_cache = result[0]
                return self._my_jid_cache
            
            return None
        except Exception as e:
            print(f"⚠️ Error getting my JID: {e}")
            return None
    
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
                # Get initials map for this group (for display in header)
                initials_map = self.get_group_unique_initials(contact_jid)
                
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
                        # Skip @lid JIDs (they are duplicates)
                        if '@lid' in member_jid:
                            continue
                        
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
                        
                        # Get initials for this member
                        initials = initials_map.get(member_jid, None)
                        
                        participants.append({
                            'jid': member_jid,
                            'name': display_name,
                            'phone': phone,
                            'formatted_phone': formatted_phone,
                            'initials': initials
                        })
                
                # Add "me" to the group participants with the detected phone number
                # Get my own initials using my actual JID (not group owner)
                my_jid = self._get_my_jid()
                my_initials = initials_map.get(my_jid, None) if my_jid else None
                
                participants.append({
                    'jid': 'me',
                    'name': 'Moi',
                    'phone': None,
                    'formatted_phone': my_phone_number if my_phone_number else 'Mon numéro',
                    'initials': my_initials
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
                    'formatted_phone': formatted_phone,
                    'initials': None  # No initials for individual conversations
                })
                
                # Add "me"
                participants.append({
                    'jid': 'me',
                    'name': 'Moi',
                    'phone': None,
                    'formatted_phone': 'Moi',
                    'initials': None  # No initials for individual conversations
                })
            
            return participants
            
        except Exception as e:
            print(f"⚠️ Error getting conversation participants: {e}")
            return []
    
    def get_group_unique_initials(self, group_jid):
        """Get unique initials for all group members with smart conflict resolution."""
        try:
            # Get owner info first
            owner_jid = None
            owner_name = None
            if '-' in group_jid:
                owner_phone = group_jid.split('-')[0]
                owner_jid = f"{owner_phone}@s.whatsapp.net"
                # Try to get owner name from database
                result = self.db_manager.fetch_one(
                    "SELECT ZPUSHNAME FROM ZWAPROFILEPUSHNAME WHERE ZJID = ?",
                    (owner_jid,)
                )
                if result and result[0]:
                    owner_name = clean_contact_name(result[0])
            
            members = self.db_manager.fetch_all("""
                SELECT DISTINCT gm.ZMEMBERJID, cs.ZPARTNERNAME
                FROM ZWAGROUPMEMBER gm
                LEFT JOIN ZWACHATSESSION cs ON gm.ZMEMBERJID = cs.ZCONTACTJID
                LEFT JOIN ZWACHATSESSION gs ON gs.ZCONTACTJID = ?
                WHERE gm.ZCHATSESSION = gs.Z_PK
            """, (group_jid,))
            
            # Collect all names with their JIDs
            member_data = {}
            for jid, name in members:
                if jid:
                    # Skip @lid JIDs (they don't have proper names)
                    if '@lid' in jid:
                        continue
                    
                    # Try to get the real name from ZWAPROFILEPUSHNAME
                    push_name_result = self.db_manager.fetch_one(
                        "SELECT ZPUSHNAME FROM ZWAPROFILEPUSHNAME WHERE ZJID = ?",
                        (jid,)
                    )
                    
                    # Choose the most complete name (more words = better)
                    push_name = push_name_result[0] if push_name_result and push_name_result[0] else None
                    session_name = name if name else None
                    
                    # Special case: if session name is "Vous", always prefer push name
                    if session_name and clean_contact_name(session_name).lower() == 'vous':
                        if push_name:
                            cleaned_name = clean_contact_name(push_name)
                            member_data[jid] = cleaned_name
                        else:
                            # Fallback: keep "Vous" if no push name available
                            member_data[jid] = clean_contact_name(session_name)
                    else:
                        # Count words in each name
                        push_words = len(push_name.split()) if push_name else 0
                        session_words = len(session_name.split()) if session_name else 0
                        
                        if push_words > session_words:
                            # Push name is more complete
                            cleaned_name = clean_contact_name(push_name)
                            member_data[jid] = cleaned_name
                        elif session_name:
                            # Session name is more complete (or equal)
                            cleaned_name = clean_contact_name(session_name)
                            member_data[jid] = cleaned_name
                        elif push_name:
                            # Fallback to push name
                            cleaned_name = clean_contact_name(push_name)
                            member_data[jid] = cleaned_name
                        else:
                            # Last resort: look up by JID in ZWACHATSESSION
                            alt_result = self.db_manager.fetch_one(
                                "SELECT ZPARTNERNAME FROM ZWACHATSESSION WHERE ZCONTACTJID = ?",
                                (jid,)
                            )
                            if alt_result and alt_result[0]:
                                cleaned_name = clean_contact_name(alt_result[0])
                                member_data[jid] = cleaned_name
            
            # Add owner if we have the info and it's not already in the list
            if owner_jid and owner_name and owner_jid not in member_data:
                member_data[owner_jid] = owner_name
            
            # Helper function to extract last name initials
            def get_last_name_initials(last_name_full):
                """Extract initials from last name, preserving case for particles.
                Example: 'Le Borgne' -> 'LB', 'de Verdalle' -> 'dV'"""
                if not last_name_full:
                    return ""
                
                words = last_name_full.split()
                initials = []
                for word in words:
                    if word:  # Skip empty strings
                        initials.append(word[0])  # Keep original case
                return ''.join(initials)
            
            # First pass: Generate base initials (1 letter first name + last name initials)
            initials_map = {}
            conflicts = {}  # Track conflicts by initials
            
            for jid, name in member_data.items():
                parts = name.split()
                if len(parts) >= 2:
                    first_name = parts[0]
                    last_name_full = ' '.join(parts[1:])
                    
                    # Generate base initials: 1 letter from first + all initials from last
                    last_initials = get_last_name_initials(last_name_full)
                    base_initials = first_name[0].upper() + last_initials
                else:
                    # Single name (no last name): use 2 letters
                    base_initials = name[:min(2, len(name))].capitalize()
                
                if base_initials not in conflicts:
                    conflicts[base_initials] = []
                conflicts[base_initials].append((jid, name, parts[0] if len(parts) >= 2 else name, len(parts) >= 2))
            
            # Second pass: Resolve conflicts by using 2 letters from first name
            for base_initials, people in conflicts.items():
                if len(people) == 1:
                    # No conflict
                    jid, name, _, _ = people[0]
                    initials_map[jid] = base_initials
                else:
                    # Conflict: use 2 letters from first name for everyone
                    for jid, name, first_name, has_last_name in people:
                        if has_last_name:
                            # Use 2 letters from first name
                            parts = name.split()
                            last_name_full = ' '.join(parts[1:])
                            last_initials = get_last_name_initials(last_name_full)
                            resolved_initials = first_name[:2].capitalize() + last_initials
                        else:
                            # Single name: use 2 letters
                            resolved_initials = name[:min(2, len(name))].capitalize()
                        
                        initials_map[jid] = resolved_initials
            
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