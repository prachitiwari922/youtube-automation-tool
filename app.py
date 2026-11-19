import os
import requests
import streamlit as st
from urllib.parse import urlencode
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

st.set_page_config(page_title="Video Auto-Publisher", page_icon="🎬")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
REDIRECT_URI = "https://youtube-automation-tool-c9etdpp6kscmn6ddmipdcn.streamlit.app"
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"


def get_client_creds():
    try:
        client_id = str(st.secrets["CLIENT_ID"]).strip()
        client_secret = str(st.secrets["CLIENT_SECRET"]).strip()
    except KeyError as e:
        st.error(f"Streamlit Secrets mein '{e}' missing hai. Settings > Secrets mein CLIENT_ID aur CLIENT_SECRET daalein.")
        st.stop()

    if not client_id or not client_secret:
        st.error("Streamlit Secrets mein CLIENT_ID ya CLIENT_SECRET khali hai.")
        st.stop()

    return client_id, client_secret


def get_auth_url(client_id):
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    return f"{AUTH_URI}?{urlencode(params)}"


def exchange_code_for_creds(auth_code, client_id, client_secret):
    resp = requests.post(
        TOKEN_URI,
        data={
            "code": auth_code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    data = resp.json()
    if resp.status_code != 200 or "access_token" not in data:
        err_desc = data.get("error_description") or data.get("error") or str(data)
        raise RuntimeError(f"Google token error: {err_desc}")

    return Credentials(
        token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )


def get_authenticated_service():
    client_id, client_secret = get_client_creds()
    creds = st.session_state.get("credentials")

    if creds and creds.valid:
        return build("youtube", "v3", credentials=creds)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            st.session_state["credentials"] = creds
            return build("youtube", "v3", credentials=creds)
        except Exception:
            st.session_state.pop("credentials", None)

    oauth_error = st.query_params.get("error")
    auth_code = st.query_params.get("code")
    used_codes = st.session_state.setdefault("used_codes", set())
    auth_url = get_auth_url(client_id)

    if oauth_error:
        st.query_params.clear()
        st.error(f"Google login cancel ya block hua: {oauth_error}")
        st.markdown(f"### 👉 [Click here to Connect Your YouTube Account]({auth_url})")
        st.stop()

    if auth_code:
        if auth_code in used_codes:
            st.query_params.clear()
            st.rerun()

        used_codes.add(auth_code)
        try:
            new_creds = exchange_code_for_creds(auth_code, client_id, client_secret)
            st.session_state["credentials"] = new_creds
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.query_params.clear()
            st.error(str(e))
            st.markdown(f"### 👉 [Click here to Connect Your YouTube Account]({auth_url})")
            st.stop()

    st.markdown(f"### 👉 [Click here to Connect Your YouTube Account]({auth_url})")
    st.stop()


def upload_to_youtube(youtube, video_path, title, description):
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "private",
        },
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response


# ================= STREAMLIT UI =================
st.title("🎬 Video Auto-Publisher (Client Tool)")

youtube_service = get_authenticated_service()
st.success("✅ YouTube Account Connected Successfully!")

uploaded_file = st.file_uploader("Choose your video file (MP4/MOV)", type=["mp4", "mov", "avi"])
title = st.text_input("Enter Video Title")
description = st.text_area("Enter Video Description")

if st.button("Upload to YouTube"):
    if uploaded_file is not None and title.strip():
        temp_video_path = "temp_video.mp4"
        with open(temp_video_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        st.info("Uploading video to YouTube... Please wait.")
        try:
            response = upload_to_youtube(youtube_service, temp_video_path, title.strip(), description)
            st.success(f"🎉 Video uploaded successfully! Video ID: {response.get('id')}")
        except Exception as e:
            st.error(f"Upload failed: {e}")
        finally:
            if os.path.exists(temp_video_path):
                os.remove(temp_video_path)
    else:
        st.warning("Please provide both a video file and a title.")
