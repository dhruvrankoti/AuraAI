import os
from typing import List
from db.session import SessionLocal
from db.models import Photo
from config import settings

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.tiff', '.bmp'}

class LocalScannerService:
    @staticmethod
    def get_all_image_paths(directory: str) -> List[str]:
        image_paths = []
        if not os.path.exists(directory):
            return []
            
        for root, _, files in os.walk(directory):
            for file in files:
                _, ext = os.path.splitext(file)
                if ext.lower() in IMAGE_EXTENSIONS:
                    image_paths.append(os.path.abspath(os.path.join(root, file)))
                    
        return image_paths

    @classmethod
    def scan_and_get_unprocessed(cls) -> List[str]:
        all_paths = cls.get_all_image_paths(settings.LOCAL_SCAN_DIR)
        if not all_paths:
            return []
            
        db = SessionLocal()
        try:
            # Query existing local file paths
            existing_photos = db.query(Photo.file_path).filter(
                Photo.storage_type == 'local'
            ).all()
            existing_paths = {p[0] for p in existing_photos}
            
            # Filter out already indexed files
            unprocessed = [p for p in all_paths if p not in existing_paths]
            return unprocessed
        finally:
            db.close()
