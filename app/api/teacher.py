from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import List, Optional
from ..core.database import get_db
from ..core.auth import require_teacher
from ..models.group import Group
from ..models.student import Student
from ..models.module import Module
from ..models.lesson import Lesson
from ..models.criteria import Criteria, GradingMethod
from ..models.grade import Grade
from ..utils.code_generator import generate_group_code
from ..utils.calculations import calculate_student_totals
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class GroupCreate(BaseModel):
    name: str


class GroupResponse(BaseModel):
    id: int
    name: str
    code: str
    is_active: bool


class StudentCreate(BaseModel):
    full_name: str


class StudentResponse(BaseModel):
    id: int
    full_name: str


class ModuleCreate(BaseModel):
    name: str


class ModuleResponse(BaseModel):
    id: int
    name: str
    is_active: bool
    is_finished: bool


class LessonCreate(BaseModel):
    name: str


class LessonResponse(BaseModel):
    id: int
    name: str
    lesson_number: int


class CriteriaCreate(BaseModel):
    name: str
    max_points: int
    grading_method: str


class CriteriaResponse(BaseModel):
    id: int
    name: str
    max_points: int
    grading_method: str


class GradeCreate(BaseModel):
    points_earned: int
    student_id: int
    criteria_id: int
    lesson_id: int


class GradeResponse(BaseModel):
    id: int
    points_earned: int
    student_id: int
    criteria_id: int
    lesson_id: int


# Groups
@router.get("/groups", response_model=List[GroupResponse])
async def get_groups(db: AsyncSession = Depends(get_db), teacher_id: int = Depends(require_teacher)):
    logger.info(f"Getting groups for teacher_id: {teacher_id}")

    try:
        result = await db.execute(select(Group).filter(Group.teacher_id == teacher_id))
        groups = result.scalars().all()
        logger.info(f"Found {len(groups)} groups")
        return groups
    except Exception as e:
        logger.error(f"Error getting groups: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving groups")


@router.post("/groups", response_model=GroupResponse)
async def create_group(group: GroupCreate, db: AsyncSession = Depends(get_db),
                       teacher_id: int = Depends(require_teacher)):
    logger.info(f"Creating group '{group.name}' for teacher_id: {teacher_id}")

    try:
        # Check group limit
        groups_count = await db.execute(
            select(func.count(Group.id)).filter(Group.teacher_id == teacher_id, Group.is_active == True))
        if groups_count.scalar() >= 6:
            raise HTTPException(status_code=400, detail="Maximum 6 active groups allowed")

        # Generate unique code
        code = generate_group_code()
        while True:
            existing_group = await db.execute(select(Group).filter(Group.code == code))
            if not existing_group.scalar_one_or_none():
                break
            code = generate_group_code()

        db_group = Group(name=group.name, code=code, teacher_id=teacher_id)
        db.add(db_group)
        await db.commit()
        await db.refresh(db_group)

        logger.info(f"Group created with id: {db_group.id}, code: {code}")
        return db_group
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating group: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error creating group")


@router.delete("/groups/{group_id}")
async def delete_group(group_id: int, db: AsyncSession = Depends(get_db),
                       teacher_id: int = Depends(require_teacher)):
    logger.info(f"Deleting group {group_id} for teacher_id: {teacher_id}")

    try:
        result = await db.execute(select(Group).filter(Group.id == group_id, Group.teacher_id == teacher_id))
        db_group = result.scalar_one_or_none()
        if not db_group:
            raise HTTPException(status_code=404, detail="Group not found")

        await db.delete(db_group)
        await db.commit()

        logger.info(f"Group {group_id} deleted successfully")
        return {"message": "Group deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting group: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error deleting group")


