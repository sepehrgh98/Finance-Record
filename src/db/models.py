from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from db.database import Base


class ReportRecord(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    report_json = Column(Text, nullable=False)

    entities = relationship(
        "EntityRecord",
        cascade="all, delete-orphan",
        back_populates="report",
    )


class EntityRecord(Base):
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), index=True, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_name = Column(String, nullable=False)
    entity_data_json = Column(Text, nullable=False)

    report = relationship("ReportRecord", back_populates="entities")
    annotations = relationship(
        "AnnotationRecord",
        cascade="all, delete-orphan",
        back_populates="entity",
    )


class AnnotationRecord(Base):
    __tablename__ = "annotations"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), index=True, nullable=False)
    entity_id = Column(Integer, ForeignKey("entities.id"), index=True, nullable=False)
    note = Column(Text, nullable=False)

    entity = relationship("EntityRecord", back_populates="annotations")


class ActionItemRecord(Base):
    __tablename__ = "action_items"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), index=True, nullable=False)
    text = Column(Text, nullable=False)


class BusinessRuleRecord(Base):
    __tablename__ = "business_rules"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), index=True, nullable=False)
    text = Column(Text, nullable=False)


class IgnoredFileRecord(Base):
    __tablename__ = "ignored_files"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), index=True, nullable=False)
    filename = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
