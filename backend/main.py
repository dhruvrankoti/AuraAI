from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from db.init_db import init_db
from api.router import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    # Initialize DB (enable vector extension, create tables)
    init_db()
    
    # Reset sync statuses on startup to clear any dirty states from previous crashes
    try:
        from tasks import set_sync_status
        set_sync_status("local", "idle")
        set_sync_status("google", "idle")
        print("Sync status file initialized/reset to idle.")
    except Exception as e:
        print(f"Failed to reset sync status on startup: {e}")

@app.get("/")
def read_root():
    return {"message": "Welcome to the AI Photo Organiser API", "docs": "/docs"}

# Include routers
app.include_router(api_router, prefix=settings.API_V1_STR)
