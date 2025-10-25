#!/usr/bin/env python3
"""Debug script to analyze mood timeline generation for a given contact."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from whatsapp_exporter.core import WhatsAppExporter
from datetime import datetime, timedelta
from collections import Counter

def analyze_mood_timeline(contact_name, weeks_to_analyze=5):
    """Analyze mood timeline generation in detail."""
    
    # Initialize exporter
    exporter = WhatsAppExporter(backup_mode=True, backup_base_path='../wtsexport')
    
    # Import mood analyzer
    from whatsapp_exporter.mood_analyzer import MoodAnalyzer
    mood_analyzer = MoodAnalyzer()
    
    # Find contact
    target_contact = exporter._find_contact(contact_name)
    if not target_contact:
        print(f"❌ Contact not found: {contact_name}")
        return
    
    print(f"✅ Found contact: {target_contact['name']} ({target_contact['jid']})")
    
    # Get all messages
    messages = exporter._get_conversation_messages(target_contact['jid'])
    print(f"📋 Total messages: {len(messages)}")
    
    # Debug: Check if reactions are loaded
    messages_with_reactions = [m for m in messages if m.get('reaction_emoji')]
    print(f"🎭 Messages with reactions: {len(messages_with_reactions)}")
    if messages_with_reactions:
        print(f"   Example reactions: {messages_with_reactions[:3]}")
    
    # Filter messages from 2023
    messages_2023 = [m for m in messages if m.get('date', '').startswith('2023')]
    print(f"📅 Messages in 2023: {len(messages_2023)}")
    
    if not messages_2023:
        print("❌ No messages found in 2023")
        return
    
    # Get first message date
    first_date = datetime.strptime(messages_2023[0]['date'], '%Y-%m-%d %H:%M:%S')
    print(f"📅 First message: {first_date}")
    
    # Find the Monday of the first week at MIDNIGHT (not at the message time!)
    start_monday = first_date - timedelta(days=first_date.weekday())
    start_monday = start_monday.replace(hour=0, minute=0, second=0, microsecond=0)
    print(f"📅 First Monday: {start_monday} (at midnight)")
    
    # Run mood_analyzer and compare
    print(f"\n{'='*80}")
    print("RUNNING MOOD_ANALYZER TO COMPARE")
    print(f"{'='*80}")
    mood_analysis = mood_analyzer.analyze_mood_timeline(messages_2023)
    if mood_analysis:
        print(f"✅ Mood analysis successful:")
        print(f"   Total reactions: {mood_analysis['total_reactions']}")
        print(f"   From reactions: {mood_analysis['total_from_reactions']}")
        print(f"   From content: {mood_analysis['total_from_content']}")
        print(f"\n📊 Weekly timeline:")
        for line in mood_analysis['weekly_timeline']:
            print(f"   {line}")
        print(f"\n   First 3 characters: {mood_analysis['weekly_timeline'][0][6:9] if mood_analysis['weekly_timeline'] else 'N/A'}")
    print(f"{'='*80}\n")
    
    # Analyze first N weeks
    for week_num in range(weeks_to_analyze):
        week_start = start_monday + timedelta(weeks=week_num)
        week_end = week_start + timedelta(days=7)
        
        print(f"\n{'='*80}")
        print(f"WEEK {week_num + 1}: {week_start.date()} to {week_end.date()}")
        print(f"{'='*80}")
        
        # Get messages for this week
        week_messages = [
            m for m in messages_2023
            if week_start <= datetime.strptime(m['date'], '%Y-%m-%d %H:%M:%S') < week_end
        ]
        
        print(f"📨 Messages in this week: {len(week_messages)}")
        
        if not week_messages:
            print("❌ No messages in this week → Timeline char: '　' (space)")
            continue
        
        # Count MOODS from reactions AND content (following mood_analyzer logic exactly)
        mood_counter = Counter()
        reaction_details = []  # Store details for debugging
        
        for msg in week_messages:
            # 1. Process reaction emojis
            if msg.get('reaction_emoji'):
                reaction_text = msg['reaction_emoji']
                
                # DEBUG: Check for specific message
                if '🥰' in reaction_text:
                    print(f"   🔍 DEBUG: Found message with 🥰 reaction")
                    print(f"      Date: {msg.get('date')}")
                    print(f"      Reaction text: {repr(reaction_text)}")
                
                # Handle group reactions format [AB:😂;CD:😍] or multiple reactions
                if reaction_text.startswith('[') and reaction_text.endswith(']'):
                    reaction_content = reaction_text[1:-1]  # Remove brackets
                    
                    # Check if it's a group reaction (contains :)
                    if ':' in reaction_content:
                        # Group reactions - parse each individual reaction
                        individual_reactions = reaction_content.split(';')
                        
                        for reaction_item in individual_reactions:
                            if ':' in reaction_item:
                                person, emoji = reaction_item.split(':', 1)
                                mood = mood_analyzer.mood_categories.get(emoji, 'unknown')
                                if mood != 'unknown':
                                    mood_counter[mood] += 1
                                    reaction_details.append({
                                        'source': 'reaction',
                                        'emoji': emoji,
                                        'mood': mood,
                                        'date': msg.get('date', '')[:10]
                                    })
                    else:
                        # Simple reaction in brackets [😂] - just extract the emoji
                        emoji = reaction_content
                        mood = mood_analyzer.mood_categories.get(emoji, 'unknown')
                        if mood != 'unknown':
                            mood_counter[mood] += 1
                            reaction_details.append({
                                'source': 'reaction',
                                'emoji': emoji,
                                'mood': mood,
                                'date': msg.get('date', '')[:10]
                            })
                else:
                    # Individual reaction without brackets
                    emoji = reaction_text.strip()
                    mood = mood_analyzer.mood_categories.get(emoji, 'unknown')
                    if mood != 'unknown':
                        mood_counter[mood] += 1
                        reaction_details.append({
                            'source': 'reaction',
                            'emoji': emoji,
                            'mood': mood,
                            'date': msg.get('date', '')[:10]
                        })
            
            # 2. Process emojis from message content
            if msg.get('content'):
                content = msg['content']
                # Use mood_analyzer's emoji pattern
                content_emojis = mood_analyzer.emoji_pattern.findall(content)
                for emoji_group in content_emojis:
                    # Extract individual emojis from each match
                    for char in emoji_group:
                        if char in mood_analyzer.mood_categories:
                            mood = mood_analyzer.mood_categories[char]
                            mood_counter[mood] += 1
                            reaction_details.append({
                                'source': 'content',
                                'emoji': char,
                                'mood': mood,
                                'date': msg.get('date', '')[:10]
                            })
        
        total_mood_entries = len(reaction_details)
        from_reactions = len([r for r in reaction_details if r['source'] == 'reaction'])
        from_content = len([r for r in reaction_details if r['source'] == 'content'])
        
        print(f"💬 Mood entries: {total_mood_entries} total ({from_reactions} from reactions, {from_content} from content)")
        
        # DEBUG: Check for 🥰 specifically
        smiling_face_with_hearts = [r for r in reaction_details if r['emoji'] == '🥰']
        if smiling_face_with_hearts:
            print(f"   🔍 DEBUG: Found {len(smiling_face_with_hearts)} instances of 🥰")
            for r in smiling_face_with_hearts:
                print(f"      → {r}")
        
        print(f"\n� Mood categories with ALL emojis (from both sources):")
        if mood_counter:
            for mood, count in mood_counter.most_common(20):
                # Find ALL emojis that contributed to this mood
                contributing = [r for r in reaction_details if r['mood'] == mood]
                emoji_counts = Counter([r['emoji'] for r in contributing])
                
                # Show the mood category and its representative emoji
                representative = mood_analyzer.mood_emojis.get(mood, '📝')
                print(f"\n   {mood} → {representative} : {count} total")
                
                # List ALL individual emojis with their counts
                for emoji, emoji_count in emoji_counts.most_common():
                    # Show the actual emojis repeated (like you requested)
                    emoji_list = emoji * emoji_count
                    print(f"      {emoji}: {emoji_count} → {emoji_list}")
        else:
            print("   (no moods found)")
        
        # Determine dominant mood (using mood_analyzer logic)
        if mood_counter:
            # Remove 'unknown' moods if there are known moods
            known_moods = {m: c for m, c in mood_counter.items() if m != 'unknown'}
            if known_moods:
                mood_counter = Counter(known_moods)
            
            most_common = mood_counter.most_common(1)[0]
            dominant_mood = most_common[0]
            dominant_count = most_common[1]
            total_moods = sum(mood_counter.values())
            
            # Get representative emoji for this mood
            representative_emoji = mood_analyzer.mood_emojis.get(dominant_mood, '📝')
            
            print(f"\n🎯 Dominant mood: {dominant_mood} ({dominant_count}/{total_moods} = {dominant_count/total_moods*100:.1f}%)")
            print(f"✅ Timeline character: {representative_emoji} (representative of '{dominant_mood}')")
        elif len(week_messages) > 0:
            print(f"\n❌ No moods found (but {len(week_messages)} messages)")
            print(f"✅ Timeline character: ＿ (underscore for messages without moods)")
        else:
            print(f"\n❌ No activity")
            print(f"✅ Timeline character: 　 (space for no activity)")

if __name__ == '__main__':
    analyze_mood_timeline("Laure", weeks_to_analyze=5)
