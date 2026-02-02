import logging
import json
from typing import List, Any, Dict
from src.Domain import ResponsePackageEntity,ConversationContext, AgentConfigEntity
from src.Tools import ExecutorTool

logger = logging.getLogger(__name__)

class AgentOrchestrator:
    def __init__(
                    self,
                    llm_client,
                    agent_config: AgentConfigEntity
                ):
        """
        Inicializa o orchestrator com configuração específica de um agente.
        
        Args:
            llm_client: Cliente LLM para fazer chamadas
            agent_config: Configuração do agente (prompts, tools, personalidade)
        """
        self.llm_client = llm_client
        self.agent_config = agent_config
        
        # Usa os prompts da configuração do agente
        self.FLOW_DECISION_PROMPT = agent_config.flow_decision_prompt
        self.RESPONSE_PROMPT = agent_config.response_prompt
        
        # Cria executor de tools com apenas as tools permitidas para este agente
        self.tool_executor = ExecutorTool(allowed_tools=agent_config.available_tools)
        
        logger.info(f"[AgentOrchestrator] ✅ Inicializado com agente: {agent_config.name}")
        logger.info(f"[AgentOrchestrator] 🔧 Tools disponíveis: {agent_config.available_tools}")
        
    def _get_available_tools_description(self) -> str:
        tools = self.tool_executor.get_available_tools()
        
        if not tools:
            return "Nenhuma ferramenta disponível no momento."
        
        descriptions = []
        descriptions.append("LISTA DE FERRAMENTAS DISPONÍVEIS (você SÓ pode usar estas):")
        descriptions.append("")

        for tool in tools:
            schema = tool.get("parameters", {})
            tool_name = tool.get("name", "unknown")
            tool_description = tool.get("description", "Sem descrição")
            
            descriptions.append(f"🔧 {tool_name}")
            descriptions.append(f"   Descrição: {tool_description}")
            
            if schema.get("required"):
                descriptions.append(f"   Parâmetros obrigatórios: {', '.join(schema.get('required', []))}")
            
            if schema.get("properties"):
                props = list(schema.get("properties", {}).keys())
                descriptions.append(f"   Parâmetros disponíveis: {', '.join(props)}")
            
            descriptions.append("")

        descriptions.append("⚠️ IMPORTANTE: Você SÓ pode oferecer funcionalidades que existem nesta lista!")
        descriptions.append("❌ NÃO invente ferramentas, canais de envio (email/SMS), ou funcionalidades não listadas!")
        
        return "\n".join(descriptions)

    def __build_flow_decision_messages(self, context, user_message,prompt:str):
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
        
        # 🔥 ADICIONAR: Histórico de decisões anteriores
        decision_history = ""
        if context.decision_history:
            recent_decisions = context.get_recent_decisions(limit=5)
            decision_lines = []
            for idx, decision in enumerate(recent_decisions, 1):
                line = f"[{idx}] Decisão: {decision.decision}"
                if decision.tool_name:
                    line += f" | Tool: {decision.tool_name}"
                if decision.reason:
                    line += f" | Razão: {decision.reason}"
                decision_lines.append(line)
            
            decision_history = f"""
                                    HISTÓRICO DE DECISÕES ANTERIORES:
                                    {chr(10).join(decision_lines)}

                                    IMPORTANTE: Use este histórico para manter consistência e evitar decisões repetitivas ou contraditórias.
                                    Analise o padrão das decisões anteriores para tomar a melhor decisão agora.
                                """
        
        prompt = self.FLOW_DECISION_PROMPT
        
        # 🔥 INJETAR MEMÓRIA E HISTÓRICO NO SYSTEM PROMPT
        context_parts = []
        if memory_context:
            context_parts.append(memory_context)
        if decision_history:
            context_parts.append(decision_history)
        
        full_prompt = f"{prompt}\n\n{chr(10).join(context_parts)}" if context_parts else prompt
        
        messages = [{"role": "system", "content": full_prompt}]
        state_payload = {
            "flow_context": flow_ctx,
            "user_message": user_message,
            "resolved_params": context.active_flow.resolved_params if context.active_flow else {},
            "decision_history": [
                {
                    "decision": d.decision,
                    "tool": d.tool_name,
                    "reason": d.reason
                }
                for d in context.get_recent_decisions(limit=5)
            ],
            "available_tools": tools_desc
        }

        state_system = f"ESTADO_ATUAL:\n{json.dumps(state_payload, ensure_ascii=False, indent=2)}"
        
        messages = [
            {"role": "system", "content": full_prompt},
            {"role": "system", "content": state_system},
        ]

        for msg in context.get_recent_messages(limit=20):
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
        
        # Obter descrição das ferramentas disponíveis
        available_tools_desc = self._get_available_tools_description()
        
        # Formatar decisão para o prompt (incluindo informação sobre complete)
        decision_context_str = json.dumps(decision, ensure_ascii=False, indent=2)
        if decision.get("decision") == "complete":
            decision_context_str += "\n\n⚠️ ATENÇÃO: O usuário está agradecendo/finalizando. Responda apenas com agradecimento breve, NÃO repita informações já fornecidas!"
        
        # Montar prompt com CONTEXTO COMPLETO
        system_prompt = self.RESPONSE_PROMPT
        messages = [{"role": "system", "content": system_prompt}]
        messages.append({
                            "role": "system",
                            "content": f"""
                                            ESTADO_DO_AGENTE:
                                            {json.dumps({
                                                "personal_context": self.agent_config.personality,
                                                "flow_context": flow_ctx,
                                                "decision": decision,
                                                "latest_tool_result": tool_results[0] if tool_results else None
                                            }, ensure_ascii=False, indent=2)}

                                            REGRAS:
                                            - Use o ESTADO_DO_AGENTE como fonte de verdade
                                            - NÃO peça dados já presentes em tool_history ou latest_tool_result
                                            - Se decision.decision == "complete", apenas agradeça brevemente
                                        """
                        })
        return messages
    
    def _apply_flow_state(self, decision: dict, context: ConversationContext, sender_id: str):
        action = decision.get("decision")
        
        if action == "new_flow":
            context.start_flow(decision.get("intent", "user_request"))
        
        elif action == "continue":
            if not context.active_flow:
                context.start_flow("user_request")
            
            # Atualiza parâmetros resolvidos
            updates = decision.get("resolved_params_update", {})
            for key, value in updates.items():
                context.active_flow.add_resolved_param(key, value)
            
            # Atualiza etapa do fluxo
            if next_step := decision.get("next_step"):
                context.active_flow.current_step = next_step
        
        elif action == "call_tool":
            # Garante que existe um flow ativo
            if not context.active_flow:
                context.start_flow("tool_execution")
            
            # Atualiza etapa
            if next_step := decision.get("next_step"):
                context.active_flow.current_step = next_step
            
            # 🔥 IMPORTANTE: Salva os tool_params no flow
            tool_params = decision.get("tool_params", {})
            for key, value in tool_params.items():
                if value and value != "":
                    context.active_flow.add_resolved_param(key, value)
                    # logger.info(f"[{sender_id}] ✅ Param '{key}' salvo no flow: {value}")
        
        elif action == "complete":
            context.complete_flow()
        
        return context
    
    def __prepare_tool_params(self, raw_params: Dict[str, Any], context: ConversationContext) -> Dict[str, Any]:
        """Lógica do seu antigo _fill_params_from_context"""
        if not context.active_flow:
            return raw_params
            
        resolved = context.active_flow.resolved_params
        filled = raw_params.copy()
        
        for key, value in filled.items():
            if (value is None or value == "") and key in resolved:
                filled[key] = resolved[key]
        return filled

    def __process_tool_outputs(self, tool_results: List[Dict[str, Any]], context: ConversationContext, package: ResponsePackageEntity):
        """Processa o retorno das Tools MCP e popula o pacote de resposta (Bloco 3 do seu código)"""
        for result in tool_results:
            result_data = result.get("result", {})
            
            # Atualiza contexto com novos dados da tool
            if context.active_flow:
                for key, value in result_data.items():
                    if key not in context.active_flow.resolved_params:
                        context.active_flow.add_resolved_param(key, value)
            
            # Extração de assets para o WhatsApp
            if pdf := result_data.get("pdf_path"):
                package.add_document(path=pdf, caption=result_data.get("pdf_caption", "Documento"))
                
            if img := result_data.get("image_path"):
                package.add_document(path=img, caption=result_data.get("image_caption", "Imagem"))

    async def process_message(self, context: ConversationContext, message: str):
        """Processa mensagem usando o contexto fornecido (já carregado do Redis)"""
        context.add_message("user", message)
        
        logger.info(f"[{context.sender_id}] 📨 Mensagem: {message}")
        
        response_package = ResponsePackageEntity()
        executed_tool_results = None  # Armazena os resultados para passar ao response
        
        # ========== 1. DECISÃO ==========
        decision_messages = self.__build_flow_decision_messages(context, message,self.agent_config.flow_decision_prompt)
        
        decision_response = await self.llm_client.chat(
            messages=decision_messages,
            tools=self.tool_executor.get_available_tools()
        )

        decision = json.loads(decision_response.get("content", "{}"))
    
        
        logger.info(f"[{context.sender_id}] 🧠 Decisão: {decision.get('decision')} | Tool: {decision.get('tool_name')}")
        
        # ========== 2. SALVA DECISÃO NO HISTÓRICO ==========
        context.add_decision(
            decision=decision.get("decision", "unknown"),
            tool_name=decision.get("tool_name"),
            tool_params=decision.get("tool_params", {}),
            reason=decision.get("reason"),
            user_message=message
        )
        
        # ========== 3. ATUALIZA FLUXO ==========
        context = self._apply_flow_state(decision, context, context.sender_id)        
        
        # ========== 4. EXECUTA TOOL ==========
        if decision.get("decision") == 'call_tool':
            tool_name = decision.get("tool_name")
            tool_params = decision.get("tool_params", {})
            
            if not tool_name:
                logger.error(f"[{context.sender_id}] ❌ action=call_tool mas tool_name vazio")
            else:
                filled = self.__prepare_tool_params(tool_params, context)
                
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
                    self.__process_tool_outputs(
                        tool_results, 
                        context, 
                        response_package
                    )
                    
                    logger.info(f"[{context.sender_id}] ✅ Tool '{tool_name}' executada com sucesso")
                    logger.info(f"[{context.sender_id}] 📊 Resultados: {json.dumps(tool_results, ensure_ascii=False)[:500]}")
                
                except Exception as e:
                    logger.error(f"[{context.sender_id}] ❌ Erro na tool: {str(e)}")
                    # Cria um resultado de erro para o modelo entender
                    executed_tool_results = [{
                        "tool": tool_name,
                        "error": str(e)
                    }]
        
        # ========== 5. GERA RESPOSTA (COM CONTEXTO DOS RESULTADOS) ==========
        response_messages = self.__build_response_messages(context,decision, executed_tool_results)
        
        logger.info(f"[{context.sender_id}] 🔍 Mensagens enviadas para resposta: {len(response_messages)} mensagens")
        
        final_response = await self.llm_client.chat(messages=response_messages)
        
        answer = final_response["content"]
        
        # ========== 6. FINALIZAÇÃO ==========
        response_package.text = answer
        context.add_message("assistant", answer)
        
        logger.info(f"[{context.sender_id}] 💬 Resposta gerada: {answer[:300]}...")
        
        return response_package