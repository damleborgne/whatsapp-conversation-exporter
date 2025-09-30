"""
Mood analysis and timeline generation for WhatsApp conversations.
"""

from datetime import datetime, timedelta


class MoodAnalyzer:
    """Analyzes mood evolution based on reactions over time."""
    
    def __init__(self):
        """Initialize mood analyzer."""
        # Define mood categories for different emoji reactions
        self.mood_categories = {
            # Positive emotions
            '😂': 'joy', '🤣': 'joy', '😄': 'joy', '😆': 'joy', '😁': 'joy',
            '😊': 'happiness', '😍': 'love', '🥰': 'love', '😘': 'love', '💕': 'love', '❤️': 'love',
            '👍': 'approval', '👏': 'approval', '🙌': 'celebration', '🎉': 'celebration',
            '😎': 'cool', '🔥': 'excitement', '💪': 'strength',
            
            # Negative emotions
            '😢': 'sadness', '😭': 'sadness', '😞': 'sadness', '😔': 'disappointment',
            '😠': 'anger', '😡': 'anger', '🤬': 'anger',
            '😱': 'shock', '😨': 'fear', '😰': 'anxiety',
            
            # Neutral/Mixed emotions
            '😮': 'surprise', '😯': 'surprise', '🤔': 'thinking', '🤷': 'confusion',
            '😐': 'neutral', '😑': 'neutral', '🙄': 'skepticism'
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
            'skepticism': '🙄'
        }

    def analyze_mood_timeline(self, messages):
        """Analyze mood evolution based on reactions over time."""
        if not messages:
            return None
        
        # Extract reactions with timestamps
        reactions_timeline = []
        
        for msg in messages:
            if msg.get('reaction_emoji') and msg.get('date'):
                try:
                    # Parse the reaction emoji(s)
                    reaction_text = msg['reaction_emoji']
                    
                    # Handle group reactions format [AB:😂;CD:😍]
                    if reaction_text.startswith('[') and reaction_text.endswith(']'):
                        # Group reactions
                        reaction_content = reaction_text[1:-1]  # Remove brackets
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
                                        'is_group': True
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
                                'is_group': False
                            })
                except Exception:
                    continue
        
        if not reactions_timeline:
            return None
        
        # Sort by date
        reactions_timeline.sort(key=lambda x: x['date'])
        
        # Create weekly timeline
        weekly_timeline = self._create_weekly_timeline(messages, reactions_timeline)
        
        return {
            'weekly_timeline': weekly_timeline,
            'total_reactions': len(reactions_timeline),
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
            
            # Find the Monday of the first week and the Sunday of the last week
            start_monday = start_date - timedelta(days=start_date.weekday())
            end_sunday = end_date + timedelta(days=(6 - end_date.weekday()))
            
            # Create weekly buckets
            weekly_moods = {}
            weekly_activity = {}
            
            # First, mark weeks with any conversation activity
            for msg in messages:
                try:
                    msg_date = datetime.strptime(msg['date'], '%Y-%m-%d %H:%M:%S')
                    week_start = msg_date - timedelta(days=msg_date.weekday())
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