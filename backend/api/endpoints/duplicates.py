from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from db.session import get_db
from db.models import Photo
from typing import List, Dict

router = APIRouter()

@router.get("/exact")
def get_exact_duplicates(db: Session = Depends(get_db)):
    """
    Finds exact duplicates by grouping photos with identical SHA256 hashes.
    """
    # Find SHA256 groups with more than 1 photo
    duplicate_shas = db.query(
        Photo.sha256,
        func.count(Photo.id).label("count")
    ).filter(Photo.sha256.isnot(None))\
     .group_by(Photo.sha256)\
     .having(func.count(Photo.id) > 1)\
     .all()

    results = []
    for sha, count in duplicate_shas:
        photos = db.query(Photo).filter(Photo.sha256 == sha).order_by(Photo.created_at).all()
        results.append({
            "sha256": sha,
            "count": count,
            "photos": [{
                "id": p.id,
                "file_path": p.file_path,
                "storage_type": p.storage_type,
                "created_at": p.created_at,
                "taken_at": p.taken_at
            } for p in photos]
        })
    
    return {"total_groups": len(results), "groups": results}

def hamming_distance(h1: int, h2: int) -> int:
    # Compute XOR and count set bits (Hamming distance)
    return bin(h1 ^ h2).count('1')

@router.get("/near")
def get_near_duplicates(
    threshold: int = Query(6, description="Hamming distance threshold (0-64). Lower means more similar.")
):
    """
    Finds near duplicates by comparing pHashes using an optimized
    Locality Sensitive Hashing (LSH) block-matching algorithm.
    """
    db = SessionLocal_helper()
    try:
        photos = db.query(Photo.id, Photo.file_path, Photo.phash, Photo.storage_type, Photo.taken_at).filter(Photo.phash.isnot(None)).all()
        if not photos:
            return {"total_pairs": 0, "pairs": []}

        # Cache photos by ID and convert hex pHash to 64-bit int
        photo_map = {}
        hash_ints = {}
        for p in photos:
            photo_map[p.id] = {
                "id": p.id,
                "file_path": p.file_path,
                "storage_type": p.storage_type,
                "taken_at": p.taken_at
            }
            try:
                hash_ints[p.id] = int(p.phash, 16)
            except ValueError:
                continue

        # LSH Index: Divide 64-bit hash into 4 chunks of 16-bits.
        # If two hashes have distance <= 4, they MUST share at least one chunk (Pigeonhole Principle).
        # We index photo IDs by chunk values.
        chunks: Dict[int, Dict[int, List[str]]] = {0: {}, 1: {}, 2: {}, 3: {}}
        
        for p_id, h_val in hash_ints.items():
            for i in range(4):
                chunk_val = (h_val >> (i * 16)) & 0xFFFF
                if chunk_val not in chunks[i]:
                    chunks[i][chunk_val] = []
                chunks[i][chunk_val].append(p_id)

        # Find candidate pairs and compute full Hamming distance
        detected_pairs = set()
        pairs_list = []

        for p_id, h_val in hash_ints.items():
            candidates = set()
            for i in range(4):
                chunk_val = (h_val >> (i * 16)) & 0xFFFF
                candidates.update(chunks[i][chunk_val])

            # Remove self
            candidates.discard(p_id)

            for cand_id in candidates:
                # Ensure we only process each pair once
                pair_key = tuple(sorted([p_id, cand_id]))
                if pair_key in detected_pairs:
                    continue

                cand_val = hash_ints[cand_id]
                dist = hamming_distance(h_val, cand_val)
                
                # If distance is within threshold, they are near duplicates
                if dist <= threshold:
                    detected_pairs.add(pair_key)
                    pairs_list.append({
                        "distance": dist,
                        "photo1": photo_map[p_id],
                        "photo2": photo_map[cand_id]
                    })

        # Sort by distance (closest first)
        pairs_list.sort(key=lambda x: x["distance"])
        return {"total_pairs": len(pairs_list), "pairs": pairs_list}
    finally:
        db.close()

# Temporary helper to avoid import loop or direct session access
def SessionLocal_helper():
    from db.session import SessionLocal
    return SessionLocal()
