import os
import logging
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from src.config import settings

logger = logging.getLogger(__name__)

class OpenAIClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY
        )
        self.model = settings.OPENAI_MODEL  # ou gpt-4o
    
    async def chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.3
    ) -> Dict[str, Any]:
        try:
            kwargs = {
                "model": self.model,
                "messages": messages
                
            }
            
            # Adiciona tools se fornecido
            if tools:
                kwargs["tools"] = [
                    {
                        "type": "function",
                        "function": tool
                    } for tool in tools
                ]
                kwargs["tool_choice"] = "auto"
            
            response = await self.client.chat.completions.create(**kwargs)
            
            # Extrai resposta
            message = response.choices[0].message
            
            result = {
                "content": message.content or "",
                "tool_calls": []
            }
            
            # Se tiver tool calls, extrai
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    result["tool_calls"].append({
                        "id": tool_call.id,
                        "name": tool_call.function.name,
                        "parameters": eval(tool_call.function.arguments)  # JSON string -> dict
                    })
            
            logger.info(f"OpenAI response: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Erro na chamada OpenAI: {e}")
            raise