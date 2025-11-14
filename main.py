import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import discord
from discord.ui import Button, View
import asyncio
from DB_Connect import play, get_play_history
from datetime import date
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta


load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')

TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = os.getenv('SERVER_ID') 

SCOPE = 'user-top-read user-read-recently-played user-read-currently-playing user-read-playback-state'

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)

global current_playback, current_progress, current_duration

class DisconnectButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Disconnect Bot", style=discord.ButtonStyle.red)
    async def disconnect_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != int(os.getenv('MY_DISCORD_ID')):
            await interaction.response.send_message("You are not allowed to disconnect the bot.", ephemeral=True)
            return
        
        await interaction.response.send_message("Disconnecting the bot...", ephemeral=True)
        await client.close()

async def daily_review():
    day_passed = (date.today() - timedelta(days=1)).isoformat()
    sorted_songs = get_play_history(day_passed)
    
    if not sorted_songs:
        print(f"No play history found for {day_passed}.")
        return
    
    daily_review_message = f"**Daily Review!**\n"
    count = 1
    for song in sorted_songs:    
        daily_review_message += f"{count}. **{song['title']}** by {song['artist']} - Played {song['playCount']} times\n"
        count += 1
    
    channel = await client.fetch_channel(CHANNEL_ID)
    
    if channel:
        if len(daily_review_message) > 2000:
            chunks = split_message(daily_review_message)
            for chunk in chunks:
                await channel.send(chunk)
        else:
            await channel.send(daily_review_message)
    else:
        print(f"Channel with ID {CHANNEL_ID} not found.")

async def sort_by_play_count(message, songs, artist=False):
    try:
        limit = None
        if message:
            parts = message.content.split()
            limit = None
            if len(parts) > 1 and parts[1].isdigit():
                limit = int(parts[1])

        if not songs:
            await message.channel.send("No song data available.")
            return
        
        if artist:
            artists = []
            for song in songs:
                artist = song["artist"]
                playcount = song["playCount"]
                
                existing_artist = next((a for a in artists if a["artist"].lower() == artist.lower()), None)
                if existing_artist:
                    existing_artist["playCount"] += playcount
                else:
                    artists.append({"artist": artist, "playCount": playcount})
                
            songs = artists        
                
        sorted_songs = sorted(songs, key=lambda s: s["playCount"], reverse=True)

        if limit:
            sorted_songs = sorted_songs[:limit]
        
        return sorted_songs
    except (FileNotFoundError):
        print("Error reading from database")
        return


def split_message(message, max_length=2000):
    """Splits a message into chunks of a maximum length."""
    leftover = ""
    chunks = []
    for i in range(0, len(message), max_length):
        chunk = leftover + message[i:i + (max_length - len(leftover))]
        
        last_times = chunk.rfind("times")
        if last_times != -1:
            last_times += len("times")
            leftover = chunk[last_times:]
            chunk = chunk[:last_times]
        else:
            leftover = ""
            
        if chunk:
            chunks.append(chunk)
    return chunks

def song_exists(data, title, artist):
    for song in data:
        if (song["title"].lower() == title.lower() and song["artist"].lower() == artist.lower()):
            song["playCount"] += 1
            return True
    return False
        
async def spotify_loop():
    global current_playback, current_progress, current_duration
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SCOPE
    ))
    channel = await client.fetch_channel(CHANNEL_ID)
    user = sp.current_user()
    print(f"Logged in as: {user['display_name']}")
    
    mogu_mogu_id = os.getenv('MOGUMOGU')
    track_id = ""
    mogu_mogu_counter = 1
    listening_to_mogu_mogu = False
    threshold = 15000

    while not client.is_closed():
        if channel:
            current = sp.current_playback()
            if current and current['is_playing']:
                track = current['item']
                
                current_playback = f"{track['name']} by {track['artists'][0]['name']}"
                current_progress = current['progress_ms']
                current_duration = track['duration_ms']
                
                if current['progress_ms'] > threshold:
                    if track['id'] != track_id:
                        title = track['name']
                        artist = track['artists'][0]['name']
                        album = track['album']['name']
                        duration = track['duration_ms'] // 1000
                        track_id = track['id']
                        
                        play(title, artist, album, duration)
                    if track['id'] == mogu_mogu_id and not listening_to_mogu_mogu:
                        try:
                            await channel.send(f"Hpmanen is listening to Mogu Mogu!\nMogu Mogu Counter: {mogu_mogu_counter}")
                            mogu_mogu_counter += 1        
                        except Exception:
                            print("Could not perform action.")
                        listening_to_mogu_mogu = True
                    elif track['id'] != mogu_mogu_id:  
                        listening_to_mogu_mogu = False
            else:
                current_playback = "Nothing is currently playing."
                current_progress = 0
                current_duration = 0
                track_id = ""
                listening_to_mogu_mogu = False
        else:
            print(f"Channel with ID {CHANNEL_ID} not found.")

        await asyncio.sleep(10)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    client.loop.create_task(spotify_loop())
            
