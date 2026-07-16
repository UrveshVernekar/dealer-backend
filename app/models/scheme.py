from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class Scheme(Base):
    __tablename__ = "schemes"

    id = Column(Integer, primary_key=True, index=True)
    scheme_code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    discount_percentage = Column(Float, nullable=True, default=0.0)
    incentive_amount = Column(Float, nullable=True, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
