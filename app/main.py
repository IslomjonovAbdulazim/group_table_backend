# Replace app/main.py with this improved version:

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .core.database import create_tables, close_db
from .api import auth, admin, teacher, public
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting application...")
    try:
        await create_tables()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down application...")
    try:
        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}")


app = FastAPI(
    title="GroupTable API",
    version="1.0.0",
    lifespan=lifespan,
    description="API for GroupTable - Educational Management System"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(teacher.router, tags=["teacher"])
app.include_router(public.router, prefix="/public", tags=["public"])


@app.get("/")
async def root():
    return {"message": "GroupTable API is running", "status": "healthy"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}