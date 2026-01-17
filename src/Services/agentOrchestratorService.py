import logging
import json
from typing import List, Optional
from src.Domain import ConversationContext,IAgentOrchestratorService,ResponsePackageEntity

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
    
    def __build_messages(self, context: ConversationContext) -> List[dict]:
        """Monta histórico de mensagens pro LLM"""
        system_prompt  = """Você é um assistente virtual brasileiro no WhatsApp.

                            COMPORTAMENTO:
                            - Converse de forma natural, como um humano
                            - Use português do Brasil coloquial
                            - Seja direto e objetivo nas respostas
                            - Não use formatação markdown excessiva
                            - Evite listas e bullet points, prefira texto corrido

                            LÓGICA DE EXECUÇÃO:
                            1. Analise o que o usuário quer
                            2. Identifique qual ferramenta (tool) pode resolver
                            3. Verifique se você tem TODOS os parâmetros obrigatórios
                            4. Se faltar algum parâmetro: PERGUNTE de forma natural
                            5. Só execute a ferramenta quando tiver TUDO que precisa
                            6. Após executar, apresente o resultado de forma clara
                            7. Se o resultado gerar novas opções, apresente e aguarde escolha do usuário

                            REGRAS CRÍTICAS:
                            - NUNCA execute uma ferramenta sem todos os parâmetros obrigatórios
                            - NUNCA invente dados que o usuário não forneceu
                            - Se tiver dúvida sobre o que fazer, pergunte ao usuário
                            - Mantenha o contexto da conversa anterior
                            - Seja proativo mas não invasivo

                            Você tem acesso a ferramentas que te ajudam a executar tarefas. Use-as quando apropriado.
                        """
    
        messages = [{"role": "system", "content": system_prompt }]
        
        # Histórico recente (20 mensagens = ~10 turnos de conversa)
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
        
        # Monta prompt com histórico
        messages = self.__build_messages(context)

        response_package = ResponsePackageEntity()

        # Primeira chamada: LLM decide se precisa de tool
        response = await self.llm_client.chat(
            messages=messages,
            tools=self.tool_executor.get_available_tools()
        )
        
        # Se LLM quer usar uma tool
        if response.get("tool_calls"):
            tool_results = await self.tool_executor.execute_tools(
                response["tool_calls"]
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
            
            # Segunda chamada: LLM com resultados das tools
            messages.append({
                "role": "assistant",
                "content": response.get("content"),
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["parameters"], ensure_ascii=False)
                        }
                    }
                    for tc in response["tool_calls"]
                ]
            })

            # ✅ CORREÇÃO: Adiciona cada resultado com o tool_call_id correto
            for tc, result in zip(response["tool_calls"], tool_results):
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result, ensure_ascii=False)
                })
            
            # Segunda chamada ao LLM com os resultados
            final_response = await self.llm_client.chat(messages=messages)
            answer = final_response["content"]
        else:
            # Não precisa de tool, responde direto
            answer = response["content"]
        
        # ✅ Adiciona texto ao pacote
        response_package.text = answer
        
        context.add_message("assistant", answer)
        
        logger.info(f"[{sender_id}] Resposta preparada - texto: {bool(answer)}, mídias: {len(response_package.media_items)}")
        
        return response_package
    
    