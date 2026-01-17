from typing import List, Dict, Any
from src.Tools import BaseTool, SearchTool,IpvaTool
import logging

logger = logging.getLogger(__name__)

class ToolExecutor:
    def __init__(self):
        # Registra todas as tools disponíveis
        self.tools: Dict[str, BaseTool] = {
            "buscar_informacao": SearchTool(),
            "consultar_ipva": IpvaTool()
            # Adicione outras tools aqui
        }
    
    def get_available_tools(self) -> List[dict]:
        """Retorna schema de todas as tools para o LLM"""
        return [tool.get_schema() for tool in self.tools.values()]
    
    async def execute_tools(self, tool_calls: List[dict]) -> List[Dict[str, Any]]:
        """Executa as tools chamadas pelo LLM"""
        results = []
        
        for call in tool_calls:
            tool_name = call["name"]
            parameters = call.get("parameters", {})
            
            if tool_name not in self.tools:
                logger.error(f"Tool desconhecida: {tool_name}")
                results.append({
                    "tool": tool_name,
                    "error": "Tool não encontrada"
                })
                continue
            
            try:
                result = await self.tools[tool_name].execute(**parameters)
                results.append({
                    "tool": tool_name,
                    "result": result
                })
            except Exception as e:
                logger.error(f"Erro ao executar {tool_name}: {e}")
                results.append({
                    "tool": tool_name,
                    "error": str(e)
                })
        
        return results