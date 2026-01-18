import logging
import json
from typing import List, Optional
from src.Domain import ConversationContext,IAgentOrchestratorService,ResponsePackageEntity
from toon import encode
from .toolExecutorService import ToolExecutor
from src.Infrastructure import OpenAIClient
# from .responseGenerator import ResponseGenerator

logger = logging.getLogger(__name__)

class AgentOrchestratorService(IAgentOrchestratorService):
    def __init__(self):
        self.llm_client = OpenAIClient()
        self.tool_executor = ToolExecutor()
        # Cache de contextos por usuário
        self.contexts: dict[str, ConversationContext] = {}

        self.DECISION_PROMPT = """
                            Você é um agente de decisão.

                            Sua função é analisar a intenção do usuário e decidir:
                            - Se deve responder diretamente
                            - Ou se deve executar uma ferramenta
                            - Se a melhor ação for responder diretamente, escreva uma resposta curta e objetiva.


                            REGRAS:
                            - Não seja simpático
                            - Não explique nada para o usuário
                            - Não gere respostas longas
                            - Apenas decida a próxima ação correta

                            PASSOS:
                            1. Identifique a intenção do usuário
                            2. Verifique se existe uma ferramenta adequada
                            3. Confirme se TODOS os parâmetros obrigatórios existem
                            4. Se faltar algo, faça uma PERGUNTA curta e objetiva
                            5. Só chame ferramentas quando tiver todos os dados

                            Nunca invente informações.
                        """

        self.AGENT_PROFILE = """
                            Você é um atendente brasileiro que conversa pelo WhatsApp.
                            Fala de forma simples, educada e natural.
                            Age como um humano real, não como um sistema.
                        """

        self.RESPONSE_PROMPT = """
                                Você está respondendo um usuário no WhatsApp.

                                REGRAS DE RESPOSTA:
                                - Máximo de 600 caracteres
                                - Tom simpático, direto e natural
                                - Linguagem simples, sem formalidade excessiva
                                - Uma ideia principal por mensagem
                                - Nada de listas, markdown ou textos longos

                                Se não souber algo, admita.
                                Se precisar de dados, pergunte de forma simples.
                                Fale como alguém digitando no WhatsApp.

                                Antes de responder, confirme mentalmente que a mensagem cabe em um WhatsApp.

                        """
    
    def __build_decision_messages(self, context: ConversationContext) -> List[dict]:
        messages = [{"role": "system", "content": self.DECISION_PROMPT}]
        
        for msg in context.get_recent_messages(limit=20):
            messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return messages


    def __build_response_messages(self, context: ConversationContext) -> List[dict]:
        messages = [
            {"role": "system", "content": self.AGENT_PROFILE},
            {"role": "system", "content": self.RESPONSE_PROMPT},
        ]

        for msg in context.get_recent_messages(limit=20):
            messages.append({
                "role": msg.role,
                "content": msg.content
            })

        return messages


    def __get_or_create_context(self, sender_id: str) -> ConversationContext:
        """Pega ou cria contexto do usuário"""
        if sender_id not in self.contexts:
            self.contexts[sender_id] = ConversationContext(sender_id=sender_id)
        return self.contexts[sender_id]
    
    async def process_message(self, sender_id: str, message: str) -> ResponsePackageEntity:
        """
        Fluxo principal:
        1. Pega contexto do usuário
        2. Adiciona mensagem ao histórico
        3. LLM decide se precisa de tool
        4. Se sim: executa tool → manda resultado pro LLM
        5. Gera resposta natural
        """
        context = self.__get_or_create_context(sender_id)
        context.add_message("user", message)
        
        logger.info(f"Processando mensagem de {sender_id}: {message}")
        

        response_package = ResponsePackageEntity()

        # 1° chamada: LLM decide se precisa de tool
        decision_messages = self.__build_decision_messages(context)

        decision_response = await self.llm_client.chat(
            messages=decision_messages,
            tools=self.tool_executor.get_available_tools()
        )
        
        # Se LLM quer usar uma tool
        if decision_response.get("tool_calls"):
            tool_results = await self.tool_executor.execute_tools(
                decision_response["tool_calls"]
            )
            context.tool_results.extend(tool_results)

            # ✅ EXTRAI ARQUIVOS DOS RESULTADOS
            for result in tool_results:
                result_data = result.get("result", {})
                
                # Se a tool retornou um PDF
                if result_data.get("pdf_path"):
                    pdf_path = result_data["pdf_path"]
                    logger.info(f"[{sender_id}] PDF encontrado: {pdf_path}")
                    
                    response_package.add_document(
                        path=pdf_path,
                        caption="pdf"
                    )
            
            response_messages = self.__build_response_messages(context) 

            # Segunda chamada: LLM com resultados das tools
            response_messages.append({
                "role": "assistant",
                "content": decision_response.get("content"),
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": encode(tc["parameters"])
                        }
                    }
                    for tc in decision_response["tool_calls"]
                ]
            })

            # ✅ CORREÇÃO: Adiciona cada resultado com o tool_call_id correto
            for tc, result in zip(decision_response["tool_calls"], tool_results):
                response_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": encode(result)
                })
            
            # 🔹 2ª CHAMADA — FALA FINAL
            final_response = await self.llm_client.chat(messages=response_messages)
            answer = final_response["content"]
        else:
            # 🔹 NÃO PRECISA DE TOOL → RESPONDE DIRETO (MAS COM PROMPT DE FALA)
            response_messages = self.__build_response_messages(context)
            response_messages.append({
                "role": "assistant",
                "content": decision_response["content"]
            })

            final_response = await self.llm_client.chat(
                messages=response_messages
            )
            answer = final_response["content"]
        
        # ✅ Adiciona texto ao pacote
        response_package.text = answer
        context.add_message("assistant", answer)
        
        logger.info(f"[{sender_id}] Resposta preparada - texto: {bool(answer)}, mídias: {len(response_package.media_items)}")
        
        return response_package
    
    