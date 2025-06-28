from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ..models.grade import Grade
from ..models.student import Student
from ..models.lesson import Lesson


async def calculate_student_totals(session: AsyncSession, module_id: int):
    result = await session.execute(
        select(
            Student.id,
            Student.full_name,
            func.sum(Grade.points_earned).label('total_points')
        )
        .join(Grade, Student.id == Grade.student_id)
        .join(Lesson, Grade.lesson_id == Lesson.id)
        .where(Lesson.module_id == module_id)
        .group_by(Student.id, Student.full_name)
        .order_by(func.sum(Grade.points_earned).desc())
    )

    students = result.fetchall()
    ranked_students = []

    for index, student in enumerate(students):
        ranked_students.append({
            "student_id": student.id,
            "name": student.full_name,
            "total_points": student.total_points or 0,
            "position": index + 1
        })

    return ranked_students


def calculate_position_change(previous_position: int, current_position: int):
    if previous_position is None:
        return 0
    change = previous_position - current_position
    return change