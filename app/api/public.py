from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
from ..core.database import get_db
from ..models.group import Group
from ..models.student import Student
from ..models.module import Module
from ..models.lesson import Lesson
from ..models.criteria import Criteria
from ..models.grade import Grade
from ..utils.calculations import calculate_student_totals
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class GroupInfo(BaseModel):
    id: int
    name: str
    code: str
    is_active: bool

    class Config:
        from_attributes = True


class ModuleInfo(BaseModel):
    id: int
    name: str
    is_active: bool
    is_finished: bool

    class Config:
        from_attributes = True


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
    """Get group information by code"""
    try:
        logger.info(f"Fetching group with code: {code}")
        result = await db.execute(
            select(Group).filter(Group.code == code.upper())
        )
        group = result.scalar_one_or_none()

        if not group:
            logger.warning(f"Group with code {code} not found")
            raise HTTPException(status_code=404, detail="Group not found")

        logger.info(f"Successfully found group: {group.name}")
        return group
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching group by code {code}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving group information")


@router.get("/{code}/modules", response_model=List[ModuleInfo])
async def get_group_modules(code: str, db: AsyncSession = Depends(get_db)):
    """Get all modules for a group by code"""
    try:
        logger.info(f"Fetching modules for group code: {code}")

        # First get the group
        group_result = await db.execute(
            select(Group).filter(Group.code == code.upper())
        )
        group = group_result.scalar_one_or_none()

        if not group:
            logger.warning(f"Group with code {code} not found")
            raise HTTPException(status_code=404, detail="Group not found")

        # Get modules for the group
        modules_result = await db.execute(
            select(Module)
            .filter(Module.group_id == group.id)
            .order_by(Module.created_at.desc())
        )
        modules = modules_result.scalars().all()

        logger.info(f"Found {len(modules)} modules for group {group.name}")
        return modules
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching modules for group {code}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving modules")


@router.get("/{code}/modules/{module_id}", response_model=List[LeaderboardEntry])
async def get_module_leaderboard(
        code: str,
        module_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Get leaderboard for a specific module"""
    try:
        logger.info(f"Fetching leaderboard for group {code}, module {module_id}")

        # Verify group exists
        group_result = await db.execute(
            select(Group).filter(Group.code == code.upper())
        )
        group = group_result.scalar_one_or_none()

        if not group:
            logger.warning(f"Group with code {code} not found")
            raise HTTPException(status_code=404, detail="Group not found")

        # Verify module belongs to group
        module_result = await db.execute(
            select(Module).filter(
                Module.id == module_id,
                Module.group_id == group.id
            )
        )
        module = module_result.scalar_one_or_none()

        if not module:
            logger.warning(f"Module {module_id} not found in group {code}")
            raise HTTPException(status_code=404, detail="Module not found")

        # Calculate leaderboard
        leaderboard = await calculate_student_totals(db, module_id)
        logger.info(f"Generated leaderboard with {len(leaderboard)} students")

        return leaderboard
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating leaderboard for module {module_id}: {e}")
        raise HTTPException(status_code=500, detail="Error generating leaderboard")


@router.get("/{code}/students/{student_id}/chart", response_model=ChartData)
async def get_student_chart(
        code: str,
        student_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Get chart data for a specific student"""
    try:
        logger.info(f"Fetching chart data for student {student_id} in group {code}")

        # Verify group exists
        group_result = await db.execute(
            select(Group).filter(Group.code == code.upper())
        )
        group = group_result.scalar_one_or_none()

        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        # Verify student belongs to group
        student_result = await db.execute(
            select(Student).filter(
                Student.id == student_id,
                Student.group_id == group.id
            )
        )
        student = student_result.scalar_one_or_none()

        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

        # TODO: Implement actual chart calculation logic
        # For now, return basic data structure
        chart_data = ChartData(
            student_name=student.full_name,
            positions=[
                {"lesson": "Start", "position": 1, "change": 0},
                {"lesson": "Current", "position": 1, "change": 0}
            ]
        )

        logger.info(f"Generated chart data for student {student.full_name}")
        return chart_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating chart for student {student_id}: {e}")
        raise HTTPException(status_code=500, detail="Error generating student chart")


@router.get("/{code}/modules/{module_id}/chart")
async def get_module_chart(
        code: str,
        module_id: int,
        db: AsyncSession = Depends(get_db)
):
    """Get chart data for a module"""
    try:
        logger.info(f"Fetching chart data for module {module_id} in group {code}")

        # Verify group exists
        group_result = await db.execute(
            select(Group).filter(Group.code == code.upper())
        )
        group = group_result.scalar_one_or_none()

        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        # Verify module belongs to group
        module_result = await db.execute(
            select(Module).filter(
                Module.id == module_id,
                Module.group_id == group.id
            )
        )
        module = module_result.scalar_one_or_none()

        if not module:
            raise HTTPException(status_code=404, detail="Module not found")

        # Get student totals for chart
        students = await calculate_student_totals(db, module_id)

        # Get lessons for the module
        lessons_result = await db.execute(
            select(Lesson)
            .filter(Lesson.module_id == module_id)
            .order_by(Lesson.lesson_number)
        )
        lessons = lessons_result.scalars().all()

        chart_data = {
            "module_name": module.name,
            "students": students,
            "lessons": [f"Lesson {l.lesson_number}" for l in lessons] or ["No lessons yet"]
        }

        logger.info(f"Generated chart data for module {module.name}")
        return chart_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating module chart for {module_id}: {e}")
        raise HTTPException(status_code=500, detail="Error generating module chart")


@router.get("/{code}/stats")
async def get_group_stats(code: str, db: AsyncSession = Depends(get_db)):
    """Get statistics for a group"""
    try:
        logger.info(f"Fetching stats for group {code}")

        # Verify group exists
        group_result = await db.execute(
            select(Group).filter(Group.code == code.upper())
        )
        group = group_result.scalar_one_or_none()

        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        # Count students
        students_result = await db.execute(
            select(Student).filter(Student.group_id == group.id)
        )
        students_count = len(students_result.scalars().all())

        # Count modules
        modules_result = await db.execute(
            select(Module).filter(Module.group_id == group.id)
        )
        modules = modules_result.scalars().all()
        modules_count = len(modules)
        active_modules_count = len([m for m in modules if m.is_active])

        # Count total lessons
        lessons_count = 0
        if modules:
            for module in modules:
                lessons_result = await db.execute(
                    select(Lesson).filter(Lesson.module_id == module.id)
                )
                lessons_count += len(lessons_result.scalars().all())

        stats = {
            "group_name": group.name,
            "group_code": group.code,
            "is_active": group.is_active,
            "students_count": students_count,
            "modules_count": modules_count,
            "active_modules_count": active_modules_count,
            "total_lessons": lessons_count
        }

        logger.info(f"Generated stats for group {group.name}")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating stats for group {code}: {e}")
        raise HTTPException(status_code=500, detail="Error generating group statistics")