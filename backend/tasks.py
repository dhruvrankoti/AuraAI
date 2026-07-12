import os
import uuid
import json
from datetime import datetime
from PIL import Image
from celery import Celery
from sklearn.cluster import DBSCAN
import numpy as np

from config import settings
from db.session import SessionLocal
from db.models import Photo, Face, PersonCluster
from services.ai_pipeline import AIService
from services.local_scanner import LocalScannerService
from services.google_photos import GooglePhotosService

celery_app = Celery("tasks", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

STATUS_FILE = os.path.join(settings.UPLOAD_DIR, "sync_status.json")

def get_sync_status() -> dict:
    if not os.path.exists(STATUS_FILE):
        return {"local": "idle", "google": "idle"}
    try:
        with open(STATUS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"local": "idle", "google": "idle"}

def set_sync_status(sync_type: str, status: str):
    current = get_sync_status()
    current[sync_type] = status
    try:
        os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
        with open(STATUS_FILE, "w") as f:
            json.dump(current, f)
    except Exception as e:
        print(f"Error saving sync status: {e}")

@celery_app.task(name="process_photo")
def process_photo(file_path: str, storage_type: str = "local", google_metadata: dict = None):
    """
    Main background pipeline for scanning, hashing, categorizing, face extraction, and OCR.
    """
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return None

    db = SessionLocal()
    try:
        # Check if the exact file path is already in the database
        existing_path = db.query(Photo).filter(Photo.file_path == file_path).first()
        if existing_path:
            print(f"File path already indexed: {file_path}")
            return str(existing_path.id)

        # 1. Exact Duplicate Check (SHA256)
        sha256 = AIService.compute_sha256(file_path)
        existing_sha = db.query(Photo).filter(Photo.sha256 == sha256).first()
        if existing_sha:
            print(f"Duplicate exact image found (shares SHA: {sha256}). Creating duplicate record.")
            # Copy details from existing record to save CPU/GPU cycles!
            photo = Photo(
                storage_type=storage_type,
                file_path=file_path,
                sha256=sha256,
                phash=existing_sha.phash,
                category=existing_sha.category,
                caption=existing_sha.caption,
                ocr_text=existing_sha.ocr_text,
                taken_at=existing_sha.taken_at,
                metadata_json=existing_sha.metadata_json,
                clip_embedding=existing_sha.clip_embedding,
                ocr_embedding=existing_sha.ocr_embedding
            )
            db.add(photo)
            db.flush()
            
            # Copy faces if any
            existing_faces = db.query(Face).filter(Face.photo_id == existing_sha.id).all()
            for ef in existing_faces:
                face = Face(
                    photo_id=photo.id,
                    face_embedding=ef.face_embedding,
                    bounding_box=ef.bounding_box,
                    person_cluster_id=ef.person_cluster_id
                )
                db.add(face)
            
            db.commit()
            return str(photo.id)

        # Load image
        img = Image.open(file_path)
        
        # 2. Perceptual Hash
        phash = AIService.compute_phash(img)

        # 3. CLIP Embedding
        clip_emb = AIService.get_image_clip_embedding(img)

        # 4. Rich Metadata & OCR & Categorization (Gemini or Local Fallback)
        ocr_text = ""
        caption = ""
        category = "other"
        taken_at = None
        metadata_json = google_metadata or {}

        # Attempt to read EXIF date
        try:
            exif = img._getexif()
            if exif and 36867 in exif:  # DateTimeOriginal tag
                date_str = exif[36867]
                taken_at = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
        except Exception:
            pass

        # If Google Photos provided metadata, use its taken time
        if google_metadata and "mediaMetadata" in google_metadata:
            creation_time = google_metadata["mediaMetadata"].get("creationTime")
            if creation_time:
                # Format: "2014-10-09T18:02:19Z"
                try:
                    taken_at = datetime.fromisoformat(creation_time.replace("Z", "+00:00"))
                except ValueError:
                    pass

        # Always process photos locally using CLIP, MTCNN, FaceNet, and PyTesseract.
        # This prevents Gemini API quota exhaustion for large photo libraries,
        # keeping the Gemini API reserved exclusively for on-demand search query planning.
        print(f"Analyzing {file_path} with Local AI Pipeline...")
        category = AIService.classify_zero_shot(img)
        
        # Run OCR locally if categorized as document/receipt/prescription
        if category in ["document", "receipt", "prescription"]:
            ocr_text = AIService.run_local_ocr(img)
            caption = f"Scanned {category}"
        else:
            caption = f"Photo containing {category}"

        # 5. Save OCR embedding if text is extracted
        ocr_emb = None
        if ocr_text.strip():
            ocr_emb = AIService.get_ocr_text_embedding(ocr_text)

        # 6. Save Photo Record
        photo = Photo(
            storage_type=storage_type,
            file_path=file_path,
            sha256=sha256,
            phash=phash,
            category=category,
            caption=caption,
            ocr_text=ocr_text if ocr_text else None,
            taken_at=taken_at or datetime.now(),
            metadata_json=metadata_json,
            clip_embedding=clip_emb,
            ocr_embedding=ocr_emb
        )
        db.add(photo)
        db.flush()  # Generate photo.id

        # 7. Face Detection & Embedding (Local)
        faces_data = AIService.detect_and_embed_faces(img)
        print(f"Detected {len(faces_data)} faces in {file_path}")
        for face_info in faces_data:
            face = Face(
                photo_id=photo.id,
                face_embedding=face_info["embedding"],
                bounding_box=face_info["bounding_box"]
            )
            db.add(face)

        db.commit()
        return photo.id
    except Exception as e:
        db.rollback()
        print(f"Failed to process photo {file_path}: {e}")
        raise e
    finally:
        db.close()

@celery_app.task(name="cluster_faces")
def cluster_faces():
    """
    Retrieves all unclustered face embeddings, runs DBSCAN, and updates person_clusters.
    """
    db = SessionLocal()
    try:
        # Fetch all faces with embeddings
        faces = db.query(Face).all()
        if not faces:
            print("No faces found to cluster.")
            return

        embeddings = [face.face_embedding for face in faces]
        X = np.array(embeddings)

        # Run DBSCAN (using Euclidean distance on L2-normalized FaceNet vectors)
        # eps 0.6 is a standard threshold for FaceNet embeddings (equivalent to Cosine distance threshold)
        dbscan = DBSCAN(eps=0.55, min_samples=2, metric="euclidean")
        labels = dbscan.fit_predict(X)

        # Map cluster label to cluster ID
        cluster_mapping = {}
        
        # Reset current cluster relations
        # We re-evaluate all clusters to keep it consistent
        for face in faces:
            face.person_cluster_id = None

        # Clean existing clusters
        db.query(PersonCluster).delete()
        db.commit()

        for idx, label in enumerate(labels):
            if label == -1:
                # Noise/unrecognized face
                continue
                
            if label not in cluster_mapping:
                # Create a new Person Cluster
                new_cluster = PersonCluster(
                    name=f"Person {len(cluster_mapping) + 1}",
                    cover_face_id=faces[idx].id
                )
                db.add(new_cluster)
                db.flush()
                cluster_mapping[label] = new_cluster.id

            faces[idx].person_cluster_id = cluster_mapping[label]

        db.commit()
        print(f"Grouped faces into {len(cluster_mapping)} clusters.")
    except Exception as e:
        db.rollback()
        print(f"Failed to cluster faces: {e}")
    finally:
        db.close()

@celery_app.task(name="sync_local_photos")
def sync_local_photos():
    """
    Scans the local directory and dispatches process_photo tasks for new files.
    """
    set_sync_status("local", "syncing")
    try:
        unprocessed_paths = LocalScannerService.scan_and_get_unprocessed()
        print(f"Found {len(unprocessed_paths)} new local photos.")
        for path in unprocessed_paths:
            if settings.USE_CELERY:
                process_photo.delay(path, "local")
            else:
                process_photo(path, "local")
        return len(unprocessed_paths)
    finally:
        set_sync_status("local", "idle")

@celery_app.task(name="sync_google_photos")
def sync_google_photos(access_token: str, refresh_token: str = None):
    """
    Syncs the latest page of Google Photos.
    """
    set_sync_status("google", "syncing")
    try:
        res = GooglePhotosService.list_media_items(
            access_token=access_token,
            refresh_token=refresh_token,
            limit=100
        )
        items = res.get("mediaItems", [])
        
        db = SessionLocal()
        new_count = 0
        try:
            for item in items:
                g_id = item["id"]
                # Check if this Google Photo ID is already in DB (file_path stores google photo ID for GP items)
                exists = db.query(Photo).filter(
                    Photo.storage_type == "google_photos",
                    Photo.file_path == g_id
                ).first()
                
                if not exists:
                    # Download media item to upload directory
                    file_name = item.get("filename", f"{g_id}.jpg")
                    download_url = item.get("baseUrl")
                    
                    # We download synchronously in worker or launch a task to download and process
                    # Let's download first
                    try:
                        local_path = GooglePhotosService.download_media_item(download_url, file_name)
                        # Dispatch process task using the local downloaded file path, but keeping storage_type as google_photos
                        if settings.USE_CELERY:
                            process_photo.delay(local_path, "google_photos", item)
                        else:
                            process_photo(local_path, "google_photos", item)
                        new_count += 1
                    except Exception as e:
                        print(f"Error downloading Google Photo item {g_id}: {e}")
            return new_count
        finally:
            db.close()
    finally:
        set_sync_status("google", "idle")
