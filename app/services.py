from __future__ import annotations

import shutil
import subprocess
import threading
import uuid
from pathlib import Path

import cv2
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.config import CLIP_DIR, CLIP_PADDING_SECONDS, FRAME_INTERVAL, MATCH_TOLERANCE, PHOTO_DIR, VIDEO_DIR
from app.database import SessionLocal
from app.models import Clip, Job, Photo, Video


FACE_CASCADE = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"))
ORB = cv2.ORB_create(nfeatures=512)


def _save_upload(upload: UploadFile, target_dir: Path) -> tuple[str, Path]:
    suffix = Path(upload.filename or "").suffix or ".bin"
    item_id = uuid.uuid4().hex
    target_path = target_dir / f"{item_id}{suffix}"
    with target_path.open("wb") as file_obj:
        shutil.copyfileobj(upload.file, file_obj)
    return item_id, target_path


def save_video(db: Session, upload: UploadFile) -> Video:
    item_id, path = _save_upload(upload, VIDEO_DIR)
    video = Video(id=item_id, filename=upload.filename or path.name, path=str(path))
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def save_photo(db: Session, upload: UploadFile) -> Photo:
    item_id, path = _save_upload(upload, PHOTO_DIR)
    photo = Photo(id=item_id, filename=upload.filename or path.name, path=str(path))
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


def get_job(db: Session, job_id: str) -> Job:
    job = (
        db.query(Job)
        .options(joinedload(Job.clips))
        .filter(Job.id == job_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def create_job(db: Session, video_id: str, photo_id: str) -> Job:
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    job = Job(video_id=video_id, photo_id=photo_id)
    db.add(job)
    db.commit()
    db.refresh(job)

    thread = threading.Thread(target=_process_job, args=(job.id,), daemon=True)
    thread.start()
    return job


def _update_job(job_id: str, **fields) -> None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
        for key, value in fields.items():
            setattr(job, key, value)
        db.add(job)
        db.commit()
    finally:
        db.close()


def _process_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        _update_job(job_id, status="processing", detail="Loading reference photo")
        photo_path = Path(job.photo.path)
        video_path = Path(job.video.path)

        reference_image = cv2.imread(str(photo_path))
        reference_descriptors = _extract_face_descriptors(reference_image)
        if reference_descriptors is None:
            raise ValueError("No face detected in the uploaded photo.")
        if len(reference_descriptors) < 10:
            raise ValueError("Reference face does not contain enough features for matching.")

        timestamps = _find_matching_timestamps(video_path, reference_descriptors, job_id)
        _update_job(job_id, matched_timestamps=timestamps, detail="Exporting clips")
        clip_paths = _export_clips(video_path, timestamps, job_id)

        fresh_job = db.query(Job).filter(Job.id == job_id).first()
        if fresh_job:
            for clip_path in clip_paths:
                db.add(Clip(job_id=job_id, path=clip_path))
            fresh_job.status = "completed"
            fresh_job.progress = 1.0
            fresh_job.detail = "Completed"
            db.add(fresh_job)
            db.commit()
    except Exception as exc:  # pragma: no cover - best effort status propagation
        _update_job(job_id, status="failed", detail=str(exc))
    finally:
        db.close()


def _find_matching_timestamps(video_path: Path, reference_descriptors, job_id: str) -> list[float]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError("Unable to open video file.")

    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    frame_index = 0
    timestamps: list[float] = []

    while True:
        success, frame = capture.read()
        if not success:
            break

        if frame_index % FRAME_INTERVAL == 0 and _frame_contains_match(frame, reference_descriptors):
            timestamps.append(frame_index / fps)

        frame_index += 1
        _update_job(
            job_id,
            progress=min(frame_index / total_frames, 0.9),
            detail=f"Scanning frame {frame_index}/{total_frames}",
        )

    capture.release()
    return _merge_timestamps(timestamps)


def _frame_contains_match(frame, reference_descriptors) -> bool:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(faces) == 0:
        return False

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    for x, y, w, h in faces:
        face_region = frame[y : y + h, x : x + w]
        candidate_descriptors = _extract_face_descriptors(face_region, detect_face=False)
        if candidate_descriptors is None:
            continue

        matches = matcher.match(reference_descriptors, candidate_descriptors)
        if not matches:
            continue

        good_matches = [match for match in matches if match.distance < 45]
        match_ratio = len(good_matches) / max(min(len(reference_descriptors), len(candidate_descriptors)), 1)
        if len(good_matches) >= 12 and match_ratio >= MATCH_TOLERANCE:
            return True

    return False


def _extract_face_descriptors(image, detect_face: bool = True):
    if image is None:
        return None

    face_region = image
    if detect_face:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        if len(faces) == 0:
            return None
        x, y, w, h = max(faces, key=lambda face: face[2] * face[3])
        face_region = image[y : y + h, x : x + w]

    face_gray = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
    normalized_face = cv2.resize(face_gray, (224, 224))
    _, descriptors = ORB.detectAndCompute(normalized_face, None)
    return descriptors


def _merge_timestamps(timestamps: list[float]) -> list[float]:
    if not timestamps:
        return []

    merged = [timestamps[0]]
    for timestamp in timestamps[1:]:
        if timestamp - merged[-1] > CLIP_PADDING_SECONDS * 2:
            merged.append(timestamp)
    return merged


def _export_clips(video_path: Path, timestamps: list[float], job_id: str) -> list[str]:
    if not timestamps:
        return []

    clips: list[str] = []
    for index, timestamp in enumerate(timestamps, start=1):
        start_time = max(timestamp - CLIP_PADDING_SECONDS, 0)
        duration = CLIP_PADDING_SECONDS * 2
        clip_path = CLIP_DIR / f"{job_id}_clip_{index}.mp4"
        command = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start_time:.3f}",
            "-i",
            str(video_path),
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(clip_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise ValueError(f"ffmpeg clip export failed: {result.stderr.strip()}")
        clips.append(str(clip_path))
    return clips
