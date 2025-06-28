from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.database import create_tables
from .api import auth, admin, teacher, public

app = FastAPI(title="GroupTable API", version="1.0.0")

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

@app.on_event("startup")
async def startup_event():
    await create_tables()

@app.get("/")
async def root():
    return {"message": "GroupTable API is running"}