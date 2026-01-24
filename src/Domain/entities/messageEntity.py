from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime
import uuid


class MessageEntity(BaseModel):
    id: Optional[uuid.UUID] = None
    conversation_id: uuid.UUID

    role: str = Field(..., description="user | assistant | system | tool")
    content: str

    created_at: Optional[datetime] = None
    metadata: Optional[Dict] = None
