from abc import ABC,abstractmethod
from src.Domain import ResponsePackageEntity


class IAgentOrchestratorService(ABC):
    @abstractmethod
    async def process_message(self, sender_id: str, message: str) -> ResponsePackageEntity:...
