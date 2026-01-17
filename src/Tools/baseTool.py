from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:...
    
    @property
    @abstractmethod
    def description(self) -> str:...
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:...
        
    def get_schema(self) -> dict:
        """Schema para o LLM"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self._get_parameters()
        }
    
    @abstractmethod
    def _get_parameters(self) -> dict:
        """Parâmetros esperados"""
        