"""Telegram bot that polls for messages and matches songs."""
import os
import sys
import requests
import time
import logging
import uuid
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=True)

from src.text_processing.message_parser import message_parser
from src.music_matching.musicbrainz_client import musicbrainz_client
from src.music_matching.fuzzy_matcher import fuzzy_matcher
from src.playlist_parser import playlist_parser
from src.radiodj_integration.radiodj_client import radiodj_client
from src.radiodj_integration.sync_service import sync_service

# Database imports
from config.database import SessionLocal
from src.database.operations import ChatOperations, MessageOperations, SongOperations, RequestOperations
from src.database.models import SongRequest

# RadioDJ integration
from src.integrations.radiodj_handler import check_radiodj_library

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def save_to_database(db, chat_id, username, raw_text, results):
    """Save song matches and return created request/result pairs."""
    try:
        # Create or update chat record
        ChatOperations.create_or_update_chat(db, str(chat_id), f"Telegram: {chat_id}")
        
        # Create message record
        message_id = f"tg_{chat_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        message = MessageOperations.create_message(
            db,
            message_id=message_id,
            chat_id=str(chat_id),
            sender_number=username,
            sender_name=username,
            raw_text=raw_text,
            timestamp=datetime.now(timezone.utc)
        )
        
        created_requests = []

        # Save each match
        for result in results:
            # Create extraction record
            extraction = SongOperations.create_extraction(
                db,
                message_id=message.id,
                original_phrase=raw_text,
                confidence_score=result.get('confidence', 0),
                extraction_method="telegram_bot"
            )
            
            # Create match record
            match = SongOperations.create_match(
                db,
                extraction_id=extraction.id,
                song_title=result.get('title', ''),
                artist_name=result.get('artist'),
                musicbrainz_id=result.get('musicbrainz_id'),
                match_confidence=result.get('confidence', 0),
                match_source="musicbrainz",
                match_metadata={'raw_result': result}
            )
            
            # Create song request
            request = RequestOperations.create_request(
                db,
                chat_id=str(chat_id),
                matched_song_id=match.id,
                requested_by=username
            )
            created_requests.append({"result": result, "request": request})
        
        logger.info(f"💾 Saved {len(results)} match(es) to database")
        return created_requests
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []


def get_updates(offset=None):
    """Get new messages from Telegram."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    try:
        response = requests.get(url, params=params, timeout=35)
        return response.json()
    except Exception as e:
        logger.error(f"Error getting updates: {e}")
        return {"result": []}


def send_message(chat_id, text, parse_mode="HTML"):
    """Send a message to a Telegram chat."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={
            "chat_id": chat_id, 
            "text": text,
            "parse_mode": parse_mode
        })
        try:
            data = response.json()
        except Exception:
            data = {'error': 'invalid json', 'text': text}
        logger.info(f"Telegram sendMessage response: %s", data)
        return data
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return None


def process_song_request(text):
    """Parse message and match songs."""
    # Extract song candidates from message
    candidates = message_parser.parse(text)
    
    if not candidates:
        return None
    
    results = []
    for candidate in candidates:
        title = candidate.get('title')
        artist = candidate.get('artist')
        
        # Search MusicBrainz
        mb_results = musicbrainz_client.search_song(title, artist)
        
        if mb_results:
            # Get best match
            best_match, confidence = fuzzy_matcher.get_best_match(title, artist, mb_results)
            
            if best_match and confidence >= 75:
                artist_name = "Unknown"
                if best_match.get('artist_credits'):
                    artist_name = best_match['artist_credits'][0].get('name', 'Unknown')
                
                results.append({
                    'title': best_match.get('title'),
                    'artist': artist_name,
                    'confidence': confidence,
                    'musicbrainz_id': best_match.get('musicbrainz_id')
                })
        
        # Rate limit for MusicBrainz
        time.sleep(1)
    
    return results


