from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


class Lesson(Base):
    __tablename__ = "gt_lessons"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    lesson_number = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)  # Added missing field
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    module_id = Column(Integer, ForeignKey("gt_modules.id"), nullable=False)

    module = relationship("Module", back_populates="lessons")
    grades = relationship("Grade", back_populates="lesson", cascade="all, delete-orphan")