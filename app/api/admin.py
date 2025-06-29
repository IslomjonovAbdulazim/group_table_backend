from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import List
from ..core.database import get_db
from ..core.auth import get_password_hash, require_admin, verify_password
from ..models.admin import Admin
from ..models.teacher import Teacher
from ..models.group import Group
from ..models.student import Student
from ..models.module import Module
from ..models.lesson import Lesson
from ..models.grade import Grade
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class TeacherCreate(BaseModel):
    name: str
    email: str
    password: str


class TeacherUpdate(BaseModel):
    name: str
    email: str


class TeacherResponse(BaseModel):
    id: int
    name: str
    email: str


class TeacherStats(BaseModel):
    groups: int
    students: int
    modules: int
    lessons: int
    total_grades: int


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class TeacherPasswordChange(BaseModel):
    new_password: str


@router.get("/teachers", response_model=List[TeacherResponse])
async def get_teachers(db: AsyncSession = Depends(get_db), admin_id: int = Depends(require_admin)):
    try:
        result = await db.execute(select(Teacher).filter(Teacher.admin_id == admin_id))
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Error getting teachers: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving teachers")


@router.post("/teachers", response_model=TeacherResponse)
async def create_teacher(teacher: TeacherCreate, db: AsyncSession = Depends(get_db),
                         admin_id: int = Depends(require_admin)):
    try:
        existing_teacher = await db.execute(select(Teacher).filter(Teacher.email == teacher.email))
        if existing_teacher.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")

        hashed_password = get_password_hash(teacher.password)
        db_teacher = Teacher(
            name=teacher.name,
            email=teacher.email,
            hashed_password=hashed_password,
            admin_id=admin_id
        )
        db.add(db_teacher)
        await db.commit()
        await db.refresh(db_teacher)
        return db_teacher
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating teacher: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error creating teacher")


@router.put("/teachers/{teacher_id}", response_model=TeacherResponse)
async def update_teacher(teacher_id: int, teacher: TeacherUpdate, db: AsyncSession = Depends(get_db),
                         admin_id: int = Depends(require_admin)):
    try:
        result = await db.execute(select(Teacher).filter(Teacher.id == teacher_id, Teacher.admin_id == admin_id))
        db_teacher = result.scalar_one_or_none()
        if not db_teacher:
            raise HTTPException(status_code=404, detail="Teacher not found")

        if teacher.email != db_teacher.email:
            existing_teacher = await db.execute(select(Teacher).filter(Teacher.email == teacher.email))
            if existing_teacher.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Email already registered")

        db_teacher.name = teacher.name
        db_teacher.email = teacher.email
        await db.commit()
        await db.refresh(db_teacher)
        return db_teacher
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating teacher: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error updating teacher")


@router.delete("/teachers/{teacher_id}")
async def delete_teacher(teacher_id: int, db: AsyncSession = Depends(get_db),
                         admin_id: int = Depends(require_admin)):
    try:
        result = await db.execute(select(Teacher).filter(Teacher.id == teacher_id, Teacher.admin_id == admin_id))
        db_teacher = result.scalar_one_or_none()
        if not db_teacher:
            raise HTTPException(status_code=404, detail="Teacher not found")

        await db.delete(db_teacher)
        await db.commit()
        return {"message": "Teacher deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting teacher: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error deleting teacher")


@router.get("/teachers/{teacher_id}/stats", response_model=TeacherStats)
async def get_teacher_stats(teacher_id: int, db: AsyncSession = Depends(get_db),
                            admin_id: int = Depends(require_admin)):
    try:
        teacher_result = await db.execute(
            select(Teacher).filter(Teacher.id == teacher_id, Teacher.admin_id == admin_id))
        teacher = teacher_result.scalar_one_or_none()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found")

        groups_count = await db.execute(select(func.count(Group.id)).filter(Group.teacher_id == teacher_id))

        students_count = await db.execute(
            select(func.count(Student.id))
            .join(Group, Student.group_id == Group.id)
            .filter(Group.teacher_id == teacher_id)
        )

        modules_count = await db.execute(
            select(func.count(Module.id))
            .join(Group, Module.group_id == Group.id)
            .filter(Group.teacher_id == teacher_id)
        )

        lessons_count = await db.execute(
            select(func.count(Lesson.id))
            .join(Module, Lesson.module_id == Module.id)
            .join(Group, Module.group_id == Group.id)
            .filter(Group.teacher_id == teacher_id)
        )

        grades_count = await db.execute(
            select(func.count(Grade.id))
            .join(Student, Grade.student_id == Student.id)
            .join(Group, Student.group_id == Group.id)
            .filter(Group.teacher_id == teacher_id)
        )

        return TeacherStats(
            groups=groups_count.scalar() or 0,
            students=students_count.scalar() or 0,
            modules=modules_count.scalar() or 0,
            lessons=lessons_count.scalar() or 0,
            total_grades=grades_count.scalar() or 0
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting teacher stats: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving teacher statistics")


# Password management
@router.post("/change-password")
async def change_admin_password(password_data: PasswordChange, db: AsyncSession = Depends(get_db),
                               admin_id: int = Depends(require_admin)):
    try:
        result = await db.execute(select(Admin).filter(Admin.id == admin_id))
        admin = result.scalar_one_or_none()
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")

        if not verify_password(password_data.current_password, admin.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

        admin.hashed_password = get_password_hash(password_data.new_password)
        await db.commit()
        return {"message": "Admin password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing admin password: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error changing admin password")


@router.post("/teachers/{teacher_id}/change-password")
async def change_teacher_password(teacher_id: int, password_data: TeacherPasswordChange,
                                 db: AsyncSession = Depends(get_db),
                                 admin_id: int = Depends(require_admin)):
    try:
        result = await db.execute(select(Teacher).filter(Teacher.id == teacher_id, Teacher.admin_id == admin_id))
        teacher = result.scalar_one_or_none()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found")

        teacher.hashed_password = get_password_hash(password_data.new_password)
        await db.commit()
        return {"message": "Teacher password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing teacher password: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error changing teacher password")