from sqlalchemy import Column, Integer, String, Float
from app.core.database import Base

class TargetData(Base):
    __tablename__ = "target_data"

    id = Column(Integer, primary_key=True, index=True)
    region = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    channel_code = Column(String(50), nullable=True)
    new_channel = Column(String(50), nullable=True)
    sold_to_code = Column(String(50), nullable=True)
    new_sold_to_party = Column(String(50), nullable=True)
    dealer_name = Column(String(255), nullable=True)
    product = Column(String(100), nullable=True)
    product_raw = Column(String(100), nullable=True)
    q1 = Column(Float, nullable=True)
    q2 = Column(Float, nullable=True)
    q3 = Column(Float, nullable=True)
    q4 = Column(Float, nullable=True)
    total = Column(Float, nullable=True)
    remarks = Column(String(255), nullable=True)
