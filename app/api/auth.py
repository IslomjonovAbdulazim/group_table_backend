from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from ..core.database import get_db
from ..core.auth import verify_password, create_access_token
from ..models.admin import Admin
from ..models.teacher import Teacher

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
    admin_result = await db.execute(select(Admin).filter(Admin.email == request.email))
    admin = admin_result.scalar_one_or_none()

    if admin and verify_password(request.password, admin.hashed_password):
        token = create_access_token(data={"sub": admin.id, "type": "admin"})
        return LoginResponse(access_token=token, token_type="bearer", user_type="admin")

    teacher_result = await db.execute(select(Teacher).filter(Teacher.email == request.email))
    teacher = teacher_result.scalar_one_or_none()

    if teacher and verify_password(request.password, teacher.hashed_password):
        token = create_access_token(data={"sub": teacher.id, "type": "teacher"})
        return LoginResponse(access_token=token, token_type="bearer", user_type="teacher")

    raise HTTPException(status_code=401, detail="Invalid credentials")