import os
from dotenv import load_dotenv
from datetime import date
import psycopg
from psycopg_pool import ConnectionPool

load_dotenv()
DB_URL = os.getenv('DB_URL')

pool = ConnectionPool(DB_URL)
    
def get_songs():
    try:
        with pool.connection() as connection:
            with connection.cursor() as cur:
                cur.execute('SELECT * FROM "Songs";')
                rows = cur.fetchall()
                return rows
    except Exception as e:
        print(f"Error fetching songs: {e}")
        return []

def play(title, artist, album, duration):
    with pool.connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    WITH s AS (
                        INSERT INTO "Songs" (title, artist, album, duration_seconds)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT ON CONSTRAINT songs_identity_unique
                        DO UPDATE SET title = EXCLUDED.title   -- no-op update, just to RETURNING
                        RETURNING id
                    )
                    INSERT INTO "PlayHistory" (song_id)
                    SELECT id FROM s
                    ON CONFLICT (song_id, "Date")
                    DO UPDATE SET "PlayCount" = "PlayHistory"."PlayCount" + 1;""", (title, artist, album, duration))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error in play(): {e}")
            return None
                
def get_play_history(history_date=None):
    if history_date is None:
        history_date = date.today().isoformat()

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT s.title, s.artist, s.duration_seconds, ph."PlayCount"
                    FROM "PlayHistory" ph
                    JOIN "Songs" s ON s.id = ph.song_id
                    WHERE ph."Date" = %s
                    ORDER BY ph."PlayCount" DESC;
                """, (history_date,))

                rows = cur.fetchall()

                # format as dictionaries for easy use
                return [
                    {
                        "title": r[0],
                        "artist": r[1],
                        "duration_seconds": r[2],
                        "playCount": r[3]
                    }
                    for r in rows
                ]
    except Exception as e:
        print(f"Error fetching play history: {e}")
        return []