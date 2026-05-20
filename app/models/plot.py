from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, Text, func
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Plot(Base):
    __tablename__ = "plots"
    __table_args__ = (UniqueConstraint("layout_id", "plot_no"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    layout_id: Mapped[str] = mapped_column(
        ForeignKey("layouts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plot_no: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="available", index=True
    )
    hotspot: Mapped[dict] = mapped_column(JSON, nullable=False)
    dim_ft: Mapped[str | None] = mapped_column(Text, nullable=True)
    dim_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    area_sq_ft: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    area_sq_yd: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    facing: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    layout = relationship("Layout", back_populates="plots")
