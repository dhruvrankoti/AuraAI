import os
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Photo Organiser"
    API_V1_STR: str = "/api/v1"
    
    # DB & Cache
    DATABASE_URL: str = Field(default="sqlite:///./aura_photos.db")
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    USE_CELERY: bool = Field(default=False)
    
    # Storage & Scanning
    UPLOAD_DIR: str = Field(default="./uploads")
    LOCAL_SCAN_DIR: str = Field(default="./photos_data")
    
    # AI Keys & Settings
    GEMINI_API_KEY: str = Field(default="")
    
    # Google Photos API credentials
    GOOGLE_CLIENT_ID: str = Field(default="")
    GOOGLE_CLIENT_SECRET: str = Field(default="")
    GOOGLE_REDIRECT_URI: str = Field(default="http://localhost:8000/api/v1/auth/google/callback")

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

# Create directories if they don't exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.LOCAL_SCAN_DIR, exist_ok=True)
