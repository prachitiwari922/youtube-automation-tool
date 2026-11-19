import os
import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

st.set_page_config(page_title="Video Auto-Publisher", page_icon="🎬")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
REDIRECT_URI = "https://youtube-automation-tool-c9etdpp6kscmn6ddmipdcn.streamlit.app"


def get_client_config():
    try:
        client_id = str(st.secrets["CLIENT_ID"]).strip()
        client_secret = str(st.secrets["CLIENT_SECRET"]).strip()
    except KeyError as e:
        st.error(f"Streamlit Secrets mein key missing hai: {e}. Settings > Secrets mein CLIENT_ID aur CLIENT_SECRET daalein.")
        st.stop()

    if not client_id or not client_secret:
        st.error("Streamlit Secrets mein CLIENT_ID ya CLIENT_SECRET khali hai.")
        st.stop()

    return {
        "web": {
            "client_id": client_id,
            "project_id": "youtube-bot-506207",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": client_secret,
            "redirect_uris": [REDIRECT_URI],
        }
    }


def build_flow():
    return Flow.from_client_config(
        get_client_config(),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )


def get_authenticated_service():
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
            creds = None

    oauth_error = st.query_params.get("error")
    auth_code = st.query_params.get("code")
    used_codes = st.session_state.setdefault("used_codes", set())

    if oauth_error:
        st.query_params.clear()
        st.error(f"Google login cancel ya block hua: {oauth_error}")
        flow = build_flow()
        auth_url, _ = flow.authorization_url(
            prompt="consent",
            access_type="offline",
            include_granted_scopes="true",
        )
        st.markdown(f"### 👉 [Click here to Connect Your YouTube Account]({auth_url})")
        st.stop()

    if auth_code:
        if auth_code in used_codes:
            st.query_params.clear()
            st.rerun()

        used_codes.add(auth_code)
        flow = build_flow()
        try:
            flow.fetch_token(code=auth_code)
            st.session_state["credentials"] = flow.credentials
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.query_params.clear()
            st.error(f"Token exchange error: {e}")
            auth_url, _ = flow.authorization_url(
                prompt="consent",
                access_type="offline",
                include_granted_scopes="true",
            )
            st.markdown(f"### 👉 [Click here to Connect Your YouTube Account]({auth_url})")
            st.stop()

    flow = build_flow()
    auth_url, _ = flow.authorization_url(
        prompt="consent",
        access_type="offline",
        include_granted_scopes="true",
    )
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
