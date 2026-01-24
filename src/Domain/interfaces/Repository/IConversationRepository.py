# src/Domain/Repositories/IConversationRepository.py
from abc import ABC, abstractmethod
from typing import Optional,List
from src.Domain import ConversationEntity

class IConversationRepository(ABC):

    @abstractmethod
    async def get_conversations(self) -> List[ConversationEntity]:...
    @abstractmethod
    async def get_active_conversation(self,sender_id: str,instance: str,channel: str) -> Optional[ConversationEntity]:...
    @abstractmethod
    async def create(self, conversation: ConversationEntity) -> ConversationEntity:...
    @abstractmethod
    async def touch(self, conversation_id):...
    @abstractmethod
    async def close(self, conversation_id):...