"""
Mood analysis and timeline generation for WhatsApp conversations.
"""

import re
from datetime import datetime, timedelta


class MoodAnalyzer:
    """Analyzes mood evolution based on emojis in messages and reactions over time."""
    
    def __init__(self):
        """Initialize mood analyzer."""
        # Define mood categories for different emoji reactions AND message content
        self.mood_categories = {
            # Positive emotions - Joy/Laughter
            '😂': 'joy', '🤣': 'joy', '😄': 'joy', '😆': 'joy', '😁': 'joy', '😀': 'joy', '🤪': 'joy',
            '😃': 'joy',
            
            # Positive emotions - Happiness/Contentment  
            '😊': 'happiness', '🙂': 'happiness', '😋': 'happiness', '😌': 'happiness', '😇': 'happiness', 
            '☺️': 'happiness', '😸': 'happiness', '😺': 'happiness', '☺': 'happiness',
            
            # Love/Affection
            '😍': 'love', '🥰': 'love', '😘': 'love', '😗': 'love', '😙': 'love', '😚': 'love',
            '💕': 'love', '❤️': 'love', '💖': 'love', '💗': 'love', '💘': 'love', '💝': 'love',
            '🤗': 'love', '💋': 'love', '😻': 'love', '❤': 'love', '💜': 'love', '💙': 'love',
            '💛': 'love', '💚': 'love', '♥': 'love', '🌹': 'love', '🌺': 'love',
            
            # Approval/Support
            '👍': 'approval', '👌': 'approval', '👏': 'approval', '🤝': 'approval', '✨': 'approval',
            '💯': 'approval', '🆒': 'approval', '✅': 'approval', '🙏': 'approval',
            
            # Celebration/Excitement
            '🙌': 'celebration', '🎉': 'celebration', '🥳': 'celebration', '🎊': 'celebration',
            '🎈': 'celebration', '🎆': 'celebration', '🎇': 'celebration', '🎂': 'celebration',
            '🎁': 'celebration', '🎄': 'celebration', '🍾': 'celebration',
            
            # Cool/Confidence
            '😎': 'cool', '🔥': 'excitement', '💪': 'strength', '⚡': 'excitement',
            
            # Negative emotions - Sadness/Disappointment
            '😢': 'sadness', '😭': 'sadness', '😞': 'sadness', '😔': 'disappointment', '☹️': 'sadness',
            '😿': 'sadness', '💔': 'sadness', '😪': 'sadness', '😥': 'sadness', '😓': 'disappointment',
            '😩': 'sadness', '😫': 'sadness', '😣': 'sadness',
            
            # Negative emotions - Anger/Frustration
            '😠': 'anger', '😡': 'anger', '🤬': 'anger', '😤': 'anger', '💢': 'anger',
            '🔴': 'anger', '😾': 'anger', '😖': 'anger',

            # Fear/Shock/Anxiety
            '😱': 'shock', '😨': 'fear', '😰': 'anxiety', '😟': 'anxiety', '😧': 'fear',
            '🙀': 'shock', '😬': 'anxiety', '😵': 'shock', '🥶': 'fear',
            
            # Surprise/Wonder
            '😮': 'surprise', '😯': 'surprise', '😲': 'surprise', '🤯': 'shock', '😳': 'surprise',
            
            # Thinking/Contemplation
            '🤔': 'thinking', '🧐': 'thinking', '🤨': 'skepticism', '💭': 'thinking',
            
            # Confusion/Uncertainty
            '🤷': 'confusion', '😕': 'confusion', '😵‍💫': 'confusion', '🙃': 'confusion',
            
            # Neutral/Indifferent
            '😐': 'neutral', '😑': 'neutral', '😶': 'neutral', '🫤': 'neutral',
            
            # Skepticism/Dismissal
            '🙄': 'skepticism', '😒': 'skepticism', '😏': 'skepticism',
            
            # Tiredness/Boredom
            '😴': 'tired', '🥱': 'tired',
            
            # Playful/Mischievous/Flirty
            '😜': 'playful', '😝': 'playful', '😛': 'playful', '🤭': 'playful',
            '😉': 'playful', '😅': 'playful',
            
            # Miscellaneous positive
            '👎': 'disapproval', '💫': 'misc', '🎶': 'misc', '🍀': 'misc',
            '🕺': 'celebration', '🏃': 'misc',
        }
        
        # Add mood_emojis mapping
        self.mood_emojis = {
            'joy': '😂',
            'happiness': '😊',
            'love': '❤️',
            'approval': '👍',
            'celebration': '🎉',
            'cool': '😎',
            'excitement': '🔥',
            'strength': '💪',
            'sadness': '😢',
            'disappointment': '😔',
            'anger': '😡',
            'shock': '😱',
            'fear': '😨',
            'anxiety': '😰',
            'surprise': '😮',
            'thinking': '🤔',
            'confusion': '🤷',
            'neutral': '😐',
            'skepticism': '🙄',
            'tired': '😴',
            'playful': '😜',
            'disapproval': '👎',
            'misc': '💫'
        }
        
        # Emoji pattern for extracting emojis from message content
        self.emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)

    def analyze_mood_timeline(self, messages):
        """
        Analyze mood evolution over time based on emojis in message reactions AND content.
        
        Args:
            messages: List of message dictionaries containing date, content, and reaction_emoji
            
        Returns:
            dict: Timeline data including weekly breakdown and statistics
        """
        if not messages:
            return None
        
        # Extract reactions with timestamps AND emojis from message content
        reactions_timeline = []
        
        for msg in messages:
            # Process reaction emojis
            if msg.get('reaction_emoji') and msg.get('date'):
                try:
                    # Parse the reaction emoji(s)
                    reaction_text = msg['reaction_emoji']
                    
                    # Handle group reactions format [AB:😂;CD:😍] or simple reactions [😂]
                    if reaction_text.startswith('[') and reaction_text.endswith(']'):
                        reaction_content = reaction_text[1:-1]  # Remove brackets
                        
                        # Check if it's a group reaction (contains :)
                        if ':' in reaction_content:
                            # Group reactions - parse each individual reaction
                            individual_reactions = reaction_content.split(';')
                            
                            for reaction_item in individual_reactions:
                                if ':' in reaction_item:
                                    person, emoji = reaction_item.split(':', 1)
                                    mood = self.mood_categories.get(emoji, 'unknown')
                                    if mood != 'unknown':
                                        reactions_timeline.append({
                                            'date': msg['date'],
                                            'emoji': emoji,
                                            'mood': mood,
                                            'person': person.strip(),
                                            'is_group': True,
                                            'source': 'reaction'
                                        })
                        else:
                            # Simple reaction in brackets [😂] - just extract the emoji
                            emoji = reaction_content
                            mood = self.mood_categories.get(emoji, 'unknown')
                            if mood != 'unknown':
                                reactions_timeline.append({
                                    'date': msg['date'],
                                    'emoji': emoji,
                                    'mood': mood,
                                    'person': 'Contact' if not msg.get('is_from_me') else 'Moi',
                                    'is_group': False,
                                    'source': 'reaction'
                                })
                    else:
                        # Individual reaction
                        emoji = reaction_text.strip()
                        mood = self.mood_categories.get(emoji, 'unknown')
                        if mood != 'unknown':
                            reactions_timeline.append({
                                'date': msg['date'],
                                'emoji': emoji,
                                'mood': mood,
                                'person': 'Contact' if not msg.get('is_from_me') else 'Moi',
                                'is_group': False,
                                'source': 'reaction'
                            })
                except Exception:
                    continue
            
            # Process emojis from message content
            if msg.get('content') and msg.get('date'):
                try:
                    content = msg['content']
                    content_emojis = self.emoji_pattern.findall(content)
                    for emoji_group in content_emojis:
                        # Extract individual emojis from each match
                        for char in emoji_group:
                            if char in self.mood_categories:
                                reactions_timeline.append({
                                    'date': msg['date'],
                                    'emoji': char,
                                    'mood': self.mood_categories[char],
                                    'person': 'Contact' if not msg.get('is_from_me') else 'Moi',
                                    'is_group': msg.get('chat_name') is not None,
                                    'source': 'content'
                                })
                except Exception:
                    continue
        
        if not reactions_timeline:
            return None
        
        # Sort by date
        reactions_timeline.sort(key=lambda x: x['date'])
        
        # Create weekly timeline
        weekly_timeline = self._create_weekly_timeline(messages, reactions_timeline)
        
        # Calculate statistics
        total_from_reactions = len([r for r in reactions_timeline if r['source'] == 'reaction'])
        total_from_content = len([r for r in reactions_timeline if r['source'] == 'content'])
        
        return {
            'weekly_timeline': weekly_timeline,
            'total_reactions': len(reactions_timeline),
            'total_from_reactions': total_from_reactions,
            'total_from_content': total_from_content,
            'start_date': reactions_timeline[0]['date'] if reactions_timeline else None,
            'end_date': reactions_timeline[-1]['date'] if reactions_timeline else None
        }
    
    def _create_weekly_timeline(self, messages, reactions_timeline):
        """Create a compact weekly timeline with one character per week, organized by year."""
        if not messages:
            return []
        
        try:
            # Get conversation date range
            start_date = datetime.strptime(messages[0]['date'], '%Y-%m-%d %H:%M:%S')
            end_date = datetime.strptime(messages[-1]['date'], '%Y-%m-%d %H:%M:%S')
            
            # Find the Monday of the first week and the Sunday of the last week at MIDNIGHT
            start_monday = start_date - timedelta(days=start_date.weekday())
            start_monday = start_monday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_sunday = end_date + timedelta(days=(6 - end_date.weekday()))
            end_sunday = end_sunday.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Create weekly buckets
            weekly_moods = {}
            weekly_activity = {}
            
            # First, mark weeks with any conversation activity
            for msg in messages:
                try:
                    msg_date = datetime.strptime(msg['date'], '%Y-%m-%d %H:%M:%S')
                    week_start = msg_date - timedelta(days=msg_date.weekday())
                    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
                    week_key = week_start.strftime('%Y-%m-%d')
                    
                    if week_key not in weekly_activity:
                        weekly_activity[week_key] = 0
                    weekly_activity[week_key] += 1
                except Exception:
                    continue
            
            # Then, analyze mood for weeks with reactions
            for reaction in reactions_timeline:
                try:
                    reaction_date = datetime.strptime(reaction['date'], '%Y-%m-%d %H:%M:%S')
                    week_start = reaction_date - timedelta(days=reaction_date.weekday())
                    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
                    week_key = week_start.strftime('%Y-%m-%d')
                    
                    if week_key not in weekly_moods:
                        weekly_moods[week_key] = {}
                    
                    mood = reaction['mood']
                    if mood not in weekly_moods[week_key]:
                        weekly_moods[week_key][mood] = 0
                    weekly_moods[week_key][mood] += 1
                except Exception:
                    continue
            
            # Build timeline string by year
            timeline_lines = []
            current_week = start_monday
            current_year = None
            year_chars = []
            
            while current_week <= end_sunday:
                week_year = current_week.year
                week_key = current_week.strftime('%Y-%m-%d')
                
                # If we've moved to a new year, save the previous year's line
                if current_year is not None and week_year != current_year:
                    if year_chars:
                        timeline_str = ''.join(year_chars)
                        start_marker = str(current_year)
                        timeline_lines.append(f"{start_marker}: {timeline_str}")
                    year_chars = []
                
                current_year = week_year
                
                # Determine character for this week
                if week_key in weekly_moods and weekly_moods[week_key]:
                    # Week has reactions - find dominant mood
                    dominant_mood = max(weekly_moods[week_key].items(), key=lambda x: x[1])[0]
                    mood_emoji = self._get_mood_emoji(dominant_mood)
                    year_chars.append(mood_emoji)
                elif week_key in weekly_activity and weekly_activity[week_key] > 0:
                    # Week has messages but no reactions - use underscore for regular width
                    year_chars.append('＿')
                else:
                    # No activity this week - use space for clear separation
                    year_chars.append('　')
                
                current_week += timedelta(weeks=1)
            
            # Add the last year
            if year_chars and current_year:
                timeline_str = ''.join(year_chars)
                start_marker = str(current_year)
                timeline_lines.append(f"{start_marker}: {timeline_str}")
            
            return timeline_lines
            
        except Exception as e:
            print(f"⚠️ Error creating weekly timeline: {e}")
            return []
    
    def _get_mood_emoji(self, mood):
        """Get representative emoji for a mood category."""
        return self.mood_emojis.get(mood, '📝')