@client.event
async def on_message(message):
    global current_playback, current_progress, current_duration
    if message.author == client.user:
        return
    
    if message.content == "!disconnect":
        view = DisconnectButtonView()
        await message.channel.send("Click the button to disconnect the bot:", view=view)
    
    if message.content.startswith("!stats"):
        try:
            sorted_songs = get_play_history()
            total_seconds = sum(song['duration_seconds']*song['playCount'] for song in sorted_songs)
            stats_message = "Top Songs:\n"
            count = 1
            for song in sorted_songs:
                song_time_seconds = song['duration_seconds'] * song['playCount']
                song_time_minutes = song_time_seconds // 60
                song_time_hours = song_time_minutes // 60
                
                stats_message += f"{count}. {song['title']} by {song['artist']} - Played {song['playCount']} times for a total of {(song_time_hours):02}:{(song_time_minutes%60):02}:{(song_time_seconds%60):02}\n"
                count += 1
                
            if len(stats_message) > 2000:
                chunks = split_message(stats_message)
                        
                for chunk in chunks:
                    await message.channel.send(chunk)
            else:
                await message.channel.send(stats_message)
                
            await message.channel.send(f"Total Time Listened: {total_seconds // 3600} hours, {(total_seconds % 3600) // 60} minutes, {total_seconds % 60} seconds")

        except (FileNotFoundError):
            await message.channel.send("Error reading from database.")
        
    if message.content == "!current":
        system_message = ""
        if current_duration != 0:
            current_progress = current_progress // 1000
            current_duration = current_duration // 1000
            system_message = f"Currently playing **{current_playback}** {((current_progress % 3600) // 60):02}:{(current_progress%60):02}/{((current_duration % 3600) // 60):02}:{(current_duration%60):02}"
        else:
            system_message = current_playback
            
        await message.channel.send(system_message)
    
    if message.content.startswith("!topartists"):
        data = get_play_history()
        sorted_artists = await sort_by_play_count(message, data, True)
        top_artists_message = "Top Artists:\n"
        count = 1
        for artist in sorted_artists:
            top_artists_message += f"{count}. {artist['artist']} - Played {artist['playCount']} times\n"    
            count += 1
        
        if len(top_artists_message) > 2000:
            chunks = split_message(top_artists_message)
            
            for chunk in chunks:
                await message.channel.send(chunk)
        else:
            await message.channel.send(top_artists_message)
    
    if message.content.startswith("!history"):
        message_parts = message.content.split()
        history_date = date.today().isoformat()
        if len(message_parts) > 1:
            history_date = message_parts[1]
            
        today_played_message = f"Play History from {history_date}:\n"
        sorted_songs = get_play_history(history_date)
        
        if sorted_songs:
            count = 1
            for song in sorted_songs:
                today_played_message += f"{count}. {song['title']} by {song['artist']} - Played {song['playCount']} times\n"
                count += 1
            
            if len(today_played_message) > 2000:
                chunks = split_message(today_played_message)
                
                for chunk in chunks:
                    await message.channel.send(chunk)
            else:
                await message.channel.send(today_played_message)
        else:
            await message.channel.send(f"No play history found for {history_date}.")
        
    
    if message.content == "!help":
        help_message = (
            "Available commands:\n"
            "`!current`: Show currently playing song and its progress.\n"
            "`!disconnect`: Disconnect the bot.\n"
            "`!history [date]`: Show play history for a specific date in YYYY-MM-DD format (default is today).\n"
            "`!stats`: Show all songs played.\n"
            "`!stats [number]`: Show top [number] most-played songs.\n"
            "`!topartists`: Show top artists ranked by total plays.\n"
            "`!topartists [number]`: Show top [number] most-played artists.\n"
            "`!help`: Show this help message."
        )
        await message.channel.send(help_message)

def main():
    print(f"Client ID: {SPOTIFY_CLIENT_ID}")
    print(f"Client Secret: {SPOTIFY_CLIENT_SECRET}")
    print(f"Redirect URI: {SPOTIFY_REDIRECT_URI}")
    

async def start_bot():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(daily_review, 'cron', hour=0, minute=0)
    scheduler.start()
    
    await client.start(TOKEN)

if __name__ == "__main__":
    main()
    asyncio.run(start_bot())