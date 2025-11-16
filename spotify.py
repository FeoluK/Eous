import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Configuration
SPOTIPY_CLIENT_ID = ''
SPOTIPY_CLIENT_SECRET = ''
# SPOTIPY_REDIRECT_URI = 'https://vikramanantha.github.io'
SPOTIPY_REDIRECT_URI = 'http://127.0.0.1:8888/callback'

# Scopes needed for playback control
SCOPE = 'user-modify-playback-state user-read-playback-state'

def play_song(song_name, artist_name=None):
    """
    Search for and play a song on Spotify
    
    Args:
        song_name: Name of the song to play
        artist_name: Optional artist name to refine search
    """
    # Authenticate
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SCOPE
    ))
    
    # Build search query
    query = f"track:{song_name}"
    if artist_name:
        query += f" artist:{artist_name}"
    
    # Search for the song
    results = sp.search(q=query, type='track', limit=5)
    
    if not results['tracks']['items']:
        print(f"No results found for '{song_name}'")
        return
    
    # Display search results
    print("\nSearch results:")
    for idx, track in enumerate(results['tracks']['items'], 1):
        artists = ", ".join([artist['name'] for artist in track['artists']])
        print(f"{idx}. {track['name']} by {artists}")
    
    # Use the first result
    track_uri = results['tracks']['items'][0]['uri']
    track_name = results['tracks']['items'][0]['name']
    track_artists = ", ".join([artist['name'] for artist in results['tracks']['items'][0]['artists']])
    
    # Get available devices
    devices = sp.devices()
    
    if not devices['devices']:
        print("\nNo active Spotify devices found. Please open Spotify on a device first.")
        return
    
    # Play the song
    try:
        sp.start_playback(uris=[track_uri])
        print(f"\nNow playing: {track_name} by {track_artists}")
    except Exception as e:
        print(f"\nError playing song: {e}")
        print("Make sure Spotify is open and active on at least one device.")

if __name__ == "__main__":
    print("=== Spotify Song Player ===\n")
    
    # Example usage
    song = input("Enter song name: ")
    artist = input("Enter artist name (optional, press Enter to skip): ").strip()
    
    if artist:
        play_song(song, artist)
    else:
        play_song(song)