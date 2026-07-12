from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import RedirectResponse
from services.google_photos import GooglePhotosService

router = APIRouter()

@router.get("/google/url")
def get_google_auth_url():
    """
    Returns the Google OAuth URL for the Google Photos API.
    """
    try:
        url = GooglePhotosService.get_auth_url()
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/google/callback")
def google_auth_callback(code: str = Query(...)):
    """
    Receives Google OAuth callback, exchanges code for credentials, and redirects to frontend.
    """
    try:
        tokens = GooglePhotosService.exchange_code_for_tokens(code)
        access_token = tokens.get("access_token", "")
        refresh_token = tokens.get("refresh_token", "")
        # Redirect to frontend settings page with tokens in URL
        return RedirectResponse(
            url=f"http://localhost:3000/settings?google_photos=connected&token={access_token}&refresh_token={refresh_token}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {e}")
