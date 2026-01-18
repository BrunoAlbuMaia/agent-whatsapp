import os
import json
import logging
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from src.config import settings
from src.Domain import IOpenAiClient

logger = logging.getLogger(__name__)

class OpenAIClient(IOpenAiClient):
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY
        )
        self.model = settings.OPENAI_MODEL
    
    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.3
    ) -> Dict[str, Any]:
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                # "temperature": temperature
            }
            
            if tools:
                kwargs["tools"] = [
                    {
                        "type": "function",
                        "function": tool,
                        "strict": True
                    } for tool in tools
                ]
                kwargs["tool_choice"] = "auto"
            
            response = await self.client.chat.completions.create(**kwargs)
            message = response.choices[0].message
            
            # Resultado padrão inicial
            result = {
                "content": message.content or ""
            }
            
            # Se a OpenAI retornou Tool Calls nativas, "jogamos" para o content no formato JSON
            if message.tool_calls:
                # Pegamos a primeira ferramenta chamada (fluxo de decisão única)
                tool_call = message.tool_calls[0]
                
                # Parse seguro dos argumentos (string -> dict)
                try:
                    tool_params = json.loads(tool_call.function.arguments)
                except Exception:
                    tool_params = {}

                # Monta o JSON de decisão que o seu Orchestrator já sabe ler
                decision_obj = {
                    "decision": "call_tool",
                    "tool_name": tool_call.function.name,
                    "tool_params": tool_params,
                    "reason": "Native tool call detected"
                }
                
                # Serializa de volta para string para o Orchestrator dar o json.loads() lá
                result["content"] = json.dumps(decision_obj, ensure_ascii=False)
            
            logger.info(f"OpenAI processed response: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Erro na chamada OpenAI: {e}")
            raise