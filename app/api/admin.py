from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import List
from ..core.database import get_db
from ..core.auth import get_password_hash, verify_token
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


def require_admin(token_data: dict = Depends(verify_token)):
    logger.info(f"Admin check - received token_data: {token_data}")
    logger.info(
        f"Token data types - user_id: {type(token_data.get('user_id'))}, user_type: {type(token_data.get('user_type'))}")

    if token_data["user_type"] != "admin":
        logger.error(f"Access denied - user_type is {token_data['user_type']}, expected 'admin'")
        raise HTTPException(status_code=403, detail="Admin access required")

    user_id = token_data["user_id"]
    if isinstance(user_id, str):
        logger.warning(f"user_id is string '{user_id}', converting to int")
        user_id = int(user_id)

    logger.info(f"Admin access granted for user_id: {user_id} (type: {type(user_id)})")
    return user_id


@router.get("/teachers", response_model=List[TeacherResponse])
async def get_teachers(db: AsyncSession = Depends(get_db), admin_id: int = Depends(require_admin)):
    logger.info(f"Getting teachers for admin_id: {admin_id}, type: {type(admin_id)}")
    admin_id = int(admin_id) if isinstance(admin_id, str) else admin_id
    logger.info(f"After conversion - admin_id: {admin_id}, type: {type(admin_id)}")
    result = await db.execute(select(Teacher).filter(Teacher.admin_id == admin_id))
    teachers = result.scalars().all()
    logger.info(f"Found {len(teachers)} teachers")
    return teachers


@router.post("/teachers", response_model=TeacherResponse)
async def create_teacher(teacher: TeacherCreate, db: AsyncSession = Depends(get_db),
                         admin_id: int = Depends(require_admin)):
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


@router.put("/teachers/{teacher_id}", response_model=TeacherResponse)
async def update_teacher(teacher_id: int, teacher: TeacherUpdate, db: AsyncSession = Depends(get_db),
                         admin_id: int = Depends(require_admin)):
    result = await db.execute(select(Teacher).filter(Teacher.id == teacher_id, Teacher.admin_id == admin_id))
    db_teacher = result.scalar_one_or_none()
    if not db_teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    db_teacher.name = teacher.name
    db_teacher.email = teacher.email
    await db.commit()
    await db.refresh(db_teacher)
    return db_teacher


@router.delete("/teachers/{teacher_id}")
async def delete_teacher(teacher_id: int, db: AsyncSession = Depends(get_db), admin_id: int = Depends(require_admin)):
    result = await db.execute(select(Teacher).filter(Teacher.id == teacher_id, Teacher.admin_id == admin_id))
    db_teacher = result.scalar_one_or_none()
    if not db_teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    await db.delete(db_teacher)
    await db.commit()
    return {"message": "Teacher deleted"}


@router.get("/teachers/{teacher_id}/stats", response_model=TeacherStats)
async def get_teacher_stats(teacher_id: int, db: AsyncSession = Depends(get_db),
                            admin_id: int = Depends(require_admin)):
    teacher_result = await db.execute(select(Teacher).filter(Teacher.id == teacher_id, Teacher.admin_id == admin_id))
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


@router.post("/teachers", response_model=TeacherResponse)
async def create_teacher(teacher: TeacherCreate, db: AsyncSession = Depends(get_db),
                         admin_id: int = Depends(require_admin)):
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


@router.put("/teachers/{teacher_id}", response_model=TeacherResponse)
async def update_teacher(teacher_id: int, teacher: TeacherUpdate, db: AsyncSession = Depends(get_db),
                         admin_id: int = Depends(require_admin)):
    result = await db.execute(select(Teacher).filter(Teacher.id == teacher_id, Teacher.admin_id == admin_id))
    db_teacher = result.scalar_one_or_none()
    if not db_teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    db_teacher.name = teacher.name
    db_teacher.email = teacher.email
    await db.commit()
    await db.refresh(db_teacher)
    return db_teacher


@router.delete("/teachers/{teacher_id}")
async def delete_teacher(teacher_id: int, db: AsyncSession = Depends(get_db), admin_id: int = Depends(require_admin)):
    result = await db.execute(select(Teacher).filter(Teacher.id == teacher_id, Teacher.admin_id == admin_id))
    db_teacher = result.scalar_one_or_none()
    if not db_teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    await db.delete(db_teacher)
    await db.commit()
    return {"message": "Teacher deleted"}


@router.get("/teachers/{teacher_id}/stats", response_model=TeacherStats)
async def get_teacher_stats(teacher_id: int, db: AsyncSession = Depends(get_db),
                            admin_id: int = Depends(require_admin)):
    teacher_result = await db.execute(select(Teacher).filter(Teacher.id == teacher_id, Teacher.admin_id == admin_id))
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