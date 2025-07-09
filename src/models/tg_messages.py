from sqlalchemy import BIGINT, UniqueConstraint, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from src.database.base import Base


class TgMessages(Base):
    __tablename__ = 'tg_messages'
    id: Mapped[int] = mapped_column(
        BIGINT,
        primary_key=True
    )
    product_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey('products.id')
    )
    tg_group_id: Mapped[int] = mapped_column(
        BIGINT,
        nullable=False
    )
    tg_topic_id: Mapped[int] = mapped_column(
        BIGINT,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint('tg_group_id', 'tg_topic_id'),
    )
