from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from pydantic import BaseModel
from typing import List, Optional
from ..core.database import get_db
from ..core.auth import require_teacher, get_password_hash, verify_password
from ..models.group import Group
from ..models.student import Student
from ..models.module import Module
from ..models.lesson import Lesson
from ..models.criteria import Criteria, GradingMethod
from ..models.grade import Grade
from ..models.teacher import Teacher
from ..utils.code_generator import generate_group_code
from ..utils.calculations import calculate_student_totals
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# Request/Response Models
class GroupCreate(BaseModel):
    name: str


class GroupUpdate(BaseModel):
    name: str


class GroupResponse(BaseModel):
    id: int
    name: str
    code: str
    is_active: bool


class StudentCreate(BaseModel):
    full_name: str


class StudentUpdate(BaseModel):
    full_name: str


class StudentResponse(BaseModel):
    id: int
    full_name: str


class ModuleResponse(BaseModel):
    id: int
    name: str
    is_active: bool
    is_finished: bool


class LessonResponse(BaseModel):
    id: int
    name: str
    lesson_number: int
    is_active: bool


class CriteriaCreate(BaseModel):
    name: str
    max_points: int
    grading_method: str


class CriteriaUpdate(BaseModel):
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


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


# Groups
@router.get("/groups", response_model=List[GroupResponse])
async def get_groups(db: AsyncSession = Depends(get_db), teacher_id: int = Depends(require_teacher)):
    try:
        result = await db.execute(select(Group).filter(Group.teacher_id == teacher_id))
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Error getting groups: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving groups")


@router.post("/groups", response_model=GroupResponse)
async def create_group(group: GroupCreate, db: AsyncSession = Depends(get_db),
                       teacher_id: int = Depends(require_teacher)):
    try:
        groups_count = await db.execute(
            select(func.count(Group.id)).filter(Group.teacher_id == teacher_id, Group.is_active == True))
        if groups_count.scalar() >= 6:
            raise HTTPException(status_code=400, detail="Maximum 6 active groups allowed")

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
        return db_group
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating group: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error creating group")


@router.put("/groups/{group_id}", response_model=GroupResponse)
async def update_group(group_id: int, group: GroupUpdate, db: AsyncSession = Depends(get_db),
                       teacher_id: int = Depends(require_teacher)):
    try:
        result = await db.execute(select(Group).filter(Group.id == group_id, Group.teacher_id == teacher_id))
        db_group = result.scalar_one_or_none()
        if not db_group:
            raise HTTPException(status_code=404, detail="Group not found")

        db_group.name = group.name
        await db.commit()
        await db.refresh(db_group)
        return db_group
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating group: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error updating group")


@router.delete("/groups/{group_id}")
async def delete_group(group_id: int, db: AsyncSession = Depends(get_db),
                       teacher_id: int = Depends(require_teacher)):
    try:
        result = await db.execute(select(Group).filter(Group.id == group_id, Group.teacher_id == teacher_id))
        db_group = result.scalar_one_or_none()
        if not db_group:
            raise HTTPException(status_code=404, detail="Group not found")

        await db.delete(db_group)
        await db.commit()
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
    try:
        result = await db.execute(select(Group).filter(Group.id == group_id, Group.teacher_id == teacher_id))
        db_group = result.scalar_one_or_none()
        if not db_group:
            raise HTTPException(status_code=404, detail="Group not found")

        db_group.is_active = False
        await db.commit()
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
    try:
        group_result = await db.execute(select(Group).filter(Group.id == group_id, Group.teacher_id == teacher_id))
        if not group_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Group not found")

        result = await db.execute(select(Student).filter(Student.group_id == group_id))
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting students: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving students")


@router.post("/groups/{group_id}/students", response_model=StudentResponse)
async def create_student(group_id: int, student: StudentCreate, db: AsyncSession = Depends(get_db),
                         teacher_id: int = Depends(require_teacher)):
    try:
        group_result = await db.execute(select(Group).filter(Group.id == group_id, Group.teacher_id == teacher_id))
        if not group_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Group not found")

        students_count = await db.execute(select(func.count(Student.id)).filter(Student.group_id == group_id))
        if students_count.scalar() >= 30:
            raise HTTPException(status_code=400, detail="Maximum 30 students allowed per group")

        db_student = Student(full_name=student.full_name, group_id=group_id)
        db.add(db_student)
        await db.commit()
        await db.refresh(db_student)
        return db_student
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating student: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error creating student")


