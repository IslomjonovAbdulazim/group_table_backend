from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from ..models.grade import Grade
from ..models.student import Student
from ..models.lesson import Lesson
from ..models.criteria import Criteria
from ..models.module import Module
import logging

logger = logging.getLogger(__name__)


async def calculate_student_totals(session: AsyncSession, module_id: int):
    """
    Calculate total points for all students in a module and rank them
    """
    try:
        logger.info(f"Calculating student totals for module {module_id}")

        # Get all students in the group that owns this module
        module_result = await session.execute(
            select(Module).filter(Module.id == module_id)
        )
        module = module_result.scalar_one_or_none()

        if not module:
            logger.warning(f"Module {module_id} not found")
            return []

        # Get all students in the group
        students_result = await session.execute(
            select(Student).filter(Student.group_id == module.group_id)
        )
        students = students_result.scalars().all()

        if not students:
            logger.info(f"No students found for module {module_id}")
            return []

        # Calculate total points for each student
        student_totals = []

        for student in students:
            # Get all grades for this student in this module
            grades_result = await session.execute(
                select(func.sum(Grade.points_earned).label('total_points'))
                .join(Lesson, Grade.lesson_id == Lesson.id)
                .filter(
                    and_(
                        Grade.student_id == student.id,
                        Lesson.module_id == module_id
                    )
                )
            )

            total_points = grades_result.scalar() or 0

            student_totals.append({
                "student_id": student.id,
                "name": student.full_name,
                "total_points": int(total_points)
            })

        # Sort by total points (descending) and assign positions
        student_totals.sort(key=lambda x: x['total_points'], reverse=True)

        # Assign positions (handle ties)
        ranked_students = []
        current_position = 1

        for i, student in enumerate(student_totals):
            # If this student has the same points as the previous one, keep the same position
            if i > 0 and student['total_points'] < student_totals[i - 1]['total_points']:
                current_position = i + 1

            ranked_students.append({
                **student,
                "position": current_position
            })

        logger.info(f"Calculated rankings for {len(ranked_students)} students in module {module_id}")
        return ranked_students

    except Exception as e:
        logger.error(f"Error calculating student totals for module {module_id}: {e}")
        return []


async def calculate_lesson_totals(session: AsyncSession, lesson_id: int):
    """
    Calculate total points for all students in a specific lesson
    """
    try:
        logger.info(f"Calculating lesson totals for lesson {lesson_id}")

        # Get lesson info
        lesson_result = await session.execute(
            select(Lesson).filter(Lesson.id == lesson_id)
        )
        lesson = lesson_result.scalar_one_or_none()

        if not lesson:
            logger.warning(f"Lesson {lesson_id} not found")
            return []

        # Get module info to find students
        module_result = await session.execute(
            select(Module).filter(Module.id == lesson.module_id)
        )
        module = module_result.scalar_one_or_none()

        if not module:
            logger.warning(f"Module {lesson.module_id} not found")
            return []

        # Get all students in the group
        students_result = await session.execute(
            select(Student).filter(Student.group_id == module.group_id)
        )
        students = students_result.scalars().all()

        # Calculate lesson totals for each student
        lesson_totals = []

        for student in students:
            # Get all grades for this student in this lesson
            grades_result = await session.execute(
                select(func.sum(Grade.points_earned).label('lesson_total'))
                .filter(
                    and_(
                        Grade.student_id == student.id,
                        Grade.lesson_id == lesson_id
                    )
                )
            )

            lesson_total = grades_result.scalar() or 0

            lesson_totals.append({
                "student_id": student.id,
                "name": student.full_name,
                "lesson_total": int(lesson_total),
                "lesson_id": lesson_id,
                "lesson_name": lesson.name
            })

        # Sort by lesson total (descending)
        lesson_totals.sort(key=lambda x: x['lesson_total'], reverse=True)

        logger.info(f"Calculated lesson totals for {len(lesson_totals)} students in lesson {lesson_id}")
        return lesson_totals

    except Exception as e:
        logger.error(f"Error calculating lesson totals for lesson {lesson_id}: {e}")
        return []


