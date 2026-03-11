from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
VIDEO_DIR = DATA_DIR / "videos"
PHOTO_DIR = DATA_DIR / "photos"
CLIP_DIR = DATA_DIR / "clips"

FRAME_INTERVAL = 5
CLIP_PADDING_SECONDS = 2
MATCH_TOLERANCE = 0.5

for directory in (VIDEO_DIR, PHOTO_DIR, CLIP_DIR):
    directory.mkdir(parents=True, exist_ok=True)
