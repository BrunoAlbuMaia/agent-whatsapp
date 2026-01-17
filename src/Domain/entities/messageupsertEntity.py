from pydantic import BaseModel

class MessageupsertEntity(BaseModel):
    sender_id: str
    sender_name: str | None
    text: str
    timestamp: int
    instance: str
