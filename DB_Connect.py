import os
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import date

load_dotenv()
DB_URL = os.getenv('DB_URL')
DB_KEY = os.getenv('DB_KEY')
supabase = None

def get_connection() -> Client | None:
    global supabase
    
    try:
        if not DB_URL or not DB_KEY:
            raise ValueError("Database URL and Key must be set in environment variables.")
        
        if supabase is None:
            supabase = create_client(DB_URL, DB_KEY)
        else:
            print("Using existing database connection.")
            
        return supabase
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return None
    
def get_songs():
    supabase = get_connection()
    if supabase is None:
        return []

    try:
        response = supabase.table('Songs').select('*').execute()
        return response.data
    except Exception as e:
        print(f"Error fetching songs: {e}")
        return []

def add_song(song_data):
    supabase = get_connection()
    if supabase is None:
        return None

    try:
        response = supabase.table('Songs').insert(song_data).execute()
        return response.data
    except Exception as e:
        print(f"Error adding song: {e}")
        return None

def increase_playcount(song_name, song_artist):
    supabase = get_connection()
    if supabase is None:
        return None

    try:
        song_playCount = supabase.table('Songs').select('playCount').eq('title', song_name).eq('artist', song_artist).execute().data[0]['playCount']
        today_playCount = supabase.table('PlayHistory').select('playCount').eq('title', song_name).eq('artist', song_artist).eq('Date', date.today().isoformat()).execute().data[0]['playCount']
        supabase.table('Songs').update({'playCount': song_playCount + 1}).eq('title', song_name).execute()
        supabase.table('PlayHistory').update({'playCount': today_playCount + 1}).eq('title', song_name).execute()
    except Exception as e:
        print(f"Error increasing playcount: {e}")
        return None

def save_play_history(song_name, song_artist):
    supabase = get_connection()
    if supabase is None:
        return None

    try:
        response = supabase.table('PlayHistory').insert({
            'title': song_name,
            'artist': song_artist,
            'Date': date.today().isoformat()
        }).execute()
        return response.data
    except Exception as e:
        print(f"Song already played today.")
        return None

def get_play_history(history_date = date.today().isoformat()):
    supabase = get_connection()
    if supabase is None:
        return []

    try:
        response = supabase.table('PlayHistory').select('*').eq('Date', history_date).execute()
        return response.data
    except Exception as e:
        print(f"Error fetching today's play history: {e}")
        return []