@router.put("/students/{student_id}", response_model=StudentResponse)
async def update_student(student_id: int, student: StudentUpdate, db: AsyncSession = Depends(get_db),
                         teacher_id: int = Depends(require_teacher)):
    try:
        result = await db.execute(
            select(Student)
            .join(Group, Student.group_id == Group.id)
            .filter(Student.id == student_id, Group.teacher_id == teacher_id)
        )
        db_student = result.scalar_one_or_none()
        if not db_student:
            raise HTTPException(status_code=404, detail="Student not found")

        db_student.full_name = student.full_name
        await db.commit()
        await db.refresh(db_student)
        return db_student
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating student: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error updating student")


@router.delete("/students/{student_id}")
async def delete_student(student_id: int, db: AsyncSession = Depends(get_db),
                         teacher_id: int = Depends(require_teacher)):
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
    try:
        group_result = await db.execute(select(Group).filter(Group.id == group_id, Group.teacher_id == teacher_id))
        if not group_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Group not found")

        result = await db.execute(select(Module).filter(Module.group_id == group_id).order_by(Module.id))
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting modules: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving modules")


@router.post("/groups/{group_id}/modules", response_model=ModuleResponse)
async def create_module(group_id: int, db: AsyncSession = Depends(get_db),
                        teacher_id: int = Depends(require_teacher)):
    try:
        group_result = await db.execute(select(Group).filter(Group.id == group_id, Group.teacher_id == teacher_id))
        if not group_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Group not found")

        active_module = await db.execute(select(Module).filter(Module.group_id == group_id, Module.is_active == True))
        if active_module.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Only one active module allowed per group")

        modules_count = await db.execute(select(func.count(Module.id)).filter(Module.group_id == group_id))
        module_number = modules_count.scalar() + 1

        db_module = Module(name=f"Module {module_number}", group_id=group_id)
        db.add(db_module)
        await db.commit()
        await db.refresh(db_module)
        return db_module
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating module: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error creating module")


@router.delete("/modules/{module_id}")
async def delete_module(module_id: int, db: AsyncSession = Depends(get_db),
                        teacher_id: int = Depends(require_teacher)):
    try:
        result = await db.execute(
            select(Module)
            .join(Group, Module.group_id == Group.id)
            .filter(Module.id == module_id, Group.teacher_id == teacher_id)
        )
        db_module = result.scalar_one_or_none()
        if not db_module:
            raise HTTPException(status_code=404, detail="Module not found")

        # Check if this is the last module in the group
        last_module = await db.execute(
            select(Module)
            .filter(Module.group_id == db_module.group_id)
            .order_by(Module.id.desc())
            .limit(1)
        )
        last_module_obj = last_module.scalar_one_or_none()

        if not last_module_obj or last_module_obj.id != module_id:
            raise HTTPException(status_code=400, detail="Only the last module can be deleted")

        if not db_module.is_active:
            raise HTTPException(status_code=400, detail="Cannot delete finished modules")

        await db.delete(db_module)
        await db.commit()
        return {"message": "Module deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting module: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error deleting module")


@router.post("/modules/{module_id}/finish")
async def finish_module(module_id: int, db: AsyncSession = Depends(get_db),
                        teacher_id: int = Depends(require_teacher)):
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
    try:
        module_result = await db.execute(
            select(Module)
            .join(Group, Module.group_id == Group.id)
            .filter(Module.id == module_id, Group.teacher_id == teacher_id)
        )
        if not module_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Module not found")

        result = await db.execute(
            select(Lesson)
            .filter(Lesson.module_id == module_id)
            .order_by(Lesson.lesson_number)
        )
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting lessons: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving lessons")


@router.post("/modules/{module_id}/lessons/start", response_model=LessonResponse)
async def start_lesson(module_id: int, db: AsyncSession = Depends(get_db),
                       teacher_id: int = Depends(require_teacher)):
    try:
        module_result = await db.execute(
            select(Module)
            .join(Group, Module.group_id == Group.id)
            .filter(Module.id == module_id, Group.teacher_id == teacher_id, Module.is_active == True)
        )
        if not module_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Active module not found")

        # Check if there's an active lesson
        active_lesson = await db.execute(
            select(Lesson)
            .filter(Lesson.module_id == module_id, Lesson.is_active == True)
        )
        if active_lesson.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Finish current lesson before starting a new one")

        # Get lesson count for numbering
        lessons_count_result = await db.execute(select(func.count(Lesson.id)).filter(Lesson.module_id == module_id))
        lessons_count = lessons_count_result.scalar()

        if lessons_count >= 15:
            raise HTTPException(status_code=400, detail="Maximum 15 lessons allowed per module")

        lesson_number = lessons_count + 1
        db_lesson = Lesson(
            name=f"Lesson {lesson_number}",
            lesson_number=lesson_number,
            module_id=module_id,
            is_active=True
        )
        db.add(db_lesson)
        await db.commit()
        await db.refresh(db_lesson)
        return db_lesson
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting lesson: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error starting lesson")


