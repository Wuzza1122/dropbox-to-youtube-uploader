import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/upload", methods=["POST"])
def upload_to_youtube():
    data = request.json
    dropbox_url = data.get("dropbox_url")
    title = data.get("title", "Uploaded from Dropbox")
    description = data.get("description", "")

    if not dropbox_url:
        return jsonify({"error": "Missing dropbox_url"}), 400

    # === Get YouTube access token from refresh ===
    token_url = "https://oauth2.googleapis.com/token"
    refresh_data = {
        "client_id": os.environ["YOUTUBE_CLIENT_ID"],
        "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"],
        "refresh_token": os.environ["YOUTUBE_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }
    token_resp = requests.post(token_url, data=refresh_data)
    access_token = token_resp.json()["access_token"]

    # === Start resumable upload session ===
    init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "video/*"
    }
    body = {
        "snippet": {
            "title": title,
            "description": description,
        },
        "status": {
            "privacyStatus": "unlisted"
        }
    }
    init_resp = requests.post(init_url, headers=headers, json=body)
    upload_url = init_resp.headers["Location"]

    # === Upload video from Dropbox in chunks ===
    CHUNK_SIZE = 5 * 1024 * 1024
    with requests.get(dropbox_url, stream=True) as r:
        r.raise_for_status()
        offset = 0
        for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
            end = offset + len(chunk) - 1
            content_range = f"bytes {offset}-{end}/*"
            chunk_headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Length": str(len(chunk)),
                "Content-Range": content_range,
            }
            resp = requests.put(upload_url, headers=chunk_headers, data=chunk)
            offset += len(chunk)
            if resp.status_code in [200, 201]:
                return jsonify({"message": "✅ Upload complete", "youtube_response": resp.json()}), 200
            elif resp.status_code not in [308]:
                return jsonify({"error": "❌ Upload failed", "status": resp.status_code, "response": resp.text}), 500

    return jsonify({"message": "Upload incomplete"}), 500
