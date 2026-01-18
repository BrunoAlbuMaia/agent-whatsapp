import logging
import json
from typing import List, Optional,Any,Dict
from src.Domain import (
                            ConversationContext,
                            IAgentOrchestratorService,
                            ResponsePackageEntity
                        )
from toon import encode
from .toolExecutorService import ToolExecutor
from src.Infrastructure import OpenAIClient
# from .responseGenerator import ResponseGenerator

logger = logging.getLogger(__name__)

class AgentOrchestratorService:
    def __init__(self):
        self.llm_client = OpenAIClient()
        self.tool_executor = ToolExecutor()
        self.contexts: dict[str, ConversationContext] = {}
        
        self.FLOW_DECISION_PROMPT = """
Você é um agente de decisão de fluxos transacionais.

## CONTEXTO ATUAL DO FLUXO
{flow_context}

## HISTÓRICO RECENTE
{recent_messages}

## ÚLTIMA MENSAGEM DO USUÁRIO
{user_message}

## FERRAMENTAS DISPONÍVEIS
{available_tools}

---

RESPONDA **SOMENTE** COM JSON NO FORMATO:

{{
  "flow_decision": "continue | new_flow | complete | reply",
  "reasoning": "por que essa decisão",
  "action": "call_tool | ask_user | reply",
  "tool_name": "nome da tool (se action=call_tool)",
  "tool_params": {{}},
  "resolved_params_update": {{}},
  "next_step": "próxima etapa do fluxo"
}}

## REGRAS

1. **Quando chamar tools:**
   - Usuário pediu uma ação que requer dados externos
   - Você tem todos os parâmetros necessários
   - Exemplo: usuário forneceu placa+renavam → chame a tool de consulta

2. **Quando pedir ao usuário:**
   - Faltam parâmetros obrigatórios para a tool
   - Usuário não especificou algo importante

3. **Quando apenas responder:**
   - Conversação casual
   - Confirmação de algo já feito
   - Esclarecimento

4. **Use resolved_params_update para extrair dados da mensagem**
   - Se usuário disse "placa ABC1234", adicione: {{"placa": "ABC1234"}}
   - Se disse "primeira parcela", adicione: {{"parcela": 1}}

5. **NUNCA invente dados**
   - Se não sabe um parâmetro, deixe vazio
   - A tool vai validar e retornar erro se necessário

6. **Continue fluxos existentes:**
   - Se há fluxo ativo e usuário está respondendo no contexto, use "continue"
   - Se mudou completamente de assunto, use "new_flow"
"""

        self.RESPONSE_PROMPT = """
Você responde no WhatsApp de forma natural e direta.

## CONTEXTO DO FLUXO
{flow_context}

## RESULTADO DA ÚLTIMA AÇÃO
{action_result}

---

INSTRUÇÕES:

- Máximo 600 caracteres
- Tom natural de WhatsApp
- Se acabou de executar uma ferramenta, use os resultados para responder
- Se dados estão faltando, peça naturalmente
- Não repita informações que o usuário já deu

**REGRA CRÍTICA**: 
- Se você executou uma ferramenta com sucesso, COMUNIQUE o resultado
- Não pergunte se o usuário quer algo que você acabou de fazer
- Exemplo: se gerou Pix, diga "Pronto, enviei o Pix!", não "Quer que eu gere?"
- Nunca diga, que já já vai enviar, pergunte o que ele realmente precisa e EXECUTE

Fale como alguém digitando no WhatsApp.
"""
    
    def _get_available_tools_description(self) -> str:
        """Retorna descrição legível das tools disponíveis"""
        tools = self.tool_executor.get_available_tools()
        
        descriptions = []
        for tool in tools:
            descriptions.append(f"- {tool['name']}: {tool['description']}")
        
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
    
    def _fill_params_from_context(
        self, 
        tool_params: Dict[str, Any],
        resolved_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Preenche parâmetros vazios/None com valores do contexto
        """
        filled = tool_params.copy()
        
        for key, value in filled.items():
            # Se o parâmetro está vazio e existe no contexto, usa do contexto
            if value is None or value == "":
                if key in resolved_params:
                    filled[key] = resolved_params[key]
        
        return filled
    
    async def process_message(self, sender_id: str, message: str):
        """Processa mensagem de forma genérica"""
        
        context = self.__get_or_create_context(sender_id)
        context.add_message("user", message)
        
        logger.info(f"[{sender_id}] 📨 Mensagem: {message}")
        
        # ✅ Detecta início de fluxo (genérico)
        if self._should_start_flow(message, context):
            context.start_flow("user_request")
            logger.info(f"[{sender_id}] 🆕 Fluxo iniciado")
        
        if context.active_flow:
            logger.info(f"[{sender_id}] 📊 Flow: {context.active_flow.primary_intent} | Step: {context.active_flow.current_step}")
        
        response_package = ResponsePackageEntity()
        
        # ========== 1. DECISÃO ==========
        decision_messages = self.__build_flow_decision_messages(context, message)
        
        decision_response = await self.llm_client.chat(
            messages=decision_messages,
            tools=None  # Não usa function calling aqui, só JSON
        )
        
        try:
            decision = json.loads(decision_response.get("content", "{}"))
        except json.JSONDecodeError:
            logger.error(f"[{sender_id}] ❌ Decisão inválida: {decision_response.get('content')}")
            decision = {"flow_decision": "reply", "action": "reply"}
        
        logger.info(f"[{sender_id}] 🧠 Decisão: {decision.get('flow_decision')} | Ação: {decision.get('action')}")
        
        # ========== 2. ATUALIZA FLUXO ==========
        
        if decision["flow_decision"] == "new_flow":
            context.start_flow(decision.get("intent", "user_request"))
            logger.info(f"[{sender_id}] 🆕 Novo fluxo iniciado")
        
        elif decision["flow_decision"] == "continue":
            if not context.active_flow:
                context.start_flow("user_request")
            
            # ✅ GENÉRICO: atualiza qualquer parâmetro que o LLM extraiu
            updates = decision.get("resolved_params_update", {})
            for key, value in updates.items():
                context.active_flow.add_resolved_param(key, value)
                logger.info(f"[{sender_id}] ✅ Param: {key} = {value}")
            
            # ✅ Atualiza step se LLM especificou
            next_step = decision.get("next_step")
            if next_step:
                context.active_flow.current_step = next_step
                logger.info(f"[{sender_id}] 📍 Step: {next_step}")
        
        elif decision["flow_decision"] == "complete":
            context.complete_flow()
            logger.info(f"[{sender_id}] ✅ Fluxo completo")
        
        # ========== 3. EXECUTA TOOL (GENÉRICO) ==========
        
        action_result = "Nenhuma ação executada"
        
        if decision.get("action") == "call_tool":
            tool_name = decision.get("tool_name")
            tool_params = decision.get("tool_params", {})
            
            if not tool_name:
                logger.error(f"[{sender_id}] ❌ action=call_tool mas tool_name vazio")
            else:
                # ✅ PREENCHE PARAMS DO CONTEXTO (genérico)
                if context.active_flow:
                    tool_params = self._fill_params_from_context(
                        tool_params,
                        context.active_flow.resolved_params
                    )
                
                logger.info(f"[{sender_id}] 🔧 Executando: {tool_name}")
                logger.info(f"[{sender_id}] 📋 Params: {tool_params}")
                
                try:
                    # ✅ EXECUTA A TOOL
                    tool_results = await self.tool_executor.execute_tools([{
                        "name": tool_name,
                        "parameters": tool_params
                    }])
                    
                    context.tool_results.extend(tool_results)
                    
                    # ✅ PROCESSA RESULTADOS (GENÉRICO)
                    for result in tool_results:
                        result_data = result.get("result", {})
                        
                        logger.info(f"[{sender_id}] 📦 Result keys: {list(result_data.keys())}")
                        
                        # ✅ GENÉRICO: salva tudo que a tool retornou
                        if context.active_flow:
                            for key, value in result_data.items():
                                # Não sobrescreve parâmetros já definidos
                                if key not in context.active_flow.resolved_params:
                                    context.active_flow.add_resolved_param(key, value)
                        
                        # ✅ Extrai arquivos (PDF, imagens, etc)
                        if result_data.get("pdf_path"):
                            response_package.add_document(
                                path=result_data["pdf_path"],
                                caption=result_data.get("pdf_caption", "Documento")
                            )
                            logger.info(f"[{sender_id}] 📄 PDF: {result_data['pdf_path']}")
                        
                        if result_data.get("image_path"):
                            response_package.add_document(
                                path=result_data["image_path"],
                                caption=result_data.get("image_caption", "Imagem")
                            )
                    
                    action_result = f"Tool '{tool_name}' executada com sucesso. Resultados: {json.dumps(tool_results, ensure_ascii=False)}"
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
        
        logger.info(f"[{sender_id}] 💬 Resposta: {answer[:100]}...")
        
        return response_package