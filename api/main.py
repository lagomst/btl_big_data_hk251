from fastapi import APIRouter

from api.routes import rag

api_router = APIRouter()
api_router.include_router(rag.router, prefix="/rag", tags=["RAG"])