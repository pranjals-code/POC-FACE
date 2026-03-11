from typing import List, Literal, Optional

from pydantic import BaseModel


class UploadResponse(BaseModel):
    item_id: str
    filename: str
    path: str


class SearchResponse(BaseModel):
    job_id: str
    status: Literal["queued", "processing", "completed", "failed"]


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    progress: float
    detail: str
    clips: List[str]
    matched_timestamps: List[float]
    video_id: Optional[str] = None
    photo_id: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
