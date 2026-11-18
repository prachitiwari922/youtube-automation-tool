import streamlit as st
import os
import json
import pickle
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Load client config from Streamlit Secrets
client_config = json.loads(st.secrets["GOOGLE_CLIENT_SECRET"])

def get_authenticated_service():
    creds = None
    if "credentials" in st.session_state:
        creds = st.session_state["credentials"]

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            st.session_state["credentials"] = creds
        else:
            # Automatically use the current app URL as redirect URI
            redirect_uri = st.experimental_get_url()
            if "?" in redirect_uri:
                redirect_uri = redirect_uri.split("?")[0]

            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=redirect_uri
            )
            
            auth_code = st.query_params.get("code")
            if auth_code:
                flow.fetch_token(code=auth_code)
                creds = flow.credentials
                st.session_state["credentials"] = creds
                st.query_params.clear()
                st.rerun()
            else:
                auth_url, _ = flow.authorization_url(prompt="consent")
                st.markdown(f"### 👉 [Click here to Connect Your YouTube Account]({auth_url})")
                st.stop()

    return build("youtube", "v3", credentials=creds)

def upload_to_youtube(video_path, title, description):
    youtube = get_authenticated_service()
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "private"
        }
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
    return response

# ================= STREAMLIT UI =================
st.title("🎬 Video Auto-Publisher (Client Tool)")

youtube_service = get_authenticated_service()
st.success("✅ YouTube Account Connected Successfully!")

uploaded_file = st.file_uploader("Choose your video file (MP4/MOV)", type=["mp4", "mov", "avi"])
title = st.text_input("Enter Video Title")
description = st.text_area("Enter Video Description")

if st.button("Upload to YouTube"):
    if uploaded_file is not None and title:
        temp_video_path = "temp_video.mp4"
        with open(temp_video_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.info("Uploading video to YouTube... Please wait.")
        try:
            response = upload_to_youtube(temp_video_path, title, description)
            st.success(f"🎉 Video uploaded successfully! Video ID: {response.get('id')}")
            if os.path.exists(temp_video_path):
                os.remove(temp_video_path)
        except Exception as e:
            st.error(f"Upload failed: {e}")
    else:
        st.warning("Please provide both a video file and a title.")
        