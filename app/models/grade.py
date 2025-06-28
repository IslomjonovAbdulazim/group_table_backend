from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


class Grade(Base):
    __tablename__ = "gt_grades"

    id = Column(Integer, primary_key=True, index=True)
    points_earned = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    student_id = Column(Integer, ForeignKey("gt_students.id"), nullable=False)
    criteria_id = Column(Integer, ForeignKey("gt_criteria.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("gt_lessons.id"), nullable=False)

    student = relationship("Student", back_populates="grades")
    criteria = relationship("Criteria", back_populates="grades")
    lesson = relationship("Lesson", back_populates="grades")