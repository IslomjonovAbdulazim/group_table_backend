from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from ..core.database import get_db
from ..core.auth import verify_password, create_access_token, get_password_hash, verify_token
from ..models.admin import Admin
from ..models.teacher import Teacher
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user_type: str
    user_id: int
    user_name: str


class RegisterAdminRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user (admin or teacher) and return access token
    """
    try:
        logger.info(f"Login attempt for email: {request.email}")

        # Check admin first
        admin_result = await db.execute(
            select(Admin).filter(Admin.email == request.email.lower())
        )
        admin = admin_result.scalar_one_or_none()

        if admin and verify_password(request.password, admin.hashed_password):
            logger.info(f"Admin login successful: {admin.email}")
            token = create_access_token(data={"sub": admin.id, "type": "admin"})
            return LoginResponse(
                access_token=token,
                token_type="bearer",
                user_type="admin",
                user_id=admin.id,
                user_name=admin.name
            )

        # Check teacher
        teacher_result = await db.execute(
            select(Teacher).filter(Teacher.email == request.email.lower())
        )
        teacher = teacher_result.scalar_one_or_none()

        if teacher and verify_password(request.password, teacher.hashed_password):
            logger.info(f"Teacher login successful: {teacher.email}")
            token = create_access_token(data={"sub": teacher.id, "type": "teacher"})
            return LoginResponse(
                access_token=token,
                token_type="bearer",
                user_type="teacher",
                user_id=teacher.id,
                user_name=teacher.name
            )

        logger.warning(f"Failed login attempt for email: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error for {request.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


@router.post("/register-admin", response_model=LoginResponse)
async def register_admin(request: RegisterAdminRequest, db: AsyncSession = Depends(get_db)):
    """
    Register the first admin user (only if no admins exist)
    """
    try:
        logger.info(f"Admin registration attempt for email: {request.email}")

        # Check if any admin already exists
        existing_admin_result = await db.execute(select(Admin))
        existing_admin = existing_admin_result.scalar_one_or_none()

        if existing_admin:
            logger.warning("Admin registration attempted but admin already exists")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin user already exists"
            )

        # Check if email is already used by teacher
        existing_teacher_result = await db.execute(
            select(Teacher).filter(Teacher.email == request.email.lower())
        )
        existing_teacher = existing_teacher_result.scalar_one_or_none()

        if existing_teacher:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # Create new admin
        hashed_password = get_password_hash(request.password)
        new_admin = Admin(
            name=request.name,
            email=request.email.lower(),
            hashed_password=hashed_password
        )

        db.add(new_admin)
        await db.commit()
        await db.refresh(new_admin)

        logger.info(f"Admin registered successfully: {new_admin.email}")

        # Create token and return response
        token = create_access_token(data={"sub": new_admin.id, "type": "admin"})
        return LoginResponse(
            access_token=token,
            token_type="bearer",
            user_type="admin",
            user_id=new_admin.id,
            user_name=new_admin.name
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin registration error for {request.email}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.get("/check-admin-exists")
async def check_admin_exists(db: AsyncSession = Depends(get_db)):
    """
    Check if any admin user exists in the system
    """
    try:
        admin_result = await db.execute(select(Admin))
        admin_exists = admin_result.scalar_one_or_none() is not None

        return {"admin_exists": admin_exists}

    except Exception as e:
        logger.error(f"Error checking admin existence: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not check admin status"
        )


@router.post("/logout")
async def logout():
    """
    Logout endpoint (client-side token removal)
    """
    return {"message": "Logged out successfully"}


@router.get("/me")
async def get_current_user(token_data: dict = Depends(verify_token), db: AsyncSession = Depends(get_db)):
    """
    Get current user information
    """
    try:
        user_id = token_data["user_id"]
        user_type = token_data["user_type"]

        if user_type == "admin":
            result = await db.execute(select(Admin).filter(Admin.id == user_id))
            user = result.scalar_one_or_none()
        else:
            result = await db.execute(select(Teacher).filter(Teacher.id == user_id))
            user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "user_type": user_type
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not get user information"
        )