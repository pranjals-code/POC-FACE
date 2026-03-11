import time
from pathlib import Path

import requests
import streamlit as st


API_BASE = "http://127.0.0.1:8000"


def upload_file(endpoint: str, uploaded_file):
    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
    return requests.post(f"{API_BASE}{endpoint}", files=files, timeout=120)


st.set_page_config(page_title="Face Clip Extractor", layout="wide")
st.title("Face Clip Extractor POC")
st.caption("Upload a video as admin, upload a photo as user, then extract clips where the person appears.")

if "video_id" not in st.session_state:
    st.session_state.video_id = None
if "photo_id" not in st.session_state:
    st.session_state.photo_id = None

section = st.sidebar.radio("Mode", ["Admin", "Users"])

if section == "Admin":
    st.subheader("Admin Video Upload")
    video_file = st.file_uploader("Upload source video", type=["mp4", "mov", "avi", "mkv"])
    if st.button("Upload Video", disabled=video_file is None):
        response = upload_file("/admin/videos", video_file)
        if response.ok:
            payload = response.json()
            st.session_state.video_id = payload["item_id"]
            st.success(f"Video uploaded. Video ID: {payload['item_id']}")
        else:
            st.error(response.text)

else:
    st.subheader("User Photo Upload")
    photo_file = st.file_uploader("Upload person photo", type=["jpg", "jpeg", "png"])
    if st.button("Upload Photo", disabled=photo_file is None):
        response = upload_file("/users/photos", photo_file)
        if response.ok:
            payload = response.json()
            st.session_state.photo_id = payload["item_id"]
            st.success(f"Photo uploaded. Photo ID: {payload['item_id']}")
        else:
            st.error(response.text)

st.divider()
st.subheader("Run Face Search")

video_id = st.text_input("Video ID", value=st.session_state.video_id or "")
photo_id = st.text_input("Photo ID", value=st.session_state.photo_id or "")

if st.button("Generate Clips", disabled=not (video_id and photo_id)):
    response = requests.post(
        f"{API_BASE}/search",
        params={"video_id": video_id, "photo_id": photo_id},
        timeout=120,
    )
    if not response.ok:
        st.error(response.text)
    else:
        job_id = response.json()["job_id"]
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        result_box = st.empty()

        while True:
            job_response = requests.get(f"{API_BASE}/jobs/{job_id}", timeout=120)
            if not job_response.ok:
                st.error(job_response.text)
                break

            job = job_response.json()
            progress_bar.progress(job["progress"])
            status_text.write(f"Status: {job['status']} | {job['detail']}")

            if job["status"] == "completed":
                if not job["clips"]:
                    result_box.info("No matching person found in the video.")
                else:
                    result_box.success(f"Generated {len(job['clips'])} clip(s).")
                    for clip_path in job["clips"]:
                        clip_bytes = Path(clip_path).read_bytes()
                        st.video(clip_bytes)
                        st.caption(clip_path)
                break

            if job["status"] == "failed":
                result_box.error(job["detail"])
                break

            time.sleep(2)
