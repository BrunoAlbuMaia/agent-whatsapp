from abc import ABC,abstractmethod
from src.Domain import ResponsePackageEntity


class IWhatsAppOrchestratorService(ABC):
    @abstractmethod
    async def send_response(
        self,
        agent_name: str,
        phone_number: str,
        response_package: ResponsePackageEntity
    ):...
