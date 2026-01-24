# src/Domain/IMessageRepository.py
from abc import ABC, abstractmethod
from typing import List
from src.Domain import MessageEntity
import uuid


class IMessageRepository(ABC):

    @abstractmethod
    async def create(self, message: MessageEntity) -> MessageEntity:
        pass

    @abstractmethod
    async def list_by_conversation(
        self,
        conversation_id: uuid.UUID,
        limit: int = 50
        ) -> List[MessageEntity]:
        pass
