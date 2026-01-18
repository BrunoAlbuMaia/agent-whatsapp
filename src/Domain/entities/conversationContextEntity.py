from typing import Dict, Optional,List
from pydantic import BaseModel,Field
from datetime import datetime

class Message(BaseModel):
    role: str
    content: str
    timestamp: datetime

class ConversationContext(BaseModel):
    sender_id: str
    messages: list[Message] = []
    current_intent: Optional[str] = None
    slots: Dict[str, str] = None
    awaiting_field: Optional[str] = None
    tool_results: List[dict] = Field(default_factory=list)

    def add_message(self, role: str, content: str):
        self.messages.append(
            Message(
                role=role,
                content=content,
                timestamp=datetime.now()
            )
        )

    def get_recent_messages(self, limit: int = 5):
        return self.messages[-limit:]