@router.post("/groups/{group_id}/finish")
async def finish_group(group_id: int, db: AsyncSession = Depends(get_db),
                       teacher_id: int = Depends(require_teacher)):
    logger.info(f"Finishing group {group_id} for teacher_id: {teacher_id}")

    try:
        result = await db.execute(select(Group).filter(Group.id == group_id, Group.teacher_id == teacher_id))
        db_group = result.scalar_one_or_none()
        if not db_group:
            raise HTTPException(status_code=404, detail="Group not found")

        db_group.is_active = False
        await db.commit()

        logger.info(f"Group {group_id} finished successfully")
        return {"message": "Group finished"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finishing group: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error finishing group")


# Students
@router.get("/groups/{group_id}/students", response_model=List[StudentResponse])
async def get_students(group_id: int, db: AsyncSession = Depends(get_db),
                       teacher_id: int = Depends(require_teacher)):
    logger.info(f"Getting students for group {group_id}, teacher_id: {teacher_id}")

    try:
        # Verify group ownership
        group_result = await db.execute(select(Group).filter(Group.id == group_id, Group.teacher_id == teacher_id))
        if not group_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Group not found")

        result = await db.execute(select(Student).filter(Student.group_id == group_id))
        students = result.scalars().all()
        logger.info(f"Found {len(students)} students")
        return students
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting students: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving students")


@router.post("/groups/{group_id}/students", response_model=StudentResponse)
async def create_student(group_id: int, student: StudentCreate, db: AsyncSession = Depends(get_db),
                         teacher_id: int = Depends(require_teacher)):
    logger.info(f"Creating student '{student.full_name}' in group {group_id}")

    try:
        # Verify group ownership
        group_result = await db.execute(select(Group).filter(Group.id == group_id, Group.teacher_id == teacher_id))
        if not group_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Group not found")

        # Check student limit
        students_count = await db.execute(select(func.count(Student.id)).filter(Student.group_id == group_id))
        if students_count.scalar() >= 30:
            raise HTTPException(status_code=400, detail="Maximum 30 students allowed per group")

        db_student = Student(full_name=student.full_name, group_id=group_id)
        db.add(db_student)
        await db.commit()
        await db.refresh(db_student)

        logger.info(f"Student created with id: {db_student.id}")
        return db_student
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating student: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error creating student")


@router.delete("/students/{student_id}")
async def delete_student(student_id: int, db: AsyncSession = Depends(get_db),
                         teacher_id: int = Depends(require_teacher)):
    logger.info(f"Deleting student {student_id} for teacher_id: {teacher_id}")

    try:
        result = await db.execute(
            select(Student)
            .join(Group, Student.group_id == Group.id)
            .filter(Student.id == student_id, Group.teacher_id == teacher_id)
        )
        db_student = result.scalar_one_or_none()
        if not db_student:
            raise HTTPException(status_code=404, detail="Student not found")

        await db.delete(db_student)
        await db.commit()

        logger.info(f"Student {student_id} deleted successfully")
        return {"message": "Student deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting student: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error deleting student")


# Modules
@router.get("/groups/{group_id}/modules", response_model=List[ModuleResponse])
async def get_modules(group_id: int, db: AsyncSession = Depends(get_db),
                      teacher_id: int = Depends(require_teacher)):
    logger.info(f"Getting modules for group {group_id}, teacher_id: {teacher_id}")

    try:
        # Verify group ownership
        group_result = await db.execute(select(Group).filter(Group.id == group_id, Group.teacher_id == teacher_id))
        if not group_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Group not found")

        result = await db.execute(select(Module).filter(Module.group_id == group_id))
        modules = result.scalars().all()
        logger.info(f"Found {len(modules)} modules")
        return modules
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting modules: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving modules")


@router.post("/groups/{group_id}/modules", response_model=ModuleResponse)
async def create_module(group_id: int, module: ModuleCreate, db: AsyncSession = Depends(get_db),
                        teacher_id: int = Depends(require_teacher)):
    logger.info(f"Creating module '{module.name}' in group {group_id}")

    try:
        # Verify group ownership
        group_result = await db.execute(select(Group).filter(Group.id == group_id, Group.teacher_id == teacher_id))
        if not group_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Group not found")

        # Check for active module
        active_module = await db.execute(select(Module).filter(Module.group_id == group_id, Module.is_active == True))
        if active_module.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Only one active module allowed per group")

        db_module = Module(name=module.name, group_id=group_id)
        db.add(db_module)
        await db.commit()
        await db.refresh(db_module)

        logger.info(f"Module created with id: {db_module.id}")
        return db_module
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating module: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error creating module")


@router.post("/modules/{module_id}/finish")
async def finish_module(module_id: int, db: AsyncSession = Depends(get_db),
                        teacher_id: int = Depends(require_teacher)):
    logger.info(f"Finishing module {module_id} for teacher_id: {teacher_id}")

    try:
        result = await db.execute(
            select(Module)
            .join(Group, Module.group_id == Group.id)
            .filter(Module.id == module_id, Group.teacher_id == teacher_id)
        )
        db_module = result.scalar_one_or_none()
        if not db_module:
            raise HTTPException(status_code=404, detail="Module not found")

        db_module.is_active = False
        db_module.is_finished = True
        await db.commit()

        logger.info(f"Module {module_id} finished successfully")
        return {"message": "Module finished"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finishing module: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error finishing module")


# Lessons
@router.get("/modules/{module_id}/lessons", response_model=List[LessonResponse])
async def get_lessons(module_id: int, db: AsyncSession = Depends(get_db),
                      teacher_id: int = Depends(require_teacher)):
    logger.info(f"Getting lessons for module {module_id}, teacher_id: {teacher_id}")

    try:
        # Verify module ownership
        module_result = await db.execute(
            select(Module)
            .join(Group, Module.group_id == Group.id)
            .filter(Module.id == module_id, Group.teacher_id == teacher_id)
        )
        if not module_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Module not found")

        result = await db.execute(select(Lesson).filter(Lesson.module_id == module_id))
        lessons = result.scalars().all()
        logger.info(f"Found {len(lessons)} lessons")
        return lessons
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting lessons: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving lessons")


@router.post("/modules/{module_id}/lessons", response_model=LessonResponse)
async def create_lesson(module_id: int, lesson: LessonCreate, db: AsyncSession = Depends(get_db),
                        teacher_id: int = Depends(require_teacher)):
    logger.info(f"Creating lesson '{lesson.name}' in module {module_id}")

    try:
        # Verify module ownership and active status
        module_result = await db.execute(
            select(Module)
            .join(Group, Module.group_id == Group.id)
            .filter(Module.id == module_id, Group.teacher_id == teacher_id, Module.is_active == True)
        )
        if not module_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Active module not found")

        # Check lesson limit
        lessons_count = await db.execute(select(func.count(Lesson.id)).filter(Lesson.module_id == module_id))
        if lessons_count.scalar() >= 15:
            raise HTTPException(status_code=400, detail="Maximum 15 lessons allowed per module")

        lesson_number = lessons_count.scalar() + 1
        db_lesson = Lesson(name=lesson.name, lesson_number=lesson_number, module_id=module_id)
        db.add(db_lesson)
        await db.commit()
        await db.refresh(db_lesson)

        logger.info(f"Lesson created with id: {db_lesson.id}, number: {lesson_number}")
        return db_lesson
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating lesson: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error creating lesson")


# Criteria
@router.get("/modules/{module_id}/criteria", response_model=List[CriteriaResponse])
async def get_criteria(module_id: int, db: AsyncSession = Depends(get_db),
                       teacher_id: int = Depends(require_teacher)):
    logger.info(f"Getting criteria for module {module_id}, teacher_id: {teacher_id}")

    try:
        # Verify module ownership
        module_result = await db.execute(
            select(Module)
            .join(Group, Module.group_id == Group.id)
            .filter(Module.id == module_id, Group.teacher_id == teacher_id)
        )
        if not module_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Module not found")

        result = await db.execute(select(Criteria).filter(Criteria.module_id == module_id))
        criteria = result.scalars().all()
        logger.info(f"Found {len(criteria)} criteria")
        return criteria
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting criteria: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving criteria")


@router.post("/modules/{module_id}/criteria", response_model=CriteriaResponse)
async def create_criteria(module_id: int, criteria: CriteriaCreate, db: AsyncSession = Depends(get_db),
                          teacher_id: int = Depends(require_teacher)):
    logger.info(f"Creating criteria '{criteria.name}' in module {module_id}")

    try:
        # Verify module ownership and active status
        module_result = await db.execute(
            select(Module)
            .join(Group, Module.group_id == Group.id)
            .filter(Module.id == module_id, Group.teacher_id == teacher_id, Module.is_active == True)
        )
        if not module_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Active module not found")

        # Check criteria limit
        criteria_count = await db.execute(select(func.count(Criteria.id)).filter(Criteria.module_id == module_id))
        if criteria_count.scalar() >= 6:
            raise HTTPException(status_code=400, detail="Maximum 6 criteria allowed per module")

        # Validate grading method
        try:
            grading_method = GradingMethod(criteria.grading_method)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid grading method")

        db_criteria = Criteria(
            name=criteria.name,
            max_points=criteria.max_points,
            grading_method=grading_method,
            module_id=module_id
        )
        db.add(db_criteria)
        await db.commit()
        await db.refresh(db_criteria)

        logger.info(f"Criteria created with id: {db_criteria.id}")
        return db_criteria
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating criteria: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error creating criteria")


# Grades
@router.post("/grades", response_model=GradeResponse)
async def create_grade(grade: GradeCreate, db: AsyncSession = Depends(get_db),
                       teacher_id: int = Depends(require_teacher)):
    logger.info(f"Creating/updating grade for teacher_id: {teacher_id}")

    try:
        # Verify lesson ownership and module active status
        lesson_result = await db.execute(
            select(Lesson)
            .join(Module, Lesson.module_id == Module.id)
            .join(Group, Module.group_id == Group.id)
            .filter(Lesson.id == grade.lesson_id, Group.teacher_id == teacher_id, Module.is_active == True)
        )
        if not lesson_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Lesson not found or module not active")

        # Check if grade already exists
        existing_grade = await db.execute(
            select(Grade).filter(
                Grade.student_id == grade.student_id,
                Grade.criteria_id == grade.criteria_id,
                Grade.lesson_id == grade.lesson_id
            )
        )

        db_grade = existing_grade.scalar_one_or_none()
        if db_grade:
            # Update existing grade
            db_grade.points_earned = grade.points_earned
            logger.info(f"Updated existing grade id: {db_grade.id}")
        else:
            # Create new grade
            db_grade = Grade(**grade.dict())
            db.add(db_grade)
            logger.info("Created new grade")

        await db.commit()
        await db.refresh(db_grade)
        return db_grade
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating/updating grade: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error processing grade")


@router.get("/modules/{module_id}/leaderboard")
async def get_leaderboard(module_id: int, db: AsyncSession = Depends(get_db),
                          teacher_id: int = Depends(require_teacher)):
    logger.info(f"Getting leaderboard for module {module_id}, teacher_id: {teacher_id}")

    try:
        # Verify module ownership
        module_result = await db.execute(
            select(Module)
            .join(Group, Module.group_id == Group.id)
            .filter(Module.id == module_id, Group.teacher_id == teacher_id)
        )
        if not module_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Module not found")

        leaderboard = await calculate_student_totals(db, module_id)
        logger.info(f"Generated leaderboard with {len(leaderboard)} entries")
        return leaderboard
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        raise HTTPException(status_code=500, detail="Error generating leaderboard")