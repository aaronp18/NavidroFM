import subprocess

video_id = "z65Flj8PBq8"

url = f"https://music.youtube.com/watch?v={video_id}"
cmd = [
    "yt-dlp",
    "-x",
    "--audio-format",
    "mp3",
    "--audio-quality",
    "0",
    "--embed-thumbnail",
    "--no-embed-info-json",
    "--output",
    "testout.%(ext)s",
    "--format",
    "bestaudio",
    # "--extractor-args",
    # "youtube:player_client=tv",  # Switched to tv client to minimize mweb warnings
    "--sleep-interval",
    "2",
    "--no-update",
    # "--cookies",
    # "cookies.txt",
]
cmd.append(url)
# Run and capture/suppress harmless warnings if needed
result = subprocess.run(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

if result.returncode != 0:
    print(f"Error downloading: {result.stderr}")
else:
    print("Download and conversion completed successfully!")
