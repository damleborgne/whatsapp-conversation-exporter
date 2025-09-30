#!/usr/bin/env python3
"""
WhatsApp Conversation Exporter - Main Entry Point
===============================================

Exports WhatsApp conversations with citations, forwards, reactions, and mood analysis.

Usage:
    python main.py --contact "Name"
    python main.py --limit 100
    python main.py

Author: Damien Le Borgne & AI Assistant
Date: September 2025
"""

import sys
import os
import argparse
from whatsapp_exporter import WhatsAppExporter


def main():
    """Main function."""
    print("💬 WHATSAPP CONVERSATION EXPORTER")
    print("=" * 60)
    print("📝 Export conversations with citations, forwards, reactions, and mood analysis")
    print()
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Export WhatsApp conversations')
    parser.add_argument('--contact', help='Specific contact name to export')
    parser.add_argument('--limit', type=int, help='Limit number of messages per conversation')
    parser.add_argument('--recent', action='store_true', help='Get most recent messages instead of oldest')
    parser.add_argument('--backup', action='store_true', help='Use backup mode (wtsexporter format)')
    parser.add_argument('--backup-path', help='Path to backup directory (default: ../wtsexport)')
    args = parser.parse_args()
    
    # Determine mode and paths
    backup_mode = args.backup
    backup_path = args.backup_path
    contact_name = args.contact
    limit = args.limit
    recent = args.recent
    
    # If no arguments provided, run interactive mode
    if len(sys.argv) == 1:
        print("🔧 INTERACTIVE MODE")
        print("=" * 40)
        print("Choose data source:")
        print("1. 📱 Local WhatsApp client data")
        print("2. 📦 iOS backup extracted by wtsexporter")
        print("3. 📋 List all contacts with phone numbers")
        print()
        
        while True:
            choice = input("Enter choice (1, 2, or 3): ").strip()
            if choice == "1":
                backup_mode = False
                backup_path = None
                print("✅ Using local WhatsApp client data")
                break
            elif choice == "2":
                backup_mode = True
                default_path = "../wtsexport"
                print(f"📂 Default backup path: {default_path}")
                user_path = input(f"Enter backup path (or press Enter for default): ").strip()
                backup_path = user_path if user_path else default_path
                print(f"✅ Using backup data from: {backup_path}")
                break
            elif choice == "3":
                # List contacts mode
                print("📋 CONTACTS LIST MODE")
                backup_mode_choice = input("Use backup mode? (y/N): ").strip().lower()
                backup_mode = backup_mode_choice in ['y', 'yes']
                
                if backup_mode:
                    default_path = "../wtsexport"
                    user_path = input(f"Enter backup path (default: {default_path}): ").strip()
                    backup_path = user_path if user_path else default_path
                else:
                    backup_path = None
                
                try:
                    exporter = WhatsAppExporter(backup_mode=backup_mode, backup_base_path=backup_path)
                    contacts = exporter.get_all_contacts()
                    
                    print(f"\n📊 Found {len(contacts)} contacts:")
                    print("=" * 80)
                    
                    for i, contact in enumerate(contacts, 1):
                        contact_type = "📱 Group" if contact['is_group'] else "👤 Contact"
                        phone_info = f" ({contact['formatted_phone']})" if contact['formatted_phone'] else ""
                        print(f"{i:3d}. {contact_type}: {contact['name']}{phone_info}")
                        if contact['is_group'] and contact['phone']:
                            print(f"     👑 Creator: {contact['formatted_phone']}")
                    
                    print("\n📋 Export options:")
                    print("1. Export specific contact by number")
                    print("2. Export all contacts")
                    print("3. Exit")
                    
                    sub_choice = input("\nEnter choice: ").strip()
                    if sub_choice == "1":
                        contact_input = input("Enter contact name or phone number: ").strip()
                        result = exporter.export_conversation(contact_input)
                        if result:
                            print(f"\n🎉 Export successful!")
                            print(f"📁 File: {result}")
                        return
                    elif sub_choice == "2":
                        # Continue with full export
                        contact_name = None
                        limit = None
                        recent = False
                        break
                    else:
                        return
                        
                except Exception as e:
                    print(f"❌ Error: {e}")
                    return
                finally:
                    if 'exporter' in locals():
                        exporter.close()
                return
            else:
                print("❌ Invalid choice. Please enter 1, 2, or 3.")
    
    # Show mode
    if backup_mode:
        print(f"📦 Using backup mode with path: {backup_path}")
    else:
        print("📱 Using local WhatsApp mode")
    
    try:
        # Initialize exporter
        exporter = WhatsAppExporter(backup_mode=backup_mode, backup_base_path=backup_path)
        
        # Single contact export
        if contact_name:
            print(f"🎯 Single contact export: {contact_name}")
            result = exporter.export_conversation(contact_name, backup_mode, limit, recent)
            
            if result:
                print(f"\n🎉 Export successful!")
                print(f"📁 File: {result}")
            else:
                print("❌ Export failed")
                # Show available contacts with reactions
                contacts = exporter.get_contacts_with_reactions()[:10]  # Top 10
                if contacts:
                    print("Available contacts with reactions:")
                    for i, contact in enumerate(contacts, 1):
                        print(f"  {i}. {contact['name']}")
            return
        
        # Multiple contacts export
        print("🔍 Getting all contacts...")
        contacts = exporter.get_all_contacts()
        
        if not contacts:
            print("❌ No contacts found")
            return
        
        print(f"📊 Found {len(contacts)} contacts and groups")
        print("=" * 60)
        
        # Export each contact
        exported_files = []
        total_reactions = 0
        
        try:
            for i, contact in enumerate(contacts, 1):
                print(f"\n📝 [{i}/{len(contacts)}] Exporting: {contact['name']}")
                if contact['reaction_count'] > 0:
                    print(f"   📊 Has {contact['reaction_count']} reaction messages")
                
                try:
                    result = exporter.export_conversation(contact['jid'], None, limit, False)
                    
                    if result:
                        exported_files.append({
                            'contact': contact['name'],
                            'file': result,
                            'size': os.path.getsize(result),
                            'reactions': contact['reaction_count']
                        })
                        total_reactions += contact['reaction_count']
                        print(f"   ✅ Exported to: {os.path.basename(result)}")
                    else:
                        print(f"   ❌ Failed to export {contact['name']}")
                except Exception as e:
                    print(f"   ❌ Error exporting {contact['name']}: {e}")
                    # Reset connection on error to prevent database lock issues
                    exporter.close()
                    exporter = WhatsAppExporter(backup_mode=backup_mode, backup_base_path=backup_path)
                    continue
        except KeyboardInterrupt:
            print(f"\n⏹️ Export interrupted by user")
        
        # Summary
        print("\n" + "=" * 80)
        print("🎉 EXPORT SUMMARY")
        print("=" * 80)
        print(f"📊 Total contacts processed: {len(contacts)}")
        print(f"✅ Successfully exported: {len(exported_files)}")
        print(f"🎯 Total reaction messages: {total_reactions}")
        
        total_size = sum(f['size'] for f in exported_files)
        print(f"📄 Total export size: {total_size:,} bytes ({total_size/1024/1024:.1f} MB)")
        
        print(f"\n📁 Exported files:")
        for i, exp in enumerate(exported_files, 1):
            size_kb = exp['size'] / 1024
            # Find contact info for phone number display
            contact_info = next((c for c in contacts if c['name'] == exp['contact']), None)
            phone_display = f" ({contact_info['formatted_phone']})" if contact_info and contact_info['formatted_phone'] else ""
            
            print(f"  {i:2d}. {exp['contact']}{phone_display}")
            print(f"      📄 {os.path.basename(exp['file'])} ({size_kb:.1f} KB, {exp['reactions']} reactions)")
        
        print(f"\n🎉 All conversations exported successfully!")
        print(f"📂 Files are saved in the 'conversations' directory.")
        
    except FileNotFoundError as e:
        print(f"❌ {e}")
        print("💡 Make sure WhatsApp is installed and has been used on this computer.")
        if not backup_mode:
            print("💡 Alternatively, try using backup mode with --backup flag.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'exporter' in locals():
            exporter.close()


if __name__ == "__main__":
    main()