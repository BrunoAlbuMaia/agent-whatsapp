from pydantic import BaseModel
from typing import Dict,Optional
from datetime import datetime
import uuid


class ConversationStateEntity(BaseModel):
    id: Optional[uuid.UUID] = None
    conversation_id: uuid.UUID

    state: Dict
    version: int

    created_at: Optional[datetime] = None
