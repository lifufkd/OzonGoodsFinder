from sqlalchemy import BIGINT, UniqueConstraint, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
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
        ForeignKey('products.id'),
        unique=True
    )
    tg_message_id: Mapped[int] = mapped_column(
        BIGINT,
        nullable=False
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

    product: Mapped["Product"] = relationship(
        back_populates="tg_message"
    )

    __table_args__ = (
        UniqueConstraint(
            'product_id',
            'tg_group_id',
            'tg_topic_id',
            name='tg_messages_product_id_tg_group_id_tg_topic_id_key'
        ),
    )
