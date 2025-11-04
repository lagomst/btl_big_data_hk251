from fastapi import FastAPI, Request, APIRouter
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager

from api.main import api_router
from core.config import settings
from core.newsrag import ManagerRAG

from core.light_rag.kg.shared_storage import initialize_share_data, initialize_pipeline_status, get_namespace_data
from core.light_rag.utils import setup_logger

def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"

WORKERS = 1

# Initialize Jinja2 templates
templates = Jinja2Templates(directory="templates")

@asynccontextmanager
async def lifespan(app: FastAPI): 
    # Code that runs on startup
    initialize_share_data()
    
    print("*** App is starting")
    print("Setting up loggers")
    setup_logger("lightrag", level="INFO")
    
    rags = await ManagerRAG.load_knowledges()
    print("Knowledges loaded: ", rags)
    # for agent in rags.values():
    #     await agent.rag.initialize_storages()
    await initialize_pipeline_status()
    status = await get_namespace_data("pipeline_status")
    print("Pipeline status: ", status)
    if "history_messages" not in status:
        status["history_messages"] = []
    app.state.rags = rags
    print("LLM_API_KEY used (suffix): " + settings.LLM_API_KEY[-4:])
    yield
    # Code that runs on shutdown
    del app.state.rags
    print("*** App is shutting down")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan
)


app.include_router(api_router, prefix=settings.API_V1_STR)
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

subapp = APIRouter()

@subapp.get("/", tags=["UI"], response_class=HTMLResponse)
async def home(request: Request):
    """Serve main UI"""
    return templates.TemplateResponse("index.html", {"request": request, "title": settings.PROJECT_NAME})

@subapp.get("/knowledge-base", tags=["UI"], response_class=HTMLResponse)
async def knowledge_base_page(request: Request):
    return templates.TemplateResponse("knowledge_base.html", {"request": request, "title": settings.PROJECT_NAME})

@subapp.get("/knowledge-base/{kb}", tags=["UI"], response_class=HTMLResponse)
async def knowledge_page(request: Request, kb: str):
    """Serve document management page for a given knowledge base"""
    return templates.TemplateResponse(
        "knowledge_detail.html",
        {"request": request, "kb": kb, "title": f"Knowledge: {kb}"}
    )

app.include_router(subapp)