def process_playlist(text, chat_id):
    """Check if message contains a playlist link and process it."""
    playlist_info = playlist_parser.detect_playlist_url(text)
    
    if not playlist_info:
        return None
    
    platform = playlist_info['platform']
    playlist_id = playlist_info['playlist_id']
    
    logger.info(f"🎧 Detected {platform} playlist: {playlist_id}")
    
    # Send "processing" message
    send_message(chat_id, f"🎧 <b>Scanning {platform.replace('_', ' ').title()} playlist...</b>\n\nThis may take a moment.", "HTML")
    
    # Get tracks from playlist
    tracks = playlist_parser.get_playlist_tracks(platform, playlist_id)
    
    if not tracks:
        return {
            'error': True,
            'message': f"❌ Couldn't fetch playlist. Make sure:\n• The playlist is public\n• Spotify credentials are set in .env\n\nSupported: Spotify playlists & albums"
        }
    
    logger.info(f"📋 Found {len(tracks)} tracks in playlist")
    
    # Match each track via MusicBrainz
    matches = []
    for i, track in enumerate(tracks[:50]):  # Limit to 50 tracks
        title = track.get('title')
        artist = track.get('artist')
        
        if not title:
            continue
        
        # Search MusicBrainz
        mb_results = musicbrainz_client.search_song(title, artist)
        
        if mb_results:
            best_match, confidence = fuzzy_matcher.get_best_match(title, artist, mb_results)
            
            if best_match and confidence >= 70:
                artist_name = "Unknown"
                if best_match.get('artist_credits'):
                    artist_name = best_match['artist_credits'][0].get('name', 'Unknown')
                
                matches.append({
                    'original_title': title,
                    'original_artist': artist,
                    'matched_title': best_match.get('title'),
                    'matched_artist': artist_name,
                    'confidence': confidence,
                    'musicbrainz_id': best_match.get('musicbrainz_id')
                })
            else:
                matches.append({
                    'original_title': title,
                    'original_artist': artist,
                    'matched_title': None,
                    'matched_artist': None,
                    'confidence': 0,
                    'musicbrainz_id': None
                })
        else:
            matches.append({
                'original_title': title,
                'original_artist': artist,
                'matched_title': None,
                'matched_artist': None,
                'confidence': 0,
                'musicbrainz_id': None
            })
        
        # Rate limit for MusicBrainz (1 request per second)
        time.sleep(1.1)
        
        # Send progress update every 10 tracks
        if (i + 1) % 10 == 0:
            logger.info(f"  Progress: {i + 1}/{min(len(tracks), 50)} tracks processed")
    
    return {
        'error': False,
        'total_tracks': len(tracks),
        'processed_tracks': len(matches),
        'matches': matches
    }


def format_playlist_response(result):
    """Format playlist matches as a nice message."""
    if result.get('error'):
        return result.get('message')
    
    matches = result.get('matches', [])
    matched = [m for m in matches if m.get('matched_title')]
    unmatched = [m for m in matches if not m.get('matched_title')]
    
    response = f"🎧 <b>Playlist Scan Complete!</b>\n\n"
    response += f"📊 <b>Results:</b>\n"
    response += f"• Total tracks: {result.get('total_tracks', 0)}\n"
    response += f"• Processed: {result.get('processed_tracks', 0)}\n"
    response += f"• ✅ Matched: {len(matched)}\n"
    response += f"• ❌ Not found: {len(unmatched)}\n\n"
    
    if matched:
        response += f"<b>✅ Matched Songs ({len(matched)}):</b>\n"
        for i, m in enumerate(matched[:20], 1):  # Show first 20
            response += f"{i}. <b>{m['matched_title']}</b> - {m['matched_artist']} ({m['confidence']:.0f}%)\n"
        
        if len(matched) > 20:
            response += f"<i>...and {len(matched) - 20} more</i>\n"
    
    if unmatched:
        response += f"\n<b>❌ Not Found ({len(unmatched)}):</b>\n"
        for i, m in enumerate(unmatched[:10], 1):  # Show first 10
            response += f"• {m['original_title']} - {m['original_artist'] or 'Unknown'}\n"
        
        if len(unmatched) > 10:
            response += f"<i>...and {len(unmatched) - 10} more</i>\n"
    
    return response


