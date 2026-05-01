from sqlalchemy import Boolean, Integer, ForeignKey, Text, DateTime, CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    comment_date: Mapped[int | None] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[int | None] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        CheckConstraint("grade >= 1 AND grade <= 5", name="check_grade_range"),
    )

    user: Mapped["User"] = relationship("User", back_populates="reviews")
    product: Mapped["Product"] = relationship("Product", back_populates="reviews")

