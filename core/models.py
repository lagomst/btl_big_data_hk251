from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, File, UploadFile, APIRouter, Request, Form, Query
from typing import Optional, Any
from decimal import Decimal

# Data models
class QueryRequest(BaseModel):
    knowledge: str
    query: str
    # mode: str = "hybrid"
    # only_need_context: bool = False


class InsertRequest(BaseModel):
    knowledge: str
    text: str
    custom_filename: str | None
    custom_file_path: str | None
    tokens_limit: Optional[int] = None
    money_limit: Optional[Decimal] = None
    price_1m_prompt: Optional[Decimal] = None
    price_1m_completion: Optional[Decimal] = None


class ChatResponse(BaseModel):
    status: str
    data: dict
    message: str | None = None

class PathListResponse(BaseModel):
    status: str
    data: list[str] |  None = None
    message: str | None = None
    
class InsertFilesRequestOCR(BaseModel):
    image_ops: Optional[str] = "grayscale,scale:factor=1"
    languages: Optional[str] = "eng"    

class InsertFilesRequest(BaseModel):
    file_url: Optional[str] = None
    ocr_option: Optional[InsertFilesRequestOCR] = None
    
class InsertResponse(BaseModel):
    error: str | None
    time: float | None
    tokens_used: dict[str, Any] | None
    files: dict[str, Any] | None
    model_used: str | None
    api_tier: str | None
    
class LimitTracker(BaseModel):
    tokens_limit: Optional[int] = None
    money_limit: Optional[Decimal] = None
    price_1m_prompt: Optional[Decimal] = None
    price_1m_completion: Optional[Decimal] = None

class ModelDetail(BaseModel):
    model_used: Optional[str] = None
    api_tier: Optional[str] = None