from abc import ABC,abstractmethod
from typing import List,Dict,Any

class IToolExecutorService(ABC):
    @abstractmethod
    def get_available_tools(self) -> List[dict]:...
    @abstractmethod
    async def execute_tools(self, tool_calls: List[dict]) -> List[Dict[str, Any]]:...