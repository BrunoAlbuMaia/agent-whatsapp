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

    def __build_flow_decision_messages(self, context, user_message):
        flow_ctx = context.get_flow_context()
        tools_desc = self._get_available_tools_description()
        
        # 🔥 ADICIONAR: Resumo dos dados já coletados
        memory_context = ""
        if context.active_flow and context.active_flow.resolved_params:
            memory_context = f"""
                                    DADOS JÁ COLETADOS NESTA CONVERSA:
                                    {json.dumps(context.active_flow.resolved_params, ensure_ascii=False, indent=2)}

                                    IMPORTANTE: Estes dados já foram fornecidos pelo usuário anteriormente. 
                                    NÃO peça novamente a menos que seja estritamente necessário.
                                """
        
        prompt = self.FLOW_DECISION_PROMPT.format(
            flow_context=flow_ctx,
            user_message=user_message,
            available_tools=tools_desc
        )
        
        # 🔥 INJETAR MEMÓRIA NO SYSTEM PROMPT
        full_prompt = f"{prompt}\n\n{memory_context}" if memory_context else prompt
        
        messages = [{"role": "system", "content": full_prompt}]
        
        # Aumentar limite OU usar todas as mensagens
        for msg in context.get_recent_messages(limit=30):  # ⬆️ Aumentar pra 30
            messages.append({"role": msg.role, "content": msg.content})
        
        return messages
            
    
    def __build_response_messages(self, context, decision, tool_results):
        flow_ctx = context.get_flow_context()
        
        # 🔥 USAR HISTÓRICO COMPLETO DE TOOLS
        all_tools_history = context.tool_results  # Histórico completo
        
        # Formatar TODAS as tools executadas (últimas 5)
        if all_tools_history:
            recent_tools = all_tools_history[-5:]  # Últimas 5 execuções
            formatted_history = []
            
            for idx, result in enumerate(recent_tools, 1):
                tool_name = result.get("tool", "unknown")
                result_data = result.get("result", {})
                
                formatted_history.append(
                    f"[Execução #{idx}] Ferramenta '{tool_name}':\n{json.dumps(result_data, ensure_ascii=False, indent=2)}"
                )
            
            tools_summary = "\n\n".join(formatted_history)
        else:
            tools_summary = "Nenhuma ferramenta executada ainda"
        
        # 🔥 DESTACAR A TOOL ATUAL (se houver)
        current_tool_result = ""
        if tool_results:
            current_tool_result =  f"""
                                        🆕 RESULTADO DA ÚLTIMA EXECUÇÃO:
                                        {json.dumps(tool_results[0], ensure_ascii=False, indent=2)}
                                    """
        
        # Montar prompt com CONTEXTO COMPLETO
        system_prompt = self.RESPONSE_PROMPT.format(
            flow_context=flow_ctx,
            decision_context=decision,
            action_result=tools_summary  # Histórico completo
        )
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Adicionar histórico de mensagens
        for msg in context.get_recent_messages(limit=20):  # ⬆️ Aumentar limite
            if msg.role in ["user", "assistant"]:
                messages.append({"role": msg.role, "content": msg.content})
        
        # 🔥 ADICIONAR RESUMO DE TOOLS COMO MENSAGEM SYSTEM
        if all_tools_history:
            messages.append({
                "role": "system", 
                "content": f"""
                                📊 HISTÓRICO DE FERRAMENTAS EXECUTADAS:
                                {tools_summary}

                                {current_tool_result}

                                IMPORTANTE: Use estes dados para responder ao usuário. Não peça informações que já foram obtidas.
                            """
            })
        
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