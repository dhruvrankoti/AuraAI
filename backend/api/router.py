from fastapi import APIRouter
from api.endpoints import photos, duplicates, people, search, auth

api_router = APIRouter()

api_router.include_router(photos.router, prefix="/photos", tags=["photos"])
api_router.include_router(duplicates.router, prefix="/duplicates", tags=["duplicates"])
api_router.include_router(people.router, prefix="/people", tags=["people"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
