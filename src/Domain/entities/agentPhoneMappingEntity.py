from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from uuid import UUID, uuid4

@dataclass
class AgentPhoneMappingEntity:
    """
    Entidade que mapeia um número de telefone (instance) para um agente.
    Permite que cada número do WhatsApp tenha um agente especializado.
    """
    phone_number: str  # Instance do WhatsApp (ex: "vendas", "fiscal", etc)
    agent_id: UUID
    id: Optional[UUID] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.id is None:
            self.id = uuid4()
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def to_dict(self) -> dict:
        """Converte para dict (útil para serialização)"""
        return {
            "id": str(self.id),
            "phone_number": self.phone_number,
            "agent_id": str(self.agent_id),
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AgentPhoneMappingEntity':
        """Cria instância a partir de dict"""
        return cls(
            id=UUID(data["id"]) if isinstance(data.get("id"), str) else data.get("id"),
            phone_number=data["phone_number"],
            agent_id=UUID(data["agent_id"]) if isinstance(data["agent_id"], str) else data["agent_id"],
            is_active=data.get("is_active", True),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
        )
