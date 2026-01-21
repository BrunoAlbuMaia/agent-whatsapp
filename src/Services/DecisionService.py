from typing import List,Dict,Any

from src.Domain import ConversationContext,ResponsePackageEntity,IDecisionService



class DecisionService(IDecisionService):
    def apply_flow_state(self, decision: dict, context: ConversationContext, sender_id: str):
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
    
    def prepare_tool_params(self, raw_params: Dict[str, Any], context: ConversationContext) -> Dict[str, Any]:
        """Lógica do seu antigo _fill_params_from_context"""
        if not context.active_flow:
            return raw_params
            
        resolved = context.active_flow.resolved_params
        filled = raw_params.copy()
        
        for key, value in filled.items():
            if (value is None or value == "") and key in resolved:
                filled[key] = resolved[key]
        return filled

    def process_tool_outputs(self, tool_results: List[Dict[str, Any]], context: ConversationContext, package: ResponsePackageEntity):
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