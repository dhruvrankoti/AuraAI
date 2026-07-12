from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from db.session import get_db
from db.models import PersonCluster, Face, Photo
from config import settings
from tasks import cluster_faces

router = APIRouter()

@router.get("/")
def list_people(db: Session = Depends(get_db)):
    """
    Lists all person clusters, counting faces and retrieving their cover photo.
    """
    clusters = db.query(PersonCluster).all()
    results = []
    
    for c in clusters:
        # Count faces in this cluster
        face_count = db.query(Face).filter(Face.person_cluster_id == c.id).count()
        
        # Retrieve cover photo path
        cover_photo_id = None
        cover_photo_path = None
        if c.cover_face_id:
            face = db.query(Face).filter(Face.id == c.cover_face_id).first()
            if face and face.photo:
                cover_photo_id = face.photo.id
                cover_photo_path = face.photo.file_path
        
        # If no cover photo is set yet, pick the first face in the cluster
        if not cover_photo_path:
            first_face = db.query(Face).filter(Face.person_cluster_id == c.id).first()
            if first_face and first_face.photo:
                cover_photo_id = first_face.photo.id
                cover_photo_path = first_face.photo.file_path
                
        results.append({
            "id": c.id,
            "name": c.name,
            "face_count": face_count,
            "cover_photo_id": cover_photo_id,
            "cover_photo_path": cover_photo_path
        })
        
    # Sort by number of photos descending
    results.sort(key=lambda x: x["face_count"], reverse=True)
    return results

@router.get("/{cluster_id}")
def get_person_details(cluster_id: str, db: Session = Depends(get_db)):
    """
    Retrieves all photos belonging to a person cluster.
    """
    cluster = db.query(PersonCluster).filter(PersonCluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Person not found")
        
    # Get all photos that have a face associated with this cluster
    faces = db.query(Face).filter(Face.person_cluster_id == cluster_id).all()
    photo_ids = list(set([f.photo_id for f in faces]))
    photos = db.query(Photo).filter(Photo.id.in_(photo_ids)).all() if photo_ids else []
    
    return {
        "id": cluster.id,
        "name": cluster.name,
        "photos": [{
            "id": p.id,
            "file_path": p.file_path,
            "storage_type": p.storage_type,
            "caption": p.caption,
            "taken_at": p.taken_at
        } for p in photos]
    }

@router.put("/{cluster_id}")
def rename_person(cluster_id: str, payload: dict, db: Session = Depends(get_db)):
    """
    Updates the name of a person cluster.
    """
    cluster = db.query(PersonCluster).filter(PersonCluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Person not found")
        
    new_name = payload.get("name")
    if not new_name:
        raise HTTPException(status_code=400, detail="Name is required")
        
    cluster.name = new_name
    db.commit()
    return {"id": cluster.id, "name": cluster.name}

@router.post("/recluster")
def trigger_face_clustering(background_tasks: BackgroundTasks):
    """
    Triggers face reclustering task.
    """
    if settings.USE_CELERY:
        task = cluster_faces.delay()
        task_id = task.id
    else:
        background_tasks.add_task(cluster_faces)
        task_id = "local_background_task"
    return {"status": "clustering_triggered", "task_id": task_id}
