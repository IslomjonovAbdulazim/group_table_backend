from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List
from ..core.database import get_db
from ..models.group import Group
from ..models.student import Student
from ..models.module import Module
from ..utils.calculations import calculate_student_totals

router = APIRouter()


class GroupInfo(BaseModel):
    id: int
    name: str
    code: str


class ModuleInfo(BaseModel):
    id: int
    name: str


class LeaderboardEntry(BaseModel):
    student_id: int
    name: str
    total_points: int
    position: int


class ChartData(BaseModel):
    student_name: str
    positions: List[dict]


@router.get("/{code}", response_model=GroupInfo)
async def get_group_by_code(code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Group).filter(Group.code == code))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


@router.get("/{code}/modules", response_model=List[ModuleInfo])
async def get_group_modules(code: str, db: AsyncSession = Depends(get_db)):
    group_result = await db.execute(select(Group).filter(Group.code == code))
    group = group_result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    result = await db.execute(select(Module).filter(Module.group_id == group.id))
    return result.scalars().all()


@router.get("/{code}/modules/{module_id}", response_model=List[LeaderboardEntry])
async def get_module_leaderboard(code: str, module_id: int, db: AsyncSession = Depends(get_db)):
    group_result = await db.execute(select(Group).filter(Group.code == code))
    group = group_result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    module_result = await db.execute(select(Module).filter(Module.id == module_id, Module.group_id == group.id))
    if not module_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Module not found")

    return await calculate_student_totals(db, module_id)


@router.get("/{code}/students/{student_id}/chart", response_model=ChartData)
async def get_student_chart(code: str, student_id: int, db: AsyncSession = Depends(get_db)):
    group_result = await db.execute(select(Group).filter(Group.code == code))
    group = group_result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    student_result = await db.execute(select(Student).filter(Student.id == student_id, Student.group_id == group.id))
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return ChartData(
        student_name=student.full_name,
        positions=[{"lesson": "Start", "position": 1, "change": 0}]
    )


@router.get("/{code}/modules/{module_id}/chart")
async def get_module_chart(code: str, module_id: int, db: AsyncSession = Depends(get_db)):
    group_result = await db.execute(select(Group).filter(Group.code == code))
    group = group_result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    module_result = await db.execute(select(Module).filter(Module.id == module_id, Module.group_id == group.id))
    if not module_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Module not found")

    students = await calculate_student_totals(db, module_id)
    return {
        "module_name": "Module Chart",
        "students": students,
        "lessons": ["Start", "Lesson 1", "Lesson 2"]
    }