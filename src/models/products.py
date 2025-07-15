from sqlalchemy import BIGINT, Enum as SAEnum, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from src.database.base import Base
from src.schemas.enums import SourceTypes


class Product(Base):
    __tablename__ = 'products'
    id: Mapped[int] = mapped_column(
        BIGINT,
        primary_key=True
    )
    source_type: Mapped[SourceTypes] = mapped_column(
        SAEnum(SourceTypes, name='products_source_type_enum', create_constraint=True),
        nullable=False
    )
    title: Mapped[str] = mapped_column(nullable=False)
    hashtag: Mapped[list] = mapped_column(
        JSON,
        nullable=False
    )
    rating: Mapped[float] = mapped_column(nullable=True)
    reviews: Mapped[int] = mapped_column(nullable=True)
    discount: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[int] = mapped_column(nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(nullable=True)
    unit_variants: Mapped[list] = mapped_column(
        JSON,
        nullable=True
    )
    characteristics: Mapped[dict] = mapped_column(
        JSON,
        nullable=True
    )
    photos_urls: Mapped[list] = mapped_column(
        JSON,
        nullable=True
    )
    video_url: Mapped[str] = mapped_column(nullable=True)
    url: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now()
    )

    tg_message: Mapped["TgMessages"] = relationship(
        back_populates="product",
        uselist=False,
        cascade="all, delete-orphan",
    )
