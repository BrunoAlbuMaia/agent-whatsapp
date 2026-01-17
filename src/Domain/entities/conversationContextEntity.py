from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

class Message(BaseModel):
    role: str  # 'user' ou 'assistant'
    content: str
    timestamp: datetime

class ConversationContext(BaseModel):
    sender_id: str
    messages: List[Message] = field(default_factory=list)
    current_intent: Optional[str] = None
    tool_results: List[dict] = field(default_factory=list)
    
    def add_message(self, role: str, content: str):
        self.messages.append(Message(
            role=role,
            content=content,
            timestamp=datetime.now()
        ))
    
    def get_recent_messages(self, limit: int = 5) -> List[Message]:
        """Pega últimas N mensagens para contexto"""
        return self.messages[-limit:]