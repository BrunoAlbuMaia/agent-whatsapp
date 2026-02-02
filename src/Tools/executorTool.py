from typing import List, Dict, Any, Optional
from .baseTool import BaseTool
from .searchTool import SearchTool
from .IpvaTools  import IpvaTool
from .SocialMediaAnalysisTool import SocialMediaAnalysisTool

from src.Domain import IToolExecutorService
import logging

logger = logging.getLogger(__name__)

class ExecutorTool:
    def __init__(self, allowed_tools: Optional[List[str]] = None):
        """
        Inicializa o executor de tools.
        
        Args:
            allowed_tools: Lista de nomes de tools permitidas para este agente.
                          Se None, todas as tools estarão disponíveis.
        """
        # Registro completo de TODAS as tools disponíveis no sistema
        self._all_tools: Dict[str, BaseTool] = {
            "buscar_informacao": SearchTool(),
            "consultar_ipva": IpvaTool(),
            "extrair_dados_relatorio_redes_sociais": SocialMediaAnalysisTool()
            # Adicione outras tools aqui conforme necessário
        }
        
        # Filtra apenas as tools permitidas para este agente
        if allowed_tools is not None:
            self.tools: Dict[str, BaseTool] = {
                name: tool 
                for name, tool in self._all_tools.items() 
                if name in allowed_tools
            }
            logger.info(f"[ExecutorTool] ✅ Tools filtradas: {list(self.tools.keys())}")
        else:
            # Se não especificado, disponibiliza todas
            self.tools = self._all_tools
            logger.info(f"[ExecutorTool] ✅ Todas as tools disponíveis: {list(self.tools.keys())}")
    
    def get_available_tools(self) -> List[dict]:
        """Retorna schema de todas as tools disponíveis para este agente"""
        return [tool.get_schema() for tool in self.tools.values()]
    
    async def execute_tools(self, tool_calls: List[dict]) -> List[Dict[str, Any]]:
        """Executa as tools chamadas pelo LLM"""
        results = []
        
        for call in tool_calls:
            tool_name = call["name"]
            parameters = call.get("parameters", {})
            
            if tool_name not in self.tools:
                logger.error(f"Tool '{tool_name}' não está disponível para este agente. Tools permitidas: {list(self.tools.keys())}")
                results.append({
                    "tool": tool_name,
                    "error": f"Tool não disponível para este agente. Tools permitidas: {', '.join(self.tools.keys())}"
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