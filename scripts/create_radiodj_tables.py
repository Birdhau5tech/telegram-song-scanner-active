"""Script to create RadioDJ integration tables."""
from config.database import engine
from sqlalchemy import text

sql1 = """
CREATE TABLE IF NOT EXISTS radiodj_played_songs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    request_id INT NOT NULL,
    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    radiodj_track_id INT,
    INDEX idx_request_id (request_id),
    INDEX idx_played_at (played_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

sql2 = """
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

with engine.connect() as conn:
    conn.execute(text(sql1))
    conn.execute(text(sql2))
    conn.commit()
    print("Tables created successfully!")
    
    result = conn.execute(text("SHOW TABLES"))
    print("\nTables in database:")
    for row in result:
        print(f"  - {row[0]}")
