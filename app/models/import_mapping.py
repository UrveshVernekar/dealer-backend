from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func
from app.core.database import Base


class ImportTableMapping(Base):
    __tablename__ = "import_table_mappings"

    id = Column(Integer, primary_key=True, index=True)
    original_sheet_name = Column(String, nullable=False, unique=True)
    normalized_table_name = Column(String, nullable=False)
    imported_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return (
            f"<ImportTableMapping(original_sheet_name={self.original_sheet_name!r}, "
            f"normalized_table_name={self.normalized_table_name!r})>"
        )