def format_response(results, radiodj_queued=None, radiodj_found_not_queued=None, radiodj_queue_details=None):
    """Format song matches as a nice message."""
    if not results:
        return None
    
    response = "🎵 <b>Song Match Found!</b>\n\n"
    
    for i, match in enumerate(results, 1):
        response += f"<b>{match['title']}</b>\n"
        response += f"👤 Artist: {match['artist']}\n"
        response += f"✅ Confidence: {match['confidence']:.0f}%\n"
        if match.get('musicbrainz_id'):
            response += f"🔗 <a href='https://musicbrainz.org/recording/{match['musicbrainz_id']}'>MusicBrainz</a>\n"
        
        # Check if queued to RadioDJ
        if radiodj_queued and match in radiodj_queued:
            response += f"📻 <b>Queued to RadioDJ!</b>\n"
            queued_track = (radiodj_queue_details or {}).get(id(match))
            if queued_track and (
                queued_track.get('title') != match.get('title')
                or queued_track.get('artist') != match.get('artist')
            ):
                response += (
                    f"📀 RadioDJ track: {queued_track.get('artist', 'Unknown')}"
                    f" - {queued_track.get('title', 'Unknown')}\n"
                )
        elif radiodj_found_not_queued and match in radiodj_found_not_queued:
            response += f"📚 Found in RadioDJ library (queue unavailable)\n"
        elif radiodj_queued is not None:
            response += f"⚠️ Not found in RadioDJ library\n"
        
        response += "\n"
    
    return response


def main():
    """Poll Telegram for messages and match songs."""
    logger.info("🤖 Telegram bot started!")
    logger.info("Listening for song requests in your group...")
    logger.info("Send messages like:")
    logger.info("  - 'Play Bohemian Rhapsody by Queen'")
    logger.info("  - 'I want to hear Blinding Lights by The Weeknd'")
    logger.info("  - 'Can you play Bad Guy by Billie Eilish'")
    logger.info("  - Or paste a Spotify playlist/album link!")
    logger.info("-" * 50)
    
    offset = None
    while True:
        updates = get_updates(offset)
        for update in updates.get("result", []):
            offset = update["update_id"] + 1
            
            if "message" in update:
                text = update["message"].get("text", "")
                chat = update["message"].get("chat", {})
                chat_id = chat.get("id")
                user = update["message"].get("from", {})
                username = user.get("first_name", "Unknown")
                
                if not text:
                    continue
                
                logger.info(f"📩 Message from {username}: {text}")
                
                # Check for playlist links first
                playlist_info = playlist_parser.detect_playlist_url(text)
                if playlist_info:
                    logger.info(f"🎧 Processing {playlist_info['platform']} playlist...")
                    result = process_playlist(text, chat_id)
                    if result:
                        response = format_playlist_response(result)
                        send_message(chat_id, response)
                        matched_count = len([m for m in result.get('matches', []) if m.get('matched_title')])
                        logger.info(f"✅ Playlist processed: {matched_count} matches")
                    continue
                
                # Process the message for song requests
                results = process_song_request(text)
                
                if results:
                    db = SessionLocal()
                    try:
                        persisted = save_to_database(db, chat_id, username, text, results)

                        radiodj_queued = []
                        radiodj_found_not_queued = []
                        radiodj_queue_details = {}
                        for item in persisted:
                            result = item['result']
                            request = item['request']

                            RequestOperations.approve_request(db, request.id)
                            request = db.query(SongRequest).filter(SongRequest.id == request.id).first()

                            if request and sync_service.process_request(db, request):
                                radiodj_queued.append(result)
                                db.refresh(request)
                                if request.radiodj_track_id:
                                    queued_track = radiodj_client.get_track_by_id(request.radiodj_track_id)
                                    if queued_track:
                                        radiodj_queue_details[id(result)] = {
                                            'title': queued_track.title,
                                            'artist': queued_track.artist,
                                        }
                            elif check_radiodj_library(
                                result.get('title', ''),
                                result.get('artist', ''),
                            ):
                                radiodj_found_not_queued.append(result)
                    finally:
                        db.close()
                    
                    # Send reply with matches and RadioDJ status
                    response = format_response(
                        results,
                        radiodj_queued,
                        radiodj_found_not_queued,
                        radiodj_queue_details,
                    )
                    send_message(chat_id, response)
                    logger.info(
                        "✅ Replied with %s match(es), %s queued, %s found but not queued",
                        len(results),
                        len(radiodj_queued),
                        len(radiodj_found_not_queued),
                    )
                else:
                    # No song match found - acknowledge the message
                    send_message(chat_id, "👋 Hey! I'm listening.\n\nTo request a song, say:\n• <i>Play [Song] by [Artist]</i>\n• Or paste a Spotify playlist link!")
                    logger.info(f"💬 Acknowledged message: {text[:50]}")
        
        time.sleep(1)


if __name__ == "__main__":
    main()
