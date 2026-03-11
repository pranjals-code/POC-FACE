# Face Clip Extractor POC

This project is a proof of concept with:

- FastAPI backend for video upload, photo upload, and asynchronous search jobs
- Streamlit frontend with `Admin` and `Users` sections in the sidebar
- OpenCV clip generation for timestamps where the uploaded face matches the uploaded person photo
- OpenCV-only face detection and approximate face matching for a lightweight POC
- PostgreSQL persistence via SQLAlchemy and Alembic

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` in the project root:

```bash
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/face_clip_poc
API_HOST=127.0.0.1
API_PORT=8000
STREAMLIT_PORT=8501
```

Run migrations:

```bash
alembic upgrade head
```

## Run

Backend:

```bash
uvicorn app.main:app --reload
```

Frontend:

```bash
streamlit run frontend/streamlit_app.py
```

## Flow

1. In `Admin`, upload the source video.
2. In `Users`, upload a clear face photo.
3. Use the generated `video_id` and `photo_id` to start search.
4. The app scans the video and creates short clips around matched timestamps.

## Notes

- This is a POC, but upload/job metadata now persists in PostgreSQL.
- Matching is approximate and intended for demo/P0C usage, not production-grade face recognition.
- Generated clips are still stored on local disk in `data/clips/`.
