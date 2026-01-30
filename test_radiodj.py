"""Test RadioDJ integration with direct connection."""
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

# Direct connection test
print("=== RadioDJ Direct Connection Test ===")

try:
    conn = pymysql.connect(
        host='127.0.0.1',
        port=3306,
        user='root',
        password='finner25',
        database='radiodj2',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    
    with conn.cursor() as cursor:
        # Count tracks
        cursor.execute("SELECT COUNT(*) as total FROM songs")
        total = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as enabled FROM songs WHERE enabled = 1")
        enabled = cursor.fetchone()['enabled']
        
        print(f"Total tracks in library: {total}")
        print(f"Enabled tracks: {enabled}")
        
        # Show sample tracks
        cursor.execute("SELECT ID, artist, title FROM songs LIMIT 5")
        tracks = cursor.fetchall()
        if tracks:
            print("\nSample tracks:")
            for t in tracks:
                print(f"  - {t['artist']} - {t['title']}")
        else:
            print("\nNo tracks imported yet. Add music to RadioDJ!")
        
        # Check queue
        cursor.execute("SELECT COUNT(*) as queue_count FROM queuelist")
        queue_count = cursor.fetchone()['queue_count']
        print(f"\nTracks in queue: {queue_count}")
    
    conn.close()
    print("\n✅ RadioDJ database connection successful!")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
