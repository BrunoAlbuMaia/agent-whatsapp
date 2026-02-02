from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from uuid import UUID, uuid4

@dataclass
class AgentConfigEntity:
    """
    Entidade que representa a configuração de um agente.
    Cada agente tem personalidade, prompts e tools específicas.
    """
    name: str
    description: str
    personality: str
    flow_decision_prompt: str
    response_prompt: str
    available_tools: List[str]
    id: Optional[UUID] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = uuid4()
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    def to_dict(self) -> dict:
        """Converte para dict (útil para serialização)"""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "personality": self.personality,
            "flow_decision_prompt": self.flow_decision_prompt,
            "response_prompt": self.response_prompt,
            "available_tools": self.available_tools,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AgentConfigEntity':
        """Cria instância a partir de dict"""
        return cls(
            id=UUID(data["id"]) if isinstance(data.get("id"), str) else data.get("id"),
            name=data["name"],
            description=data["description"],
            personality=data["personality"],
            flow_decision_prompt=data["flow_decision_prompt"],
            response_prompt=data["response_prompt"],
            available_tools=data["available_tools"],
            is_active=data.get("is_active", True),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None
        )
