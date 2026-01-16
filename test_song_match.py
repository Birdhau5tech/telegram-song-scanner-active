"""Test script to demonstrate song matching."""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.text_processing.message_parser import message_parser
from src.music_matching.musicbrainz_client import musicbrainz_client
from src.music_matching.fuzzy_matcher import fuzzy_matcher

def test_song_matching(message: str):
    """Test the complete song matching flow."""
    print(f"\n{'='*60}")
    print(f"Input message: {message}")
    print('='*60)
    
    # Step 1: Parse the message to extract song candidates
    print("\n📝 Step 1: Extracting songs from message...")
    candidates = message_parser.parse(message)
    
    if not candidates:
        print("❌ No songs found in message")
        return
    
    for i, candidate in enumerate(candidates, 1):
        print(f"\n  Song {i}:")
        print(f"    Title: {candidate.get('title', 'Unknown')}")
        print(f"    Artist: {candidate.get('artist', 'Unknown')}")
        print(f"    Confidence: {candidate.get('confidence', 0)}%")
        print(f"    Method: {candidate.get('extraction_method', 'unknown')}")
    
    # Step 2: Search MusicBrainz for each candidate
    print("\n🔍 Step 2: Searching MusicBrainz...")
    
    for candidate in candidates:
        title = candidate.get('title')
        artist = candidate.get('artist')
        
        print(f"\n  Searching for: '{title}' by '{artist}'...")
        
        results = musicbrainz_client.search_song(title, artist)
        
        if results:
            print(f"  ✅ Found {len(results)} matches!")
            
            # Step 3: Use fuzzy matcher to get best match
            best_match, confidence = fuzzy_matcher.get_best_match(title, artist, results)
            
            if best_match:
                print(f"\n  🎵 Best Match:")
                print(f"    Title: {best_match.get('title')}")
                artist_name = "Unknown"
                if best_match.get('artist_credits'):
                    artist_name = best_match['artist_credits'][0].get('name', 'Unknown')
                print(f"    Artist: {artist_name}")
                print(f"    Confidence: {confidence}%")
                print(f"    MusicBrainz ID: {best_match.get('musicbrainz_id', 'N/A')}")
            else:
                print("  ⚠️ No confident match found")
        else:
            print("  ❌ No results from MusicBrainz")
    
    print(f"\n{'='*60}")
    print("✅ Test complete!")
    print('='*60)

if __name__ == "__main__":
    # Test with some example messages
    test_messages = [
        "I want to hear Bohemian Rhapsody by Queen",
        "Can you play Blinding Lights by The Weeknd?",
        "Play Shape of You",
    ]
    
    for msg in test_messages:
        test_song_matching(msg)
        print("\n")
