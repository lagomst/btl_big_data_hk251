from sys import getsizeof
from core.newsrag import ManagerRAG
from fastapi import HTTPException, File, UploadFile, APIRouter, Request, Form, Query
from fastapi.responses import StreamingResponse
import core.commons as commons

# import utils
from typing import Generator, Optional
import time
from datetime import datetime
from decimal import Decimal

from core.models import ChatResponse, PathListResponse, InsertRequest, BaseModel, InsertResponse, LimitTracker, ModelDetail
from core.config import settings
from core.request import download_google_drive_file
from newsplease import NewsPlease, NewsArticle

router = APIRouter()


# def generate_filename(knowledge: str, name: str) -> str:
#     return f"{knowledge}_{name}"

def generate_filepath(knowledge: str, name: str, custom_path: str = None) -> str:
    filepath = '/' + knowledge
    if custom_path:
        filepath += '/' + custom_path.strip()
    filepath += '/' + name + '/'
    return filepath

def get_data_from_filename(inner_name: str):
    parts = inner_name.split('_', maxsplit=1)
    return parts[0], parts[1]

def get_default_name() -> str:
    today = datetime.now().isoformat()
    return "user_input_" + today

def get_default_path() -> str:
    return ""

# API routes
@router.get("/knowledge", response_model=PathListResponse)
async def knowledges():
    try:
        knowledges = await ManagerRAG.get_knowledges()
    except Exception as e:
        return PathListResponse(status="error", message=f"Query knowledge failed! Reason: {e}", data=[])
    return PathListResponse(status="success", data=knowledges)
    
@router.post("/knowledge/{name}")
async def create_knowledge(request: Request, name: str, 
    source: Optional[str] = Form(""),
):
    try:
        knowledge = await ManagerRAG.create_knowledge(name, source=source)
        request.app.state.rags[name] = knowledge
        knowledges = await ManagerRAG.get_knowledges()
        return PathListResponse(status="success", data=knowledges)
    except Exception as e:
        return PathListResponse(status="error", message=f"Create knowledge failed! Reason: {e}", data=[])

@router.delete("/knowledge/{name}")
async def delete_knowledge(name: str, request: Request):
    try:
        manager_rag: ManagerRAG = request.app.state.rags[name]
        await manager_rag.delete_knowledge(name)
        del request.app.state.rags[name]
        knowledges = await ManagerRAG.get_knowledges()
        return PathListResponse(status="success", data=knowledges)
    except Exception as e:
        return PathListResponse(status="error", message=f"Delete knowledge failed! Reason: {e}", data=[])

@router.get("/knowledge/model", response_model=ChatResponse)
async def get_knowledge_llm_model(knowledge: str, request: Request):
    try:
        manager_rag = request.app.state.rags[knowledge]
        model_detail: ModelDetail = await manager_rag.get_model_from_knowledge()
        return ChatResponse(
            status="success",
            message="Query successful!",
            data=model_detail.model_dump()
        )
    except Exception as e:
        return ChatResponse(
            status="error",
            message=f"Get knowledge model failed! Reason: {e}",
            data={}
        )
    

@router.get("/search-files")
async def search_files(
    knowledge:str, 
    request: Request,
    prefix: Optional[str] = None,
    filter: Optional[str] = None,
    status: Optional[str] = None,
    path: Optional[str] = None
):
    manager_rag: ManagerRAG = request.app.state.rags[knowledge]
    blacklist = ("content",)
    data = await manager_rag.search_docs(prefix=prefix, filter=filter, status=status, path=path, blacklist=blacklist)
    return {
        "status": "success",
        "message": "Query successful!",
        "data": data
    }

async def query(rag, query: str, stream: bool = True):
    async for message in rag.aquery(query, stream=stream):
        yield message

@router.get("/query-stream")
async def stream_text(
    rq: Request,
    knowledge: str, 
    str_query: str, 
    tokens_limit: Optional[int] = None,
    
):
    manager_rag: ManagerRAG = rq.app.state.rags[knowledge]
    limit_tracker = LimitTracker(
        tokens_limit=tokens_limit,
    )
    try:
        result = await manager_rag.aquery(question=str_query, stream=False, limit_tracker=limit_tracker)
        if result.get("error"):
            raise RuntimeError(result.get("error"))
    
    except Exception as e:
        return ChatResponse(
            status="error",
            data= result if result else None,
            message=f"Query failed! Reason: {e}"
        )
    
    return ChatResponse(
        status="success",
        data=result,
        message="Query successfully!"
    )


