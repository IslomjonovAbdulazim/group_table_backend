# Replace your app/models/criteria.py with this simpler approach:

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from ..core.database import Base


class GradingMethod(enum.Enum):
    ONE_BY_ONE = "one_by_one"
    BULK = "bulk"


class Criteria(Base):
    __tablename__ = "gt_criteria"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    max_points = Column(Integer, nullable=False)

    # Use String column instead of enum to avoid cache issues
    grading_method = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    module_id = Column(Integer, ForeignKey("gt_modules.id"), nullable=False)

    module = relationship("Module", back_populates="criteria")
    grades = relationship("Grade", back_populates="criteria", cascade="all, delete-orphan")