async def calculate_criteria_stats(session: AsyncSession, criteria_id: int):
    """
    Calculate statistics for a specific criteria across all lessons
    """
    try:
        logger.info(f"Calculating criteria stats for criteria {criteria_id}")

        # Get criteria info
        criteria_result = await session.execute(
            select(Criteria).filter(Criteria.id == criteria_id)
        )
        criteria = criteria_result.scalar_one_or_none()

        if not criteria:
            logger.warning(f"Criteria {criteria_id} not found")
            return {}

        # Get all grades for this criteria
        grades_result = await session.execute(
            select(
                func.count(Grade.id).label('total_grades'),
                func.avg(Grade.points_earned).label('average_points'),
                func.max(Grade.points_earned).label('max_points_earned'),
                func.min(Grade.points_earned).label('min_points_earned')
            )
            .filter(Grade.criteria_id == criteria_id)
        )

        stats = grades_result.first()

        if not stats or stats.total_grades == 0:
            return {
                "criteria_id": criteria_id,
                "criteria_name": criteria.name,
                "max_points": criteria.max_points,
                "total_grades": 0,
                "average_points": 0,
                "max_points_earned": 0,
                "min_points_earned": 0,
                "completion_rate": 0
            }

        # Calculate completion rate (assuming all students should have grades)
        module_result = await session.execute(
            select(Module).filter(Module.id == criteria.module_id)
        )
        module = module_result.scalar_one_or_none()

        expected_grades = 0
        if module:
            students_result = await session.execute(
                select(func.count(Student.id))
                .filter(Student.group_id == module.group_id)
            )
            students_count = students_result.scalar() or 0

            lessons_result = await session.execute(
                select(func.count(Lesson.id))
                .filter(Lesson.module_id == module.id)
            )
            lessons_count = lessons_result.scalar() or 0

            expected_grades = students_count * lessons_count

        completion_rate = (stats.total_grades / expected_grades * 100) if expected_grades > 0 else 0

        return {
            "criteria_id": criteria_id,
            "criteria_name": criteria.name,
            "max_points": criteria.max_points,
            "total_grades": stats.total_grades,
            "average_points": round(float(stats.average_points), 2),
            "max_points_earned": stats.max_points_earned,
            "min_points_earned": stats.min_points_earned,
            "completion_rate": round(completion_rate, 2)
        }

    except Exception as e:
        logger.error(f"Error calculating criteria stats for criteria {criteria_id}: {e}")
        return {}


def calculate_position_change(previous_position: int, current_position: int):
    """
    Calculate the change in position between two rankings
    Returns positive for improvement (moving up), negative for decline
    """
    if previous_position is None or current_position is None:
        return 0

    # Lower position number = better ranking
    # So if previous was 5 and current is 3, change = +2 (improvement)
    change = previous_position - current_position
    return change


async def get_module_statistics(session: AsyncSession, module_id: int):
    """
    Get comprehensive statistics for a module
    """
    try:
        logger.info(f"Getting module statistics for module {module_id}")

        # Get module info
        module_result = await session.execute(
            select(Module).filter(Module.id == module_id)
        )
        module = module_result.scalar_one_or_none()

        if not module:
            return {}

        # Count lessons
        lessons_result = await session.execute(
            select(func.count(Lesson.id))
            .filter(Lesson.module_id == module_id)
        )
        lessons_count = lessons_result.scalar() or 0

        # Count criteria
        criteria_result = await session.execute(
            select(func.count(Criteria.id))
            .filter(Criteria.module_id == module_id)
        )
        criteria_count = criteria_result.scalar() or 0

        # Count total possible points
        total_points_result = await session.execute(
            select(func.sum(Criteria.max_points))
            .filter(Criteria.module_id == module_id)
        )
        max_points_per_lesson = total_points_result.scalar() or 0
        total_possible_points = max_points_per_lesson * lessons_count

        # Count students
        students_result = await session.execute(
            select(func.count(Student.id))
            .filter(Student.group_id == module.group_id)
        )
        students_count = students_result.scalar() or 0

        # Count total grades given
        grades_result = await session.execute(
            select(func.count(Grade.id))
            .join(Lesson, Grade.lesson_id == Lesson.id)
            .filter(Lesson.module_id == module_id)
        )
        total_grades = grades_result.scalar() or 0

        # Calculate average score
        avg_score_result = await session.execute(
            select(func.avg(Grade.points_earned))
            .join(Lesson, Grade.lesson_id == Lesson.id)
            .filter(Lesson.module_id == module_id)
        )
        average_score = avg_score_result.scalar() or 0

        expected_grades = students_count * lessons_count * criteria_count
        completion_rate = (total_grades / expected_grades * 100) if expected_grades > 0 else 0

        return {
            "module_id": module_id,
            "module_name": module.name,
            "is_active": module.is_active,
            "is_finished": module.is_finished,
            "lessons_count": lessons_count,
            "criteria_count": criteria_count,
            "students_count": students_count,
            "total_possible_points": total_possible_points,
            "max_points_per_lesson": max_points_per_lesson,
            "total_grades_given": total_grades,
            "expected_grades": expected_grades,
            "completion_rate": round(completion_rate, 2),
            "average_score": round(float(average_score), 2) if average_score else 0
        }

    except Exception as e:
        logger.error(f"Error getting module statistics for module {module_id}: {e}")
        return {}