@router.post("/insert-text", response_model=ChatResponse)
async def insert_endpoint(request: InsertRequest, rq: Request):
    # print("Sanity check: Request received for insert-text")
    # print("Rags: ", rq.app.state.rags)
    manager_rag = rq.app.state.rags[request.knowledge]
    
    # Setup input 
    knowledge = request.knowledge
    if not request.custom_filename:
        raw_filename = get_default_name(knowledge)
    else:
        raw_filename = request.custom_filename
    # filename = generate_filename(knowledge, raw_filename)
    file_paths = generate_filepath(knowledge, raw_filename, request.custom_file_path)
    
    # Set up limit tracker
    limit_tracker = LimitTracker(
        tokens_limit=request.tokens_limit,
    )
    
    # Call rag to handle text
    try:
        resp: InsertResponse = await manager_rag.ainsert(
            text=request.text, filename=raw_filename, 
            file_paths=file_paths, limit_tracker=limit_tracker
        )
    except Exception as e:
        return ChatResponse(
            status="error",
            message="An error encountered while RAG inserting text!",
            data={"error": str(e)}
        )
    total_tokens_used = resp.tokens_used.get("total_tokens")
    if resp.error is None:
        status = "success"
        message = f"Text inserted successfully. Processed in {resp["time"]:.2f}. Tokens used: {total_tokens_used}"
    else:
        status = "error"
        message = f"Text inserted failed. Reason: {resp["error"]}. Processed in {resp["time"]:.2f}. Tokens used: {total_tokens_used}"
    
    return ChatResponse(
        status=status,
        message=message,
        data=resp.model_dump()
    )

@router.post("/insert-file", response_model=ChatResponse)
async def insert_file(
    knowledge:str, 
    request: Request,
    file: Optional[UploadFile] = File(None),
    file_url: Optional[str] = Form(""),
    custom_file_path: Optional[str] = Form(""),
    tokens_limit: Optional[int] = Form(None),
    use_ocr: Optional[bool] = Form(False),
    image_ops: Optional[str] = Form("grayscale,scale:factor=1"),
    languages: Optional[str] = Form("eng")
):
    manager_rag: ManagerRAG = request.app.state.rags[knowledge]
    # print("File received: ", file) # DEBUG
    # Get files from UploadFile or URL
    filename = content_type = None
    try:
        if file:
            content = await file.read()
            filename = file.filename
            content_type = file.content_type
        elif file_url:            
            # TODO: create cloud based solution for uploaded files
            raise NotImplemented("Cloud-based files are not supported at the moment!")
        else:
            raise ValueError("No file or url received!")
    except Exception as e:
        return ChatResponse(
            status="error",
            message=f"Extracing files failed!",
            data={"filename": filename, 
                  "content-type":content_type, 
                  "url": file_url, 
                  "error": str(e)
            }
        )
    
    if isinstance(content, bytes) and commons.detect_parquet_magic(content):
        ext = ".parquet"
    else:
        ext = commons.get_etx_from_content_type(content_type)
    
    print(f"content-type: {ext}")
    
    # Start OCR if enabled
    ocr_extract_time = None
    if use_ocr:
        ocr_start = time.time()
        raw_text = commons.get_text_from_stream_with_OCR(content, ext, image_ops, languages)
        ocr_extract_time = time.time() - ocr_start
    else:
        raw_text = commons.get_text_from_stream(content, ext)
    
    if isinstance(raw_text, list):
        raw_text = '\n\n'.join(raw_text)
    # print("Snippet of raw_text extracted:")
    # print(raw_text[:min(64, len(raw_text))]+'...')
    # Setup knowlege-based name and path
    # kb_filename = generate_filename(knowledge, filename)
    kb_file_paths = generate_filepath(knowledge, filename, custom_file_path)
    
    # Setup limit
    limit_tracker = LimitTracker(
        tokens_limit=tokens_limit,
    )
    
    # Let LightRAG process the files
    try:
        if isinstance(raw_text, str):
            resp: InsertResponse = await manager_rag.ainsert(
                text=raw_text, 
                filename=filename, 
                file_paths=kb_file_paths, 
                limit_tracker=limit_tracker
            )
        elif isinstance(raw_text, Generator):
            for text in raw_text:
                curr_filename = filename + text.split(';')[0]
                resp: InsertResponse = await manager_rag.ainsert(
                    text=text, 
                    filename=curr_filename, 
                    file_paths=kb_file_paths, 
                    limit_tracker=limit_tracker
                )
        else:
            raise ValueError("Unsupported raw_text type!")
    except Exception as e:
        return ChatResponse(
            status="error",
            message="An error encountered while RAG inserting texts!",
            data={"error": str(e)}
        )
    
    # Set data fields
    if ocr_extract_time is not None:
        resp.time += ocr_extract_time
    
    resp.files = {
        "filename": filename,
        "content_type": content_type,
        "size": file.size
    }
    
    # Set status and message fields
    if resp.error is None:
        status = "success"
        message = f"File content from {filename} inserted successfully."
    else:
        status = "error"
        message = f"File content from {filename} inserted failed."
    
    print(resp.model_dump())
    
    return ChatResponse(
        status=status,
        message=message,
        data=resp.model_dump()
    )

