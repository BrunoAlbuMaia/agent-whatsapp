from abc import ABC,abstractmethod
from typing import List, Dict, Any, Optional

class IOpenAiClient(ABC):
    @abstractmethod
    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.3
    ) -> Dict[str, Any]:...