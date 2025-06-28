from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from ..core.database import get_db
from ..core.auth import verify_password, create_access_token
from ..models.admin import Admin
from ..models.teacher import Teacher
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user_type: str

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    logger.info(f"Login attempt for email: {request.email}")

    admin_result = await db.execute(select(Admin).filter(Admin.email == request.email))
    admin = admin_result.scalar_one_or_none()

    if admin:
        logger.info(f"Found admin with id: {admin.id}")
        if verify_password(request.password, admin.hashed_password):
            logger.info("Admin password verified, creating token")
            token = create_access_token(data={"sub": admin.id, "type": "admin"})
            logger.info(f"Admin login successful, returning token")
            return LoginResponse(access_token=token, token_type="bearer", user_type="admin")
        else:
            logger.warning("Admin password verification failed")

    teacher_result = await db.execute(select(Teacher).filter(Teacher.email == request.email))
    teacher = teacher_result.scalar_one_or_none()

    if teacher:
        logger.info(f"Found teacher with id: {teacher.id}")
        if verify_password(request.password, teacher.hashed_password):
            logger.info("Teacher password verified, creating token")
            token = create_access_token(data={"sub": teacher.id, "type": "teacher"})
            logger.info(f"Teacher login successful, returning token")
            return LoginResponse(access_token=token, token_type="bearer", user_type="teacher")
        else:
            logger.warning("Teacher password verification failed")

    logger.error(f"Invalid credentials for email: {request.email}")
    raise HTTPException(status_code=401, detail="Invalid credentials")