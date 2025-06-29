from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .core.database import create_tables
from .api import auth, admin, teacher, public
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")
    await create_tables()
    logger.info("Database tables created")
    yield
    logger.info("Shutting down application...")

app = FastAPI(title="GroupTable API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(teacher.router, tags=["teacher"])
app.include_router(public.router, tags=["public"])

@app.get("/")
async def root():
    return {"message": "GroupTable API is running"}