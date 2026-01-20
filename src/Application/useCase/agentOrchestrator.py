import logging
import json
from typing import List, Any, Dict
from src.Domain import (
    ConversationContext,
    IToolExecutorService,
    IDecisionService,
    IOpenAiClient,
    IAgentPrompts,
    ResponsePackageEntity
)

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    def __init__(self, tool_excutor: IToolExecutorService, llm_client: IOpenAiClient, 
                 agentsPrompts: IAgentPrompts, decision_service: IDecisionService):
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
        flow_ctx = context.get_flow_context()
        tools_desc = self._get_available_tools_description()
        
        # Monta o prompt do sistema (SEM o histórico dentro)
        prompt = self.FLOW_DECISION_PROMPT.format(
            flow_context=flow_ctx,
            user_message=user_message,
            available_tools=tools_desc
        )
        
        # Inicia com o prompt do sistema
        messages = [{"role": "system", "content": prompt}]
        
        # 🔥 CORREÇÃO: Adiciona o histórico como MENSAGENS SEPARADAS
        for msg in context.get_recent_messages(limit=15):
            if msg.role in ["user", "assistant"]:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        return messages
            
    
    def __build_response_messages(
        self, 
        context: ConversationContext,
        decision: Dict[str, Any] = None,  # 🔥 ADICIONA decision
        tool_results: List[Dict[str, Any]] = None
    ) -> List[dict]:
        """Monta mensagens para geração de resposta - VERSÃO CORRIGIDA"""
        flow_ctx = context.get_flow_context()
        
        # Formata os resultados das tools de forma mais clara
        action_result = "Nenhuma ação executada ainda"
        if tool_results:
            formatted_results = []
            for result in tool_results:
                tool_name = result.get("tool", "unknown")
                result_data = result.get("result", {})
                
                formatted_results.append(
                    f"Ferramenta '{tool_name}' retornou:\n{json.dumps(result_data, ensure_ascii=False, indent=2)}"
                )
            action_result = "\n\n".join(formatted_results)
        
        # Monta o prompt do sistema com contexto completo
        system_prompt = self.RESPONSE_PROMPT.format(
            flow_context=flow_ctx,
            decision_context = decision,
            action_result=action_result
        )
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Adiciona o histórico de mensagens do usuário e assistente
        for msg in context.get_recent_messages(limit=10):
            # Ignora mensagens de sistema antigas para não poluir
            if msg.role in ["user", "assistant"]:
                messages.append({"role": msg.role, "content": msg.content})
        
        if tool_results:
            tool_summary = f"""
                                DADOS RETORNADOS PELA FERRAMENTA (USE ESTES DADOS NA SUA RESPOSTA):

                                {action_result}

                                Importante: Estes dados já foram obtidos com sucesso. Use-os para responder ao usuário.
                            """
            messages.append({"role": "system", "content": tool_summary})
        
        return messages
    
    def __get_or_create_context(self, sender_id: str) -> ConversationContext:
        if sender_id not in self.contexts:
            self.contexts[sender_id] = ConversationContext(sender_id=sender_id)
        return self.contexts[sender_id]
    
    async def process_message(self, sender_id: str, message: str):
        """Processa mensagem de forma genérica"""
        context = self.__get_or_create_context(sender_id)
        context.add_message("user", message)
        
        logger.info(f"[{sender_id}] 📨 Mensagem: {message}")
        
        response_package = ResponsePackageEntity()
        executed_tool_results = None  # Armazena os resultados para passar ao response
        
        # ========== 1. DECISÃO ==========
        decision_messages = self.__build_flow_decision_messages(context, message)
        
        decision_response = await self.llm_client.chat(
            messages=decision_messages,
            tools=self.tool_executor.get_available_tools()
        )

        decision = json.loads(decision_response.get("content", "{}"))
        
        logger.info(f"[{sender_id}] 🧠 Decisão: {decision.get('decision')} | Tool: {decision.get('tool_name')}")
        
        # ========== 2. ATUALIZA FLUXO ==========
        self.decision_service.apply_flow_state(decision, context, sender_id)        
        
        # ========== 3. EXECUTA TOOL ==========
        if decision.get("decision") == 'call_tool':
            tool_name = decision.get("tool_name")
            tool_params = decision.get("tool_params", {})
            
            if not tool_name:
                logger.error(f"[{sender_id}] ❌ action=call_tool mas tool_name vazio")
            else:
                self.decision_service.prepare_tool_params(tool_params, context)
                
                try:
                    # Executa a tool
                    tool_results = await self.tool_executor.execute_tools([{
                        "name": tool_name,
                        "parameters": tool_params
                    }])
                    
                    # Armazena para usar na resposta
                    executed_tool_results = tool_results
                    
                    # Armazena no contexto
                    context.tool_results.extend(tool_results)
                    
                    # Processa resultados (PDFs, imagens, etc)
                    self.decision_service.process_tool_outputs(
                        tool_results, 
                        context, 
                        response_package
                    )
                    
                    logger.info(f"[{sender_id}] ✅ Tool '{tool_name}' executada com sucesso")
                    logger.info(f"[{sender_id}] 📊 Resultados: {json.dumps(tool_results, ensure_ascii=False)[:500]}")
                
                except Exception as e:
                    logger.error(f"[{sender_id}] ❌ Erro na tool: {str(e)}")
                    # Cria um resultado de erro para o modelo entender
                    executed_tool_results = [{
                        "tool": tool_name,
                        "error": str(e)
                    }]
        
        # ========== 4. GERA RESPOSTA (COM CONTEXTO DOS RESULTADOS) ==========
        response_messages = self.__build_response_messages(context,decision, executed_tool_results)
        
        logger.info(f"[{sender_id}] 🔍 Mensagens enviadas para resposta: {len(response_messages)} mensagens")
        
        final_response = await self.llm_client.chat(messages=response_messages)
        
        answer = final_response["content"]
        
        # ========== 5. FINALIZAÇÃO ==========
        response_package.text = answer
        context.add_message("assistant", answer)
        
        logger.info(f"[{sender_id}] 💬 Resposta gerada: {answer[:300]}...")
        
        return response_package