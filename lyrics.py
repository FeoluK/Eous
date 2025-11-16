import requests
import re
import time

def search_lyrics(track_name, artist_name, album_name=None, duration=None):
    """
    Search for synced lyrics on LRCLIB
    
    Args:
        track_name: Name of the track
        artist_name: Name of the artist
        album_name: Optional album name for better matching
        duration: Optional song duration in seconds for better matching
    
    Returns:
        Dictionary with lyrics data or None
    """
    base_url = "https://lrclib.net/api/search"
    
    params = {
        'track_name': track_name,
        'artist_name': artist_name
    }
    
    if album_name:
        params['album_name'] = album_name
    
    try:
        response = requests.get(base_url, params=params)
        
        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            return None
        
        results = response.json()
        
        if not results:
            print("No results found")
            return None
        
        # If duration provided, find closest match
        if duration:
            results = sorted(results, key=lambda x: abs(x.get('duration', 0) - duration))
        
        # Return first result
        return results[0]
    
    except Exception as e:
        print(f"Error fetching lyrics: {e}")
        return None

def get_lyrics_by_id(track_id):
    """
    Get lyrics by LRCLIB track ID
    
    Args:
        track_id: LRCLIB track ID
    
    Returns:
        Dictionary with lyrics data
    """
    url = f"https://lrclib.net/api/get/{track_id}"
    
    try:
        response = requests.get(url)
        
        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            return None
        
        return response.json()
    
    except Exception as e:
        print(f"Error fetching lyrics: {e}")
        return None

def parse_lrc_timestamps(synced_lyrics):
    """
    Parse LRC format lyrics into a list of (timestamp, lyric) tuples
    
    Args:
        synced_lyrics: String containing LRC format lyrics
    
    Returns:
        List of tuples (seconds, lyric_text)
    """
    if not synced_lyrics:
        return []
    
    lines = []
    # Pattern: [MM:SS.xx]lyric text
    pattern = r'\[(\d+):(\d+\.\d+)\](.*)'
    
    for line in synced_lyrics.split('\n'):
        match = re.match(pattern, line)
        if match:
            minutes = int(match.group(1))
            seconds = float(match.group(2))
            text = match.group(3).strip()
            
            total_seconds = minutes * 60 + seconds
            lines.append((total_seconds, text))
    
    return lines

def display_lyrics_info(lyrics_data):
    """
    Display information about the lyrics
    
    Args:
        lyrics_data: Dictionary from LRCLIB API
    """
    print("\n" + "=" * 60)
    print(f"Track: {lyrics_data['trackName']}")
    print(f"Artist: {lyrics_data['artistName']}")
    if lyrics_data.get('albumName'):
        print(f"Album: {lyrics_data['albumName']}")
    print(f"Duration: {lyrics_data.get('duration', 'N/A')} seconds")
    print(f"Synced Lyrics: {'Yes' if lyrics_data.get('syncedLyrics') else 'No'}")
    print(f"Plain Lyrics: {'Yes' if lyrics_data.get('plainLyrics') else 'No'}")
    print("=" * 60)

def save_lrc_file(lyrics_data, filename=None):
    """
    Save synced lyrics to an LRC file
    
    Args:
        lyrics_data: Dictionary from LRCLIB API
        filename: Optional custom filename
    """
    if not lyrics_data.get('syncedLyrics'):
        print("No synced lyrics available to save")
        return
    
    if not filename:
        safe_title = re.sub(r'[^\w\s-]', '', lyrics_data['trackName'])
        safe_artist = re.sub(r'[^\w\s-]', '', lyrics_data['artistName'])
        filename = f"{safe_artist} - {safe_title}.lrc"
    
    with open(filename, 'w', encoding='utf-8') as f:
        # Write metadata
        f.write(f"[ar:{lyrics_data['artistName']}]\n")
        f.write(f"[ti:{lyrics_data['trackName']}]\n")
        if lyrics_data.get('albumName'):
            f.write(f"[al:{lyrics_data['albumName']}]\n")
        f.write(f"[length:{lyrics_data.get('duration', 0)}]\n")
        f.write("\n")
        f.write(lyrics_data['syncedLyrics'])
    
    print(f"\nLRC file saved to: {filename}")

