"""Quick test to reply to latest Telegram message with song match."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from dotenv import load_dotenv
load_dotenv()

from src.text_processing.message_parser import message_parser
from src.music_matching.musicbrainz_client import musicbrainz_client
from src.music_matching.fuzzy_matcher import fuzzy_matcher

token = os.getenv('TELEGRAM_BOT_TOKEN')

def send_reply(chat_id, text):
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    response = requests.post(url, json={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'})
    return response.json()

# Get latest message
url = f'https://api.telegram.org/bot{token}/getUpdates'
response = requests.get(url)
updates = response.json().get('result', [])

if updates:
    latest = updates[-1]
    if 'message' in latest:
        text = latest['message'].get('text', '')
        msg_chat_id = latest['message']['chat']['id']
        print(f'Latest message: {text}')
        print(f'Chat ID: {msg_chat_id}')
        
        # Parse for songs
        candidates = message_parser.parse(text)
        print(f'Parsed candidates: {len(candidates)} found')
        
        if candidates:
            c = candidates[0]
            title = c.get('title')
            artist = c.get('artist')
            print(f'Searching MusicBrainz for: {title} by {artist}')
            
            results = musicbrainz_client.search_song(title, artist)
            print(f'MusicBrainz results: {len(results) if results else 0}')
            
            if results:
                best, conf = fuzzy_matcher.get_best_match(title, artist, results)
                if best:
                    artist_name = 'Unknown'
                    if best.get('artist_credits'):
                        artist_name = best['artist_credits'][0].get('name', 'Unknown')
                    
                    reply = f"🎵 Song Match Found!\n\n{best.get('title')}\n👤 Artist: {artist_name}\n✅ Confidence: {conf:.0f}%"
                    print(f'Sending reply...')
                    result = send_reply(msg_chat_id, reply)
                    print(f'Reply result: {result.get("ok")}')
                else:
                    print('No confident match')
            else:
                print('No MusicBrainz results')
        else:
            print('No song request detected')
else:
    print('No messages found')
