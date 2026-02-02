# Full pipeline polling - Telegram -> Match -> RadioDJ
import requests
import os
import sys
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

# Set DB credentials
os.environ.setdefault('MARIADB_HOST', '127.0.0.1')
os.environ.setdefault('MARIADB_DATABASE', 'radiodj2')
os.environ.setdefault('MARIADB_USERNAME', 'root')
os.environ.setdefault('MARIADB_PASSWORD', 'finner25')

token = os.getenv('TELEGRAM_BOT_TOKEN')
base = f'https://api.telegram.org/bot{token}'

# Initialize components
from src.text_processing.text_cleaner import text_cleaner
from src.text_processing.message_parser import message_parser
from src.music_matching.matching_orchestrator import matching_orchestrator
from src.radiodj_integration.radiodj_client import radiodj_client

print(f'RadioDJ: {radiodj_client.validate_connection()}')

# Delete webhook
requests.post(f'{base}/deleteWebhook')
print('Ready! Send message to @Birdhau5bot')

offset = 0
import time
while True:
    try:
        r = requests.get(f'{base}/getUpdates', params={'offset': offset, 'timeout': 30}, timeout=35)
        data = r.json()
        for u in data.get('result', []):
            offset = u['update_id'] + 1
            msg = u.get('message', {})
            txt = msg.get('text', '')
            chat_id = msg.get('chat', {}).get('id')
            sender = msg.get('from', {}).get('username', 'unknown')
            print(f'Got: {txt} from {sender}')
            
            # Step 1: Clean and parse
            cleaned = text_cleaner.clean(txt)
            candidates = message_parser.parse(cleaned) if cleaned else []
            
            if not candidates:
                requests.post(f'{base}/sendMessage', json={'chat_id': chat_id, 'text': f'No song found in: {txt}\nTry: Artist - Title'})
                continue
            
            results = []
            for c in candidates:
                title = c.get('title', '')
                artist = c.get('artist', '')
                print(f'  Searching: {title} by {artist}')
                
                # Step 2: Search MusicBrainz
                mb = matching_orchestrator.musicbrainz.search_song(title, artist)
                if mb:
                    best = mb[0]
                    m_title = best.get('title', title)
                    m_artist = best['artist_credits'][0].get('name', '') if best.get('artist_credits') else ''
                    print(f'  Found: {m_title} by {m_artist}')
                    
                    # Step 3: Search RadioDJ library
                    track_id = radiodj_client.find_track_in_library(m_artist, m_title)
                    if track_id:
                        # Step 4: Add to queue
                        ok = radiodj_client.add_track_to_queue_db(track_id)
                        if ok:
                            results.append(f'[OK] {m_title} by {m_artist} - ADDED TO RADIODJ!')
                        else:
                            results.append(f'[!] {m_title} by {m_artist} - Queue failed')
                    else:
                        results.append(f'[?] {m_title} by {m_artist} - Not in RadioDJ library')
                else:
                    # Try Jamendo
                    jm = matching_orchestrator.jamendo.search_song(title, artist)
                    if jm:
                        best = jm[0]
                        results.append(f'[Jamendo] {best.get("title")} by {best.get("artist")}')
                    else:
                        results.append(f'[X] No match: {title} by {artist or "unknown"}')
            
            reply = 'Song Results:\n\n' + '\n'.join(results)
            requests.post(f'{base}/sendMessage', json={'chat_id': chat_id, 'text': reply})
            print('Reply sent!')
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()
        time.sleep(2)
