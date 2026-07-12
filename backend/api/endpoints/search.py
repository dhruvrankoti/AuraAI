from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import numpy as np

from db.session import get_db
from db.models import Photo, Face, PersonCluster
from services.search_planner import SearchPlanner
from services.ai_pipeline import AIService
from config import settings
from typing import List, Optional

router = APIRouter()

@router.post("/")
def search_photos(payload: dict, db: Session = Depends(get_db)):
    """
    Search photos using a natural language query translated into a structured search plan.
    """
    query_text = payload.get("query")
    if not query_text:
        raise HTTPException(status_code=400, detail="Query text is required")

    # 1. Translate Query to Search Plan
    plan = SearchPlanner.plan_search(query_text)
    
    # 2. Build Database Query
    query = db.query(Photo)
    
    # Apply category filter
    if plan.categories:
        query = query.filter(Photo.category.in_(plan.categories))
        
    # Apply date range filters
    if plan.date_start:
        query = query.filter(Photo.taken_at >= plan.date_start)
    if plan.date_end:
        query = query.filter(Photo.taken_at <= plan.date_end)
        
    # Apply OCR text filter
    if plan.ocr_query:
        query = query.filter(Photo.ocr_text.ilike(f"%{plan.ocr_query}%"))
        
    # Check dialect for JSON extraction
    is_sqlite = settings.DATABASE_URL.startswith("sqlite")

    # Apply location filters (caption or metadata)
    if plan.location:
        loc_term = f"%{plan.location}%"
        if is_sqlite:
            # SQLite JSON syntax
            query = query.filter(
                (Photo.caption.ilike(loc_term)) |
                (Photo.file_path.ilike(loc_term)) |
                (func.json_extract(Photo.metadata_json, "$.location").ilike(loc_term))
            )
        else:
            # PostgreSQL JSON syntax
            query = query.filter(
                (Photo.caption.ilike(loc_term)) |
                (Photo.file_path.ilike(loc_term)) |
                (func.json_extract_path_text(Photo.metadata_json, "location").ilike(loc_term))
            )
        
    # Apply person filters (join faces and clusters)
    if plan.person_names:
        # Match any of the specified names in person clusters
        query = query.join(Photo.faces).join(Face.person_cluster).filter(
            PersonCluster.name.in_(plan.person_names)
        )
        
    # Apply CLIP Vector Similarity Ordering if semantic search query is present
    results = []
    if plan.semantic_query:
        try:
            # Generate embedding for the search query
            query_vector = AIService.get_text_clip_embedding(plan.semantic_query)
            
            if is_sqlite:
                # SQLite: Fetch filtered rows and rank in Python
                photos_all = query.all()
                q_vec_np = np.array(query_vector)
                
                scored_photos = []
                for p in photos_all:
                    if p.clip_embedding:
                        # clip_embedding is parsed as list by SafeVector
                        p_vec_np = np.array(p.clip_embedding)
                        # Cosine similarity
                        dot_prod = np.dot(q_vec_np, p_vec_np)
                        norm_q = np.linalg.norm(q_vec_np)
                        norm_p = np.linalg.norm(p_vec_np)
                        if norm_q > 0 and norm_p > 0:
                            sim = dot_prod / (norm_q * norm_p)
                        else:
                            sim = -1.0
                        scored_photos.append((p, sim))
                    else:
                        scored_photos.append((p, -1.0))
                
                # Sort by similarity descending (highest similarity first)
                scored_photos.sort(key=lambda x: x[1], reverse=True)
                photos = [sp[0] for sp in scored_photos[:40]]
            else:
                # PostgreSQL: Native pgvector <=> operator
                photos = query.order_by(Photo.clip_embedding.cosine_distance(query_vector)).limit(40).all()
        except Exception as e:
            print(f"Error executing vector similarity: {e}. Falling back to default list.")
            photos = query.order_by(Photo.taken_at.desc()).limit(40).all()
    else:
        # Default order by taken time
        photos = query.order_by(Photo.taken_at.desc()).limit(40).all()

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

    # Return search plan and results for transparency
    return {
        "query": query_text,
        "search_plan": plan.model_dump(),
        "results_count": len(results),
        "photos": results
    }
