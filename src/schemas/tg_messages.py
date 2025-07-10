from pydantic import BaseModel


class AddTgMessage(BaseModel):
    product_id: int
    tg_message_id: int
    tg_group_id: int
    tg_topic_id: int


class TgMessages(AddTgMessage):
    id: int