@router.post("/lessons/{lesson_id}/finish")
async def finish_lesson(lesson_id: int, db: AsyncSession = Depends(get_db),
                        teacher_id: int = Depends(require_teacher)):
    try:
        result = await db.execute(
            select(Lesson)
            .join(Module, Lesson.module_id == Module.id)
            .join(Group, Module.group_id == Group.id)
            .filter(Lesson.id == lesson_id, Group.teacher_id == teacher_id)
        )
        db_lesson = result.scalar_one_or_none()
        if not db_lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")

        db_lesson.is_active = False
        await db.commit()
        return {"message": "Lesson finished"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finishing lesson: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error finishing lesson")


@router.delete("/lessons/{lesson_id}")
async def delete_lesson(lesson_id: int, db: AsyncSession = Depends(get_db),
                        teacher_id: int = Depends(require_teacher)):
    try:
        result = await db.execute(
            select(Lesson)
            .join(Module, Lesson.module_id == Module.id)
            .join(Group, Module.group_id == Group.id)
            .filter(Lesson.id == lesson_id, Group.teacher_id == teacher_id)
        )
        db_lesson = result.scalar_one_or_none()
        if not db_lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")

        if not db_lesson.is_active:
            raise HTTPException(status_code=400, detail="Cannot delete finished lessons")

        # Check if this is the last lesson in the module
        last_lesson = await db.execute(
            select(Lesson)
            .filter(Lesson.module_id == db_lesson.module_id)
            .order_by(Lesson.lesson_number.desc())
            .limit(1)
        )
        last_lesson_obj = last_lesson.scalar_one_or_none()

        if not last_lesson_obj or last_lesson_obj.id != lesson_id:
            raise HTTPException(status_code=400, detail="Only the latest lesson can be deleted")

        await db.delete(db_lesson)
        await db.commit()
        return {"message": "Lesson deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting lesson: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error deleting lesson")


# Criteria
@router.get("/modules/{module_id}/criteria", response_model=List[CriteriaResponse])
async def get_criteria(module_id: int, db: AsyncSession = Depends(get_db),
                       teacher_id: int = Depends(require_teacher)):
    try:
        module_result = await db.execute(
            select(Module)
            .join(Group, Module.group_id == Group.id)
            .filter(Module.id == module_id, Group.teacher_id == teacher_id)
        )
        if not module_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Module not found")

        result = await db.execute(select(Criteria).filter(Criteria.module_id == module_id))
        return result.scalars().all()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting criteria: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving criteria")


# Replace ONLY the create_criteria function in your app/api/teacher.py with this debug version:

@router.post("/modules/{module_id}/criteria", response_model=CriteriaResponse)
async def create_criteria(module_id: int, criteria: CriteriaCreate, db: AsyncSession = Depends(get_db),
                          teacher_id: int = Depends(require_teacher)):
    try:
        logger.info(f"🔄 Creating criteria: {criteria.name}, method: {criteria.grading_method}")

        module_result = await db.execute(
            select(Module)
            .join(Group, Module.group_id == Group.id)
            .filter(Module.id == module_id, Group.teacher_id == teacher_id, Module.is_active == True)
        )
        if not module_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Active module not found")

        criteria_count = await db.execute(select(func.count(Criteria.id)).filter(Criteria.module_id == module_id))
        if criteria_count.scalar() >= 6:
            raise HTTPException(status_code=400, detail="Maximum 6 criteria allowed per module")

        # Convert to lowercase to match enum values
        grading_method_str = criteria.grading_method.lower()
        logger.info(f"🔄 Converting grading method: '{criteria.grading_method}' -> '{grading_method_str}'")

        try:
            grading_method = GradingMethod(grading_method_str)
            logger.info(f"✅ Enum conversion successful: {grading_method}")
            logger.info(f"🔍 Enum name: {grading_method.name}")
            logger.info(f"🔍 Enum value: {grading_method.value}")
            logger.info(f"🔍 Enum type: {type(grading_method)}")
        except ValueError as ve:
            logger.error(f"❌ Invalid grading method: {grading_method_str}, error: {ve}")
            raise HTTPException(status_code=400, detail="Invalid grading method")

        # Test what SQLAlchemy will actually send
        logger.info(f"🔍 About to create Criteria object...")

        db_criteria = Criteria(
            name=criteria.name,
            max_points=criteria.max_points,
            grading_method=grading_method,
            module_id=module_id
        )

        logger.info(f"🔍 Criteria object created, grading_method attr: {db_criteria.grading_method}")
        logger.info(f"🔍 Criteria object grading_method value: {db_criteria.grading_method.value}")

        db.add(db_criteria)
        logger.info(f"🔍 About to commit to database...")

        await db.commit()
        await db.refresh(db_criteria)
        logger.info(f"✅ Criteria created successfully: {db_criteria.id}")
        return db_criteria

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating criteria: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error creating criteria")

@router.put("/criteria/{criteria_id}", response_model=CriteriaResponse)
async def update_criteria(criteria_id: int, criteria: CriteriaUpdate, db: AsyncSession = Depends(get_db),
                          teacher_id: int = Depends(require_teacher)):
    try:
        logger.info(f"🔄 Updating criteria: {criteria_id}, method: {criteria.grading_method}")

        result = await db.execute(
            select(Criteria)
            .join(Module, Criteria.module_id == Module.id)
            .join(Group, Module.group_id == Group.id)
            .filter(Criteria.id == criteria_id, Group.teacher_id == teacher_id)
        )
        db_criteria = result.scalar_one_or_none()
        if not db_criteria:
            raise HTTPException(status_code=404, detail="Criteria not found")

        # Convert to lowercase to match enum values
        grading_method_str = criteria.grading_method.lower()
        logger.info(f"🔄 Converting grading method: '{criteria.grading_method}' -> '{grading_method_str}'")

        try:
            grading_method = GradingMethod(grading_method_str)
            logger.info(f"✅ Enum conversion successful: {grading_method}")
        except ValueError:
            logger.error(f"❌ Invalid grading method: {grading_method_str}")
            raise HTTPException(status_code=400, detail="Invalid grading method")

        db_criteria.name = criteria.name
        db_criteria.max_points = criteria.max_points
        db_criteria.grading_method = grading_method
        await db.commit()
        await db.refresh(db_criteria)
        logger.info(f"✅ Criteria updated successfully: {criteria_id}")
        return db_criteria
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating criteria: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error updating criteria")


@router.delete("/criteria/{criteria_id}")
async def delete_criteria(criteria_id: int, db: AsyncSession = Depends(get_db),
                          teacher_id: int = Depends(require_teacher)):
    try:
        result = await db.execute(
            select(Criteria)
            .join(Module, Criteria.module_id == Module.id)
            .join(Group, Module.group_id == Group.id)
            .filter(Criteria.id == criteria_id, Group.teacher_id == teacher_id)
        )
        db_criteria = result.scalar_one_or_none()
        if not db_criteria:
            raise HTTPException(status_code=404, detail="Criteria not found")

        await db.delete(db_criteria)
        await db.commit()
        return {"message": "Criteria deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting criteria: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error deleting criteria")


# Grades
@router.post("/grades", response_model=GradeResponse)
async def create_grade(grade: GradeCreate, db: AsyncSession = Depends(get_db),
                       teacher_id: int = Depends(require_teacher)):
    try:
        lesson_result = await db.execute(
            select(Lesson)
            .join(Module, Lesson.module_id == Module.id)
            .join(Group, Module.group_id == Group.id)
            .filter(Lesson.id == grade.lesson_id, Group.teacher_id == teacher_id, Module.is_active == True)
        )
        if not lesson_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Lesson not found or module not active")

        existing_grade = await db.execute(
            select(Grade).filter(
                Grade.student_id == grade.student_id,
                Grade.criteria_id == grade.criteria_id,
                Grade.lesson_id == grade.lesson_id
            )
        )

        db_grade = existing_grade.scalar_one_or_none()
        if db_grade:
            db_grade.points_earned = grade.points_earned
        else:
            db_grade = Grade(**grade.dict())
            db.add(db_grade)

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
    try:
        module_result = await db.execute(
            select(Module)
            .join(Group, Module.group_id == Group.id)
            .filter(Module.id == module_id, Group.teacher_id == teacher_id)
        )
        if not module_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Module not found")

        return await calculate_student_totals(db, module_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        raise HTTPException(status_code=500, detail="Error generating leaderboard")


# Password change
@router.post("/change-password")
async def change_password(password_data: PasswordChange, db: AsyncSession = Depends(get_db),
                          teacher_id: int = Depends(require_teacher)):
    try:
        result = await db.execute(select(Teacher).filter(Teacher.id == teacher_id))
        teacher = result.scalar_one_or_none()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found")

        if not verify_password(password_data.current_password, teacher.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

        teacher.hashed_password = get_password_hash(password_data.new_password)
        await db.commit()
        return {"message": "Password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error changing password")