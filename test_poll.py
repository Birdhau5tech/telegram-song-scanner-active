"""Full pipeline polling test - Telegram → Match → RadioDJ"""
import requests
import os
import time
import sys
from dotenv import load_dotenv

# Fix encoding for Windows
sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

# Set up env for RadioDJ
os.environ.setdefault('MARIADB_HOST', '127.0.0.1')
os.environ.setdefault('MARIADB_DATABASE', 'radiodj2')
os.environ.setdefault('MARIADB_USERNAME', 'root')
os.environ.setdefault('MARIADB_PASSWORD', 'finner25')

token = os.getenv('TELEGRAM_BOT_TOKEN')
base = f'https://api.telegram.org/bot{token}'

# Delete webhook
requests.post(f'{base}/deleteWebhook')
print('Webhook cleared. Waiting for messages... Send one to @Birdhau5bot now!')
print('Try: "Miguel Migs Tonight" or any song name')

# Initialize the full pipeline components
import sys
sys.path.insert(0, '.')
from config.database import SessionLocal
from src.text_processing.text_cleaner import text_cleaner
from src.text_processing.message_parser import message_parser
from src.music_matching.matching_orchestrator import matching_orchestrator
from src.radiodj_integration.radiodj_client import radiodj_client

print(f"RadioDJ connection: {radiodj_client.validate_connection()}")

offset = 0
for i in range(120):  # Poll for 2 minutes
    r = requests.get(f'{base}/getUpdates', params={'offset': offset, 'timeout': 2})
    data = r.json()
    if data.get('result'):
        for u in data['result']:
            offset = u['update_id'] + 1
            msg = u.get('message', {})
            txt = msg.get('text', '')
            chat_id = msg.get('chat', {}).get('id')
            sender = msg.get('from', {}).get('username', 'unknown')
            print(f'\n📩 Got: "{txt}" from @{sender}')
            
            # Step 1: Clean text
            cleaned = text_cleaner.clean(txt)
            print(f'  Cleaned: {cleaned}')
            
            # Step 2: Parse for song candidates
            candidates = message_parser.parse(cleaned)
            print(f'  Candidates: {candidates}')
            
            if not candidates:
                reply = "No song found. Try: 'Artist - Title'"
                requests.post(f'{base}/sendMessage', json={'chat_id': chat_id, 'text': reply})
                continue
            
            results = []
            for c in candidates:
                title = c.get('title', '')
                artist = c.get('artist', '')
                print(f'  Searching for: "{title}" by "{artist}"')
                
                # Step 3: Search MusicBrainz
                mb_results = matching_orchestrator.musicbrainz.search_song(title, artist)
                if mb_results:
                    best = mb_results[0]
                    matched_title = best.get('title', title)
                    matched_artist = ''
                    if best.get('artist_credits'):
                        matched_artist = best['artist_credits'][0].get('name', '')
                    print(f'  ✅ MusicBrainz match: {matched_title} by {matched_artist}')
                    
                    # Step 4: Search in RadioDJ library
                    track_id = radiodj_client.find_track_in_library(matched_artist, matched_title)
                    if track_id:
                        # Step 5: Add to queue
                        success = radiodj_client.add_track_to_queue_db(track_id)
                        if success:
                            results.append(f"✅ {matched_title} by {matched_artist} - Added to RadioDJ!")
                        else:
                            results.append(f"⚠️ {matched_title} by {matched_artist} - Found but queue failed")
                    else:
                        results.append(f"🔍 {matched_title} by {matched_artist} - Not in RadioDJ library")
                else:
                    # Try Jamendo
                    jamendo_results = matching_orchestrator.jamendo.search_song(title, artist)
                    if jamendo_results:
                        best = jamendo_results[0]
                        results.append(f"🎵 Found on Jamendo: {best.get('title')} by {best.get('artist')}")
                    else:
                        results.append(f"❌ No match for: {title} by {artist or 'unknown'}")
            
            reply = "🎵 Results:\n\n" + "\n".join(results)
            rr = requests.post(f'{base}/sendMessage', json={'chat_id': chat_id, 'text': reply})
            print(f'  Reply sent: {rr.status_code}')
    else:
        print('.', end='', flush=True)
    time.sleep(1)
print('\nDone')
