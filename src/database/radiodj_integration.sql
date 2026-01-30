-- RadioDJ Integration Tables for WhatsApp Song Scanner
-- Run this after the main schema is loaded

USE song_scanner;

-- Track which songs have been played in RadioDJ
CREATE TABLE IF NOT EXISTS radiodj_played_songs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    request_id INT NOT NULL,
    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    radiodj_track_id INT,
    FOREIGN KEY (request_id) REFERENCES matched_songs(id) ON DELETE CASCADE,
    INDEX idx_request_id (request_id),
    INDEX idx_played_at (played_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Map MusicBrainz IDs to RadioDJ track IDs
CREATE TABLE IF NOT EXISTS radiodj_track_mapping (
    id INT AUTO_INCREMENT PRIMARY KEY,
    musicbrainz_id VARCHAR(36) NOT NULL,
    radiodj_track_id INT NOT NULL,
    title VARCHAR(255),
    artist VARCHAR(255),
    file_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_mb_id (musicbrainz_id),
    INDEX idx_rdj_id (radiodj_track_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- View for RadioDJ to read pending song requests
CREATE OR REPLACE VIEW radiodj_pending_requests AS
SELECT 
    ms.id AS request_id,
    ms.song_title,
    ms.artist_name,
    ms.album_name,
    ms.musicbrainz_id,
    ms.match_confidence,
    sr.requested_by,
    sr.created_at AS request_time,
    sr.status,
    tm.radiodj_track_id,
    tm.file_path
FROM matched_songs ms
JOIN song_requests sr ON sr.matched_song_id = ms.id
LEFT JOIN radiodj_track_mapping tm ON tm.musicbrainz_id = ms.musicbrainz_id
WHERE sr.status = 'pending'
ORDER BY sr.created_at ASC;

-- View for songs that have been queued but not played
CREATE OR REPLACE VIEW radiodj_queued_songs AS
SELECT 
    ms.id AS request_id,
    ms.song_title,
    ms.artist_name,
    sr.requested_by,
    sr.created_at AS queued_at
FROM matched_songs ms
JOIN song_requests sr ON sr.matched_song_id = ms.id
WHERE sr.status = 'queued'
ORDER BY sr.created_at ASC;
