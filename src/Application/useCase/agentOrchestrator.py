import logging
import json
from typing import List,Any,Dict
from src.Domain import (
                            ConversationContext,
                            IToolExecutorService,
                            IDecisionService,
                            IOpenAiClient,
                            IAgentPrompts,
                            ResponsePackageEntity
                        )
                        
from toon import encode
logger = logging.getLogger(__name__)

class AgentOrchestrator:
    def __init__(self,tool_excutor:IToolExecutorService,llm_client:IOpenAiClient,agentsPrompts:IAgentPrompts,decision_service:IDecisionService):
        self.llm_client = llm_client
        self.tool_executor = tool_excutor
        self.decision_service = decision_service
        self.contexts: dict[str, ConversationContext] = {}
        
        self.FLOW_DECISION_PROMPT = agentsPrompts.get_flow_decision_prompt()
        self.RESPONSE_PROMPT = agentsPrompts.get_response_prompt()
        
    def _get_available_tools_description(self) -> str:
        tools = self.tool_executor.get_available_tools()
        descriptions = []

        for tool in tools:
            schema = tool["parameters"]
            descriptions.append(
                f"""
                    Tool: {tool['name']}
                    Required params: {schema.get('required', [])}
                    Properties: {list(schema.get('properties', {}).keys())}
                """
            )

        return "\n".join(descriptions)

    def __build_flow_decision_messages(
        self, 
        context: ConversationContext, 
        user_message: str
    ) -> List[dict]:
        """Monta mensagens para decisão de fluxo"""
        flow_ctx = context.get_flow_context()
        tools_desc = self._get_available_tools_description()
        
        recent = "\n".join([
            f"{msg.role}: {msg.content}" 
            for msg in context.get_recent_messages(limit=5)
        ])
        
        prompt = self.FLOW_DECISION_PROMPT.format(
            flow_context=flow_ctx,
            recent_messages=recent,
            user_message=user_message,
            available_tools=tools_desc
        )
        
        return [{"role": "system", "content": prompt}]
    
    def __build_response_messages(
        self, 
        context: ConversationContext,
        action_result: str = "Nenhuma ação executada ainda"
    ) -> List[dict]:
        """Monta mensagens para geração de resposta"""
        flow_ctx = context.get_flow_context()
        
        messages = [
            {
                "role": "system", 
                "content": self.RESPONSE_PROMPT.format(
                    flow_context=flow_ctx,
                    action_result=action_result
                )
            }
        ]
        
        for msg in context.get_recent_messages(limit=15):
            messages.append({"role": msg.role, "content": msg.content})
        
        return messages
    
    def __get_or_create_context(self, sender_id: str) -> ConversationContext:
        if sender_id not in self.contexts:
            self.contexts[sender_id] = ConversationContext(sender_id=sender_id)
        return self.contexts[sender_id]
    
    def _should_start_flow(self, message: str, context: ConversationContext) -> bool:
        """
        Heurística simples: se usuário pede algo que não é só conversa,
        inicia fluxo genérico
        """
        if context.active_flow:
            return False
        
        # Keywords que indicam pedido de serviço
        service_keywords = [
            "quero", "preciso", "pode", "me ajuda", "gostaria",
            "emitir", "gerar", "consultar", "verificar", "pagar"
        ]
        
        message_lower = message.lower()
        return any(kw in message_lower for kw in service_keywords)
    
    
    
    async def process_message(self, sender_id: str, message: str):
        """Processa mensagem de forma genérica"""
        context = self.__get_or_create_context(sender_id)
        context.add_message("user", message)
        
        logger.info(f"[{sender_id}] 📨 Mensagem: {message}")
        
        # # ✅ Detecta início de fluxo (genérico)
        # if self._should_start_flow(message, context):
        #     context.start_flow("user_request")
        #     logger.info(f"[{sender_id}] 🆕 Fluxo iniciado")
        
        # if context.active_flow:
        #     logger.info(f"[{sender_id}] 📊 Flow: {context.active_flow.primary_intent} | Step: {context.active_flow.current_step}")
        
        response_package = ResponsePackageEntity()
        
        # ========== 1. DECISÃO ==========
        decision_messages = self.__build_flow_decision_messages(context, message)
        
        decision_response = await self.llm_client.chat(
            messages=decision_messages,
            tools= self.tool_executor.get_available_tools()
        )

        decision = json.loads(decision_response.get("content", "{}"))
        
        logger.info(f"[{sender_id}] 🧠 Decisão: {decision.get('flow_decision')} | Ação: {decision.get('action')}")
        
        # ========== 2. ATUALIZA FLUXO ==========
        self.decision_service.apply_flow_state(decision,context,sender_id)        
        
        # ========== 3. EXECUTA TOOL (GENÉRICO) ==========
        action_result = "Nenhuma ação executada"
        if decision.get("decision") == 'call_tool':
            tool_name = decision.get("tool_name")
            tool_params = decision.get("tool_params", {})
            
            if not tool_name:
                logger.error(f"[{sender_id}] ❌ action=call_tool mas tool_name vazio")
            else:
                self.decision_service.prepare_tool_params(
                                                            tool_params,
                                                            context
                                                        )
                try:
                    # ✅ EXECUTA A TOOL
                    tool_results = await self.tool_executor.execute_tools([{
                        "name": tool_name,
                        "parameters": tool_params
                    }])
                    
                    context.tool_results.extend(tool_results)
                    
                    # ✅ PROCESSA RESULTADOS (GENÉRICO)
                    action_result = f"Tool '{tool_name}' executada com sucesso. Resultados: {json.dumps(tool_results, ensure_ascii=False)}"
                    self.decision_service.process_tool_outputs(tool_results,context,response_package)
                    logger.info(f"[{sender_id}] ✅ Tool executada")
                
                except Exception as e:
                    logger.error(f"[{sender_id}] ❌ Erro na tool: {str(e)}")
                    action_result = f"Erro ao executar '{tool_name}': {str(e)}"
        
        # ========== 4. GERA RESPOSTA ==========
        response_messages = self.__build_response_messages(context, action_result)
        final_response = await self.llm_client.chat(messages=response_messages)
        
        answer = final_response["content"]
        
        # ========== 5. FINALIZAÇÃO ==========
        
        response_package.text = answer
        context.add_message("assistant", answer)
        
        logger.info(f"[{sender_id}] 💬 Resposta: {answer[:600]}...")
        
        return response_package