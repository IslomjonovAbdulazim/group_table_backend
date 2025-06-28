from sqlalchemy import Column, Integer, String, Enum, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from ..core.database import Base


class GradingMethod(enum.Enum):
    ONE_BY_ONE = "one_by_one"
    BULK = "bulk"


class Criteria(Base):
    __tablename__ = "criteria"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    max_points = Column(Integer, nullable=False)
    grading_method = Column(Enum(GradingMethod), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    module_id = Column(Integer, ForeignKey("modules.id"), nullable=False)

    module = relationship("Module", back_populates="criteria")
    grades = relationship("Grade", back_populates="criteria", cascade="all, delete-orphan")