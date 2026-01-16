"""Playlist parser to extract songs from streaming service playlists."""
import re
import requests
import base64
import os
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")


class PlaylistParser:
    """Parse playlists from various streaming services."""

    def __init__(self):
        self.spotify_token = None
        self.spotify_token_expiry = 0

    def detect_playlist_url(self, text: str) -> Optional[Dict]:
        """Detect if text contains a playlist URL.
        
        Returns dict with 'platform' and 'playlist_id' if found.
        """
        # Spotify playlist
        spotify_pattern = r'(?:https?://)?(?:open\.)?spotify\.com/playlist/([a-zA-Z0-9]+)'
        match = re.search(spotify_pattern, text)
        if match:
            return {'platform': 'spotify', 'playlist_id': match.group(1), 'url': match.group(0)}
        
        # Spotify album
        spotify_album_pattern = r'(?:https?://)?(?:open\.)?spotify\.com/album/([a-zA-Z0-9]+)'
        match = re.search(spotify_album_pattern, text)
        if match:
            return {'platform': 'spotify_album', 'playlist_id': match.group(1), 'url': match.group(0)}
        
        # YouTube Music playlist
        ytm_pattern = r'(?:https?://)?music\.youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)'
        match = re.search(ytm_pattern, text)
        if match:
            return {'platform': 'youtube_music', 'playlist_id': match.group(1), 'url': match.group(0)}
        
        # YouTube playlist
        yt_pattern = r'(?:https?://)?(?:www\.)?youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)'
        match = re.search(yt_pattern, text)
        if match:
            return {'platform': 'youtube', 'playlist_id': match.group(1), 'url': match.group(0)}
        
        # Apple Music playlist
        apple_pattern = r'(?:https?://)?music\.apple\.com/\w+/playlist/[^/]+/pl\.([a-zA-Z0-9-]+)'
        match = re.search(apple_pattern, text)
        if match:
            return {'platform': 'apple_music', 'playlist_id': match.group(1), 'url': match.group(0)}
        
        # SoundCloud playlist
        soundcloud_pattern = r'(?:https?://)?soundcloud\.com/([^/]+)/sets/([^/\s?]+)'
        match = re.search(soundcloud_pattern, text)
        if match:
            return {'platform': 'soundcloud', 'playlist_id': f"{match.group(1)}/{match.group(2)}", 'url': match.group(0)}
        
        return None

    def _get_spotify_token(self) -> Optional[str]:
        """Get Spotify access token using client credentials."""
        if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
            return None
        
        import time
        if self.spotify_token and time.time() < self.spotify_token_expiry:
            return self.spotify_token
        
        try:
            auth_str = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
            auth_b64 = base64.b64encode(auth_str.encode()).decode()
            
            response = requests.post(
                "https://accounts.spotify.com/api/token",
                headers={"Authorization": f"Basic {auth_b64}"},
                data={"grant_type": "client_credentials"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.spotify_token = data["access_token"]
                self.spotify_token_expiry = time.time() + data["expires_in"] - 60
                return self.spotify_token
        except Exception as e:
            print(f"Spotify auth error: {e}")
        
        return None

    def get_spotify_playlist(self, playlist_id: str) -> List[Dict]:
        """Fetch tracks from a Spotify playlist."""
        token = self._get_spotify_token()
        if not token:
            return []
        
        tracks = []
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        
        try:
            while url:
                response = requests.get(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10
                )
                
                if response.status_code != 200:
                    break
                
                data = response.json()
                
                for item in data.get("items", []):
                    track = item.get("track")
                    if track and track.get("name"):
                        artists = [a["name"] for a in track.get("artists", [])]
                        tracks.append({
                            "title": track["name"],
                            "artist": artists[0] if artists else None,
                            "all_artists": artists,
                            "album": track.get("album", {}).get("name"),
                            "duration_ms": track.get("duration_ms"),
                            "spotify_id": track.get("id")
                        })
                
                url = data.get("next")
                
                # Limit to first 100 tracks
                if len(tracks) >= 100:
                    break
                    
        except Exception as e:
            print(f"Spotify playlist error: {e}")
        
        return tracks

    def get_spotify_album(self, album_id: str) -> List[Dict]:
        """Fetch tracks from a Spotify album."""
        token = self._get_spotify_token()
        if not token:
            return []
        
        tracks = []
        
        try:
            response = requests.get(
                f"https://api.spotify.com/v1/albums/{album_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                album_name = data.get("name")
                album_artists = [a["name"] for a in data.get("artists", [])]
                
                for track in data.get("tracks", {}).get("items", []):
                    artists = [a["name"] for a in track.get("artists", [])]
                    tracks.append({
                        "title": track["name"],
                        "artist": artists[0] if artists else album_artists[0] if album_artists else None,
                        "all_artists": artists or album_artists,
                        "album": album_name,
                        "duration_ms": track.get("duration_ms"),
                        "spotify_id": track.get("id")
                    })
                    
        except Exception as e:
            print(f"Spotify album error: {e}")
        
        return tracks

    def get_playlist_tracks(self, platform: str, playlist_id: str) -> List[Dict]:
        """Get tracks from a playlist based on platform."""
        if platform == "spotify":
            return self.get_spotify_playlist(playlist_id)
        elif platform == "spotify_album":
            return self.get_spotify_album(playlist_id)
        elif platform in ["youtube", "youtube_music"]:
            # YouTube requires API key or scraping
            return []
        elif platform == "apple_music":
            # Apple Music requires developer token
            return []
        elif platform == "soundcloud":
            # SoundCloud requires API
            return []
        
        return []


# Singleton instance
playlist_parser = PlaylistParser()
