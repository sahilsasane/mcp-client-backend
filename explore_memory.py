#!/usr/bin/env python3
"""
Script to explore the chat_memory.pkl file contents
"""

import json
import pickle
from datetime import datetime
from pprint import pprint


def explore_pickle_file(filename="chat_memory.pkl"):
    """Explore the contents of the pickle file"""
    try:
        print(f"🔍 Exploring {filename}...")
        print("=" * 50)

        with open(filename, "rb") as f:
            data = pickle.load(f)

        print("📊 TOP-LEVEL STRUCTURE:")
        print(f"Type: {type(data)}")
        if isinstance(data, dict):
            print(f"Keys: {list(data.keys())}")
        print()

        # Show current session info
        current_session_id = data.get("current_session_id")
        print(f"🎯 CURRENT SESSION ID: {current_session_id}")
        print()

        # Show sessions overview
        sessions = data.get("sessions", {})
        print(f"📋 SESSIONS OVERVIEW ({len(sessions)} total):")
        print("-" * 30)

        for i, (session_id, session_data) in enumerate(sessions.items(), 1):
            is_current = "👉 CURRENT" if session_id == current_session_id else ""
            print(f"{i}. {session_data['title']} {is_current}")
            print(f"   ID: {session_id}")
            print(f"   Created: {session_data['created_at']}")
            print(f"   Last Activity: {session_data['last_activity']}")
            print(f"   Messages: {len(session_data['messages'])}")
            print()

        return data

    except FileNotFoundError:
        print(f"❌ File {filename} not found")
        return None
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return None


def explore_session_details(data, session_index=1):
    """Explore details of a specific session"""
    sessions = data.get("sessions", {})
    session_items = list(sessions.items())

    if session_index > len(session_items):
        print(f"❌ Session index {session_index} out of range (1-{len(session_items)})")
        return

    session_id, session_data = session_items[session_index - 1]

    print(f"🔎 DETAILED VIEW - SESSION {session_index}")
    print("=" * 50)
    print(f"Title: {session_data['title']}")
    print(f"ID: {session_id}")
    print(f"Created: {session_data['created_at']}")
    print(f"Last Activity: {session_data['last_activity']}")
    print(f"Context: {session_data.get('context', {})}")
    print()

    messages = session_data["messages"]
    print(f"💬 MESSAGES ({len(messages)} total):")
    print("-" * 30)

    for i, msg in enumerate(messages, 1):
        role_emoji = {"user": "👤", "assistant": "🤖", "tool": "🔧", "system": "⚙️"}.get(
            msg["role"], "❓"
        )

        timestamp = datetime.fromisoformat(msg["timestamp"]).strftime("%H:%M:%S")
        content_preview = msg["content"][:100] + (
            "..." if len(msg["content"]) > 100 else ""
        )

        print(f"{i}. {role_emoji} [{timestamp}] {msg['role'].upper()}")
        print(f"   Content: {content_preview}")

        if msg.get("tool_calls"):
            print(f"   Tool Calls: {len(msg['tool_calls'])}")
            for tc in msg["tool_calls"]:
                print(f"     - {tc['function']['name']}")

        if msg.get("tool_call_id"):
            print(f"   Tool Call ID: {msg['tool_call_id']}")

        print()


def export_to_json(data, output_file="chat_memory_export.json"):
    """Export pickle data to JSON for easier viewing"""
    try:
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"✅ Exported to {output_file}")
    except Exception as e:
        print(f"❌ Error exporting: {e}")


def main():
    """Main exploration function"""
    print("🧠 CHAT MEMORY EXPLORER")
    print("=" * 50)

    # Load and explore the pickle file
    data = explore_pickle_file()

    if not data:
        return

    sessions = data.get("sessions", {})
    if not sessions:
        print("No sessions found in the file.")
        return

    # Show menu
    while True:
        print("\n🔧 EXPLORATION OPTIONS:")
        print("1. Show session overview (default)")
        print("2. Explore specific session details")
        print("3. Export to JSON")
        print("4. Show raw data structure")
        print("5. Exit")

        choice = input("\nEnter choice (1-5, default=1): ").strip() or "1"

        if choice == "1":
            explore_pickle_file()

        elif choice == "2":
            session_num = input(f"Enter session number (1-{len(sessions)}): ").strip()
            try:
                session_index = int(session_num)
                explore_session_details(data, session_index)
            except ValueError:
                print("❌ Invalid session number")

        elif choice == "3":
            export_to_json(data)

        elif choice == "4":
            print("\n📄 RAW DATA STRUCTURE:")
            print("-" * 30)
            pprint(data, depth=3)

        elif choice == "5":
            print("👋 Goodbye!")
            break

        else:
            print("❌ Invalid choice")


if __name__ == "__main__":
    main()