def display_synced_lyrics_preview(synced_lyrics, num_lines=10):
    """
    Display a preview of synced lyrics with timestamps
    
    Args:
        synced_lyrics: String containing LRC format lyrics
        num_lines: Number of lines to display
    """
    lines = parse_lrc_timestamps(synced_lyrics)
    
    print("\nLyrics Preview (first {} lines):".format(min(num_lines, len(lines))))
    print("-" * 60)
    
    for timestamp, text in lines[:num_lines]:
        minutes = int(timestamp // 60)
        seconds = timestamp % 60
        print(f"[{minutes:02d}:{seconds:05.2f}] {text}")
    
    if len(lines) > num_lines:
        print(f"... ({len(lines) - num_lines} more lines)")

def simulate_karaoke(synced_lyrics, speed_multiplier=1.0):
    """
    Simulate karaoke-style display of lyrics (demonstration)
    
    Args:
        synced_lyrics: String containing LRC format lyrics
        speed_multiplier: Speed up or slow down playback (1.0 = normal)
    """
    lines = parse_lrc_timestamps(synced_lyrics)
    
    if not lines:
        print("No synced lyrics available")
        return
    
    print("\n" + "=" * 60)
    print("KARAOKE MODE (press Ctrl+C to stop)")
    print("=" * 60 + "\n")
    
    start_time = time.time()
    
    try:
        for i, (timestamp, text) in enumerate(lines):
            # Wait until the timestamp
            while (time.time() - start_time) < (timestamp / speed_multiplier):
                time.sleep(0.01)
            
            # Display the lyric
            print(f"\r{' ' * 80}\r{text}", end='', flush=True)
            
            # Add newline for last line
            if i == len(lines) - 1:
                print()
    
    except KeyboardInterrupt:
        print("\n\nKaraoke stopped")

if __name__ == "__main__":
    print("=== LRCLIB Timestamped Lyrics Fetcher ===\n")
    
    # Get user input
    track = input("Enter track name: ")
    artist = input("Enter artist name: ")
    album = input("Enter album name (optional, press Enter to skip): ").strip() or None
    
    # Search for lyrics
    print("\nSearching for lyrics...")
    lyrics_data = search_lyrics(track, artist, album)
    
    if lyrics_data:
        display_lyrics_info(lyrics_data)
        
        if lyrics_data.get('syncedLyrics'):
            print("\n✓ Synced lyrics found!")
            
            # Show preview
            display_synced_lyrics_preview(lyrics_data['syncedLyrics'])
            
            # Options
            print("\nOptions:")
            print("1. Save to LRC file")
            print("2. Demo karaoke mode")
            print("3. Both")
            print("4. Exit")
            
            choice = input("\nSelect option (1-4): ").strip()
            
            if choice in ['1', '3']:
                save_lrc_file(lyrics_data)
            
            if choice in ['2', '3']:
                speed = input("\nEnter playback speed (1.0 = normal, 2.0 = 2x faster): ").strip()
                try:
                    speed = float(speed) if speed else 1.0
                except:
                    speed = 1.0
                simulate_karaoke(lyrics_data['syncedLyrics'], speed)
        
        elif lyrics_data.get('plainLyrics'):
            print("\n✓ Plain lyrics found (no timestamps)")
            print("\nFirst few lines:")
            print("-" * 60)
            print('\n'.join(lyrics_data['plainLyrics'].split('\n')[:10]))
            
            save = input("\nSave plain lyrics to file? (y/n): ").lower()
            if save == 'y':
                filename = f"{lyrics_data['artistName']} - {lyrics_data['trackName']}.txt"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(lyrics_data['plainLyrics'])
                print(f"Saved to: {filename}")
        
        else:
            print("\n✗ No lyrics available for this track")
    else:
        print("\nCould not find lyrics for this track")