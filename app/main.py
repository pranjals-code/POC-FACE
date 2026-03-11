from fastapi import Depends, FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import HealthResponse, JobStatusResponse, SearchResponse, UploadResponse
from app.services import create_job, get_job, save_photo, save_video


app = FastAPI(title="Face Clip Extractor POC", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/admin/videos", response_model=UploadResponse)
async def upload_video(file: UploadFile = File(...), db: Session = Depends(get_db)) -> UploadResponse:
    video = save_video(db, file)
    return UploadResponse(item_id=video.id, filename=video.filename, path=video.path)


@app.post("/users/photos", response_model=UploadResponse)
async def upload_photo(file: UploadFile = File(...), db: Session = Depends(get_db)) -> UploadResponse:
    photo = save_photo(db, file)
    return UploadResponse(item_id=photo.id, filename=photo.filename, path=photo.path)


@app.post("/search", response_model=SearchResponse)
async def search_person(video_id: str, photo_id: str, db: Session = Depends(get_db)) -> SearchResponse:
    job = create_job(db, video_id=video_id, photo_id=photo_id)
    return SearchResponse(job_id=job.id, status=job.status)


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def job_status(job_id: str, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = get_job(db, job_id)
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        detail=job.detail,
        clips=[clip.path for clip in job.clips],
        matched_timestamps=job.matched_timestamps or [],
        video_id=job.video_id,
        photo_id=job.photo_id,
    )