@router.post("/insert-news-url", response_model=ChatResponse)
async def insert_news_url(
    knowledge:str, 
    request: Request,
    url: Optional[str] = Form(""),
    custom_file_path: Optional[str] = Form(""),
    tokens_limit: Optional[int] = Form(None),
):
    manager_rag: ManagerRAG = request.app.state.rags[knowledge]
    # print("File received: ", file) # DEBUG
    # Get files from UploadFile or URL
    filename = content_type = None
    try:
       
        # TODO: create news-site url identifier
        if not url:
            raise ValueError("Please input an url")
        article = commons.crawl_news_from_url(url)
        if not article:
            raise RuntimeError("Unable to crawl website!")
        
        print("Content: ", article)
        filename = article.get("filename")
        maintext = article.get("maintext")
        title = article.get("title")
        date_publish = article.get("date_publish")
        date_modify = article.get("date_modify")
        
                    
    except Exception as e:
        return ChatResponse(
            status="error",
            message=f"Extracing url failed!",
            data={
                  "url": url, 
                  "error": str(e)
                }   
        )
    
    
    kb_file_paths = generate_filepath(knowledge, filename, custom_file_path)
    
    # Setup limit
    limit_tracker = LimitTracker(
        tokens_limit=tokens_limit,
    )
    
    raw_text = title + '\n' + f'{date_publish=} {date_modify=}' \
        + maintext  
    
    # Let LightRAG process the files
    try:
        resp: InsertResponse = await manager_rag.ainsert(
            text=raw_text, 
            filename=filename, 
            file_paths=kb_file_paths, 
            limit_tracker=limit_tracker
        )

    except Exception as e:
        return ChatResponse(
            status="error",
            message="An error encountered while RAG inserting texts!",
            data={"error": str(e)}
        )
    
    # Set data fields
    resp.files = {
        "filename": filename,
        "content_type": "text",
        "size": getsizeof(raw_text)
    }
    
    # Set status and message fields
    if resp.error is None:
        status = "success"
        message = f"File content from {filename} inserted successfully."
    else:
        status = "error"
        message = f"File content from {filename} inserted failed."
    
    print(resp.model_dump())
    
    return ChatResponse(
        status=status,
        message=message,
        data=resp.model_dump()
    )

@router.delete("/delete-file", response_model=ChatResponse)
async def delete_file(knowledge:str, raw_filename: str, request: Request):
    manager_rag = request.app.state.rags[knowledge]
    # filename = generate_filename(knowledge, raw_filename)
    try:     
        result = await manager_rag.adelete_by_filename(filename=raw_filename)
    except Exception as e:
        return ChatResponse(
            status="error",
            message="An error encountered while RAG deleting files!",
            data={"error": str(e)}
        )
    
    status = "success" if result.get("status") == "success" else "error"
    message = "Deletion complete!"
    return ChatResponse(
        status=status,
        message=message,
        data=result
    )

@router.get("/html_graph/{knowledge_name}", response_model=ChatResponse)
async def get_html_graph(knowledge_name: str):
    html = await ManagerRAG.gen_html_graph(knowledge_name)
    return ChatResponse(status="success", data=html)
   

@router.get("/health")
async def health_check():
    return {"status": "healthy"}

# -----------------------------
# Completion API (Streaming)
# -----------------------------

class CompletionRequest(BaseModel):
    model: str
    prompt: str
    max_tokens: Optional[int] = 16
    temperature: Optional[float] = 1.0
    stream: Optional[bool] = False  # Enable streaming


async def generate_tokens(rag: ManagerRAG, message: str, max_tokens: int):
    async for message in rag.aquery(message, stream=True):
        yield message 

@router.post("/completions")
async def create_completion(request: CompletionRequest, rq: Request):
    rag = rq.app.state.rags[request.model]
    return StreamingResponse(
        generate_tokens(rag,request.prompt, request.max_tokens), media_type="text/event-stream")
  

# -----------------------------
# Chat Completion API (Streaming)
# -----------------------------

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel): 
    model: str
    messages: list[ChatMessage]
    temperature: Optional[float] = 1.0
    stream: Optional[bool] = False  # Enable streaming

async def generate_chat_response(rag, messages):
    
    return "TODO"

@router.post("/chat/completions")
async def create_chat_completion(request: ChatCompletionRequest, rq: Request):
    
    return "TODO"

# @router.get("/read-sftp", response_class=PlainTextResponse)
# def read_sftp_file(
#     host: str = Query(...),
#     port: int = Query(22),
#     username: str = Query(...),
#     password: str = Query(...),
#     filepath: str = Query(...)
# ):
#     try:
#         ssh = paramiko.SSHClient()
#         ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#         ssh.connect(hostname=host, port=port, username=username, password=password)

#         sftp = ssh.open_sftp()
#         with sftp.open(filepath, 'rb') as file_stream:
#             content = commons.get_text_from_stream(file_stream)

#         sftp.close()
#         ssh.close()

#         return content

#     except FileNotFoundError:
#         raise HTTPException(status_code=404, detail="File not found on SFTP server")
#     except paramiko.AuthenticationException:
#         raise HTTPException(status_code=401, detail="Authentication failed")
#     except paramiko.SSHException as e:
#         raise HTTPException(status_code=500, detail=f"SSH error: {str(e)}")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
