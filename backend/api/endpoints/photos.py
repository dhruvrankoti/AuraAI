import os
import shutil
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from db.session import get_db
from db.models import Photo, Face
from config import settings
from tasks import process_photo, sync_local_photos, sync_google_photos
from services.google_photos import GooglePhotosService

router = APIRouter()

@router.get("/")
def list_photos(
    category: Optional[str] = None,
    storage_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    query = db.query(Photo)
    if category:
        query = query.filter(Photo.category == category)
    if storage_type:
        query = query.filter(Photo.storage_type == storage_type)
    
    total = query.count()
    # Order by taken_at descending
    photos = query.order_by(Photo.taken_at.desc()).offset(skip).limit(limit).all()
    
    # Format response
    results = []
    for p in photos:
        results.append({
            "id": p.id,
            "storage_type": p.storage_type,
            "file_path": p.file_path,
            "category": p.category,
            "caption": p.caption,
            "taken_at": p.taken_at,
            "created_at": p.created_at,
            "has_faces": len(p.faces) > 0
        })
        
    return {"total": total, "photos": results, "skip": skip, "limit": limit}

@router.post("/upload")
def upload_photo(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    # Save the uploaded file
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    dest_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    
    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")
        
    # Queue processing task
    if settings.USE_CELERY:
        task = process_photo.delay(dest_path, "local")
        task_id = task.id
    else:
        background_tasks.add_task(process_photo, dest_path, "local")
        task_id = "local_background_task"
    
    return {"status": "processing", "file_path": dest_path, "task_id": task_id}

@router.get("/{photo_id}")
def get_photo_detail(photo_id: str, db: Session = Depends(get_db)):
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
        
    faces = []
    for f in photo.faces:
        faces.append({
            "id": f.id,
            "bounding_box": f.bounding_box,
            "person_cluster_id": f.person_cluster_id,
            "person_name": f.person_cluster.name if f.person_cluster else "Unknown"
        })
        
    return {
        "id": photo.id,
        "storage_type": photo.storage_type,
        "file_path": photo.file_path,
        "sha256": photo.sha256,
        "phash": photo.phash,
        "category": photo.category,
        "caption": photo.caption,
        "ocr_text": photo.ocr_text,
        "taken_at": photo.taken_at,
        "metadata_json": photo.metadata_json,
        "faces": faces
    }

@router.get("/{photo_id}/file")
def get_photo_file(photo_id: str, db: Session = Depends(get_db)):
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
        
    if not os.path.exists(photo.file_path):
        raise HTTPException(status_code=404, detail="Photo file not found on disk")
        
    # Return file response
    return FileResponse(photo.file_path)

@router.delete("/{photo_id}")
def delete_photo(photo_id: str, db: Session = Depends(get_db)):
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
        
    # Delete file from local storage if applicable
    if photo.storage_type == "local" or photo.file_path.startswith(settings.UPLOAD_DIR):
        if os.path.exists(photo.file_path):
            try:
                os.remove(photo.file_path)
            except Exception as e:
                print(f"Error deleting file {photo.file_path}: {e}")
                
    db.delete(photo)
    db.commit()
    return {"status": "deleted"}

@router.post("/sync/local")
def trigger_local_sync(background_tasks: BackgroundTasks):
    from tasks import get_sync_status
    status = get_sync_status()
    if status.get("local") == "syncing":
        raise HTTPException(status_code=400, detail="Local folder sync is already in progress.")

    if settings.USE_CELERY:
        task = sync_local_photos.delay()
        task_id = task.id
    else:
        background_tasks.add_task(sync_local_photos)
        task_id = "local_background_task"
    return {"status": "sync_triggered", "task_id": task_id}

class GoogleSyncRequest(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None

@router.post("/sync/google")
def trigger_google_sync(payload: GoogleSyncRequest, background_tasks: BackgroundTasks):
    from tasks import get_sync_status
    status = get_sync_status()
    if status.get("google") == "syncing":
        raise HTTPException(status_code=400, detail="Google Photos sync is already in progress.")

    if settings.USE_CELERY:
        task = sync_google_photos.delay(payload.access_token, payload.refresh_token)
        task_id = task.id
    else:
        background_tasks.add_task(sync_google_photos, payload.access_token, payload.refresh_token)
        task_id = "local_background_task"
    return {"status": "sync_triggered", "task_id": task_id}

@router.get("/status/google")
def check_google_connection(token: Optional[str] = Query(None)):
    # Check if a client-side Google Photos token is present
    connected = token is not None and len(token) > 0
    return {"connected": connected}

@router.get("/sync/status")
def check_sync_status():
    from tasks import get_sync_status
    return get_sync_status()
