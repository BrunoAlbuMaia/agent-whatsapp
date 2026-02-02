from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID
from src.Domain.entities.agentConfigEntity import AgentConfigEntity

class IAgentConfigRepository(ABC):
    """Interface para repositório de configurações de agentes"""
    
    @abstractmethod
    async def get_by_id(self, agent_id: UUID) -> Optional[AgentConfigEntity]:
        """Busca agente por ID"""
        ...
    
    @abstractmethod
    async def get_by_phone_number(self, phone_number: str) -> Optional[AgentConfigEntity]:
        """Busca agente mapeado para um número de telefone"""
        ...
    
    @abstractmethod
    async def list_active(self) -> List[AgentConfigEntity]:
        """Lista todos os agentes ativos"""
        ...
    
    @abstractmethod
    async def create(self, agent_config: AgentConfigEntity) -> AgentConfigEntity:
        """Cria novo agente"""
        ...
    
    @abstractmethod
    async def update(self, agent_config: AgentConfigEntity) -> AgentConfigEntity:
        """Atualiza agente existente"""
        ...
    
    @abstractmethod
    async def get_default_agent(self) -> Optional[AgentConfigEntity]:
        """Retorna o agente padrão (fallback)"""
        ...
