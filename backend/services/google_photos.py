import os
import json
import requests
from typing import Optional, List
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from config import settings

TOKEN_FILE = os.path.join(settings.UPLOAD_DIR, "google_photos_token.json")

class GooglePhotosService:
    @classmethod
    def get_flow(cls) -> Flow:
        client_config = {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
            }
        }
        return Flow.from_client_config(
            client_config,
            scopes=["https://www.googleapis.com/auth/photoslibrary.readonly"],
            redirect_uri=settings.GOOGLE_REDIRECT_URI
        )

    @classmethod
    def get_auth_url(cls) -> str:
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise ValueError("Google Client ID and Secret must be configured in environment variables.")
        flow = cls.get_flow()
        auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
        return auth_url

    @classmethod
    def exchange_code_for_tokens(cls, code: str) -> dict:
        flow = cls.get_flow()
        flow.fetch_token(code=code)
        credentials = flow.credentials
        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_type": "Bearer",
            "expires_in": 3600
        }

    @classmethod
    def refresh_access_token(cls, refresh_token: str) -> str:
        url = "https://oauth2.googleapis.com/token"
        payload = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        response = requests.post(url, data=payload)
        response.raise_for_status()
        return response.json()["access_token"]

    @classmethod
    def list_media_items(cls, access_token: str, refresh_token: Optional[str] = None, page_token: Optional[str] = None, limit: int = 50) -> dict:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        url = "https://photoslibrary.googleapis.com/v1/mediaItems"
        params = {"pageSize": limit}
        if page_token:
            params["pageToken"] = page_token

        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 401 and refresh_token:
                # Refresh token dynamically
                print("Google Photos access token expired. Refreshing...")
                new_token = cls.refresh_access_token(refresh_token)
                headers["Authorization"] = f"Bearer {new_token}"
                response = requests.get(url, headers=headers, params=params)
            
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching Google Photos: {e}")
            return {"mediaItems": [], "nextPageToken": None}

    @classmethod
    def download_media_item(cls, download_url: str, file_name: str) -> str:
        # Download URL for Google Photos requires appending suffix for quality, e.g. '=d' for original bytes
        full_url = f"{download_url}=d"
        response = requests.get(full_url, stream=True)
        response.raise_for_status()
        
        dest_path = os.path.join(settings.UPLOAD_DIR, f"gp_{file_name}")
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return dest_path
