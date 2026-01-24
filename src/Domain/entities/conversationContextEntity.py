from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid
import json

@dataclass
class FlowIntent:
    """Representa um fluxo de intenção em andamento"""
    flow_id: str
    primary_intent: str
    sub_intent: Optional[str] = None
    
    # Estado
    status: str = "active"  # active | completed | abandoned
    current_step: str = "initiated"
    
    # Dados
    resolved_params: Dict = field(default_factory=dict)
    pending_params: List[str] = field(default_factory=list)
    
    # Metadados
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    ttl_seconds: int = 1800  # 30min
    
    def is_expired(self) -> bool:
        """Verifica se o fluxo expirou por inatividade"""
        elapsed = (datetime.now() - self.last_updated).total_seconds()
        return elapsed > self.ttl_seconds
    
    def update(self, **kwargs):
        """Atualiza campos e timestamp"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.last_updated = datetime.now()
    
    def add_resolved_param(self, key: str, value):
        """Adiciona parâmetro resolvido e remove de pending"""
        self.resolved_params[key] = value
        if key in self.pending_params:
            self.pending_params.remove(key)
        self.last_updated = datetime.now()
    
    def to_context_string(self) -> str:
        """Serializa para o prompt do LLM"""
        return f"""
Flow ID: {self.flow_id}
Intenção: {self.primary_intent}
Sub-intenção: {self.sub_intent or 'nenhuma'}
Status: {self.status}
Etapa Atual: {self.current_step}
Dados Resolvidos: {self.resolved_params}
Dados Pendentes: {self.pending_params}
"""


@dataclass
class Message:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DecisionRecord:
    """Registro de uma decisão tomada pelo agente"""
    decision: str  # call_tool, ask_user, reply, complete, new_flow
    tool_name: Optional[str] = None
    tool_params: Dict = field(default_factory=dict)
    reason: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    user_message: Optional[str] = None  # Mensagem que gerou esta decisão


class ConversationContext:
    """Contexto de conversa com gerenciamento de fluxo"""
    
    def __init__(self, sender_id: str):
        self.sender_id = sender_id
        self.messages: List[Message] = []
        self.tool_results: List[dict] = []
        
        # ✅ NOVO: gerenciamento de fluxo
        self.active_flow: Optional[FlowIntent] = None
        self.flow_history: List[FlowIntent] = []
        
        # ✅ NOVO: histórico de decisões
        self.decision_history: List[DecisionRecord] = []
    
    def add_message(self, role: str, content: str):
        """Adiciona mensagem ao histórico"""
        self.messages.append(Message(role=role, content=content))
    
    def get_recent_messages(self, limit: int = 20) -> List[Message]:
        """Retorna últimas N mensagens"""
        return self.messages[-limit:]
    
    # ========== GERENCIAMENTO DE FLUXO ==========
    
    def start_flow(self, primary_intent: str, pending_params: List[str] = None) -> FlowIntent:
        """Inicia um novo fluxo de intenção"""
        # Se já existe fluxo ativo, arquiva
        if self.active_flow:
            self.active_flow.status = "abandoned"
            self.flow_history.append(self.active_flow)
        
        # Cria novo fluxo
        self.active_flow = FlowIntent(
            flow_id=str(uuid.uuid4())[:8],
            primary_intent=primary_intent,
            pending_params=pending_params or []
        )
        return self.active_flow
    
    def continue_flow(self, **updates) -> Optional[FlowIntent]:
        """Continua o fluxo ativo com atualizações"""
        if not self.active_flow:
            return None
        
        # Verifica se expirou
        if self.active_flow.is_expired():
            self.active_flow.status = "abandoned"
            self.flow_history.append(self.active_flow)
            self.active_flow = None
            return None
        
        self.active_flow.update(**updates)
        return self.active_flow
    
    def complete_flow(self):
        """Marca o fluxo como completo"""
        if self.active_flow:
            self.active_flow.status = "completed"
            self.flow_history.append(self.active_flow)
            self.active_flow = None
    
    def get_flow_context(self) -> str:
        """Retorna contexto do fluxo para o prompt"""
        if not self.active_flow:
            return "Nenhum fluxo ativo no momento."
        return self.active_flow.to_context_string()
    
    def has_resolved_param(self, key: str) -> bool:
        """Verifica se um parâmetro já foi resolvido no fluxo"""
        if not self.active_flow:
            return False
        return key in self.active_flow.resolved_params
    
    def get_resolved_param(self, key: str, default=None):
        """Obtém parâmetro resolvido"""
        if not self.active_flow:
            return default
        return self.active_flow.resolved_params.get(key, default)
    
    # ========== GERENCIAMENTO DE DECISÕES ==========
    
    def add_decision(self, decision: str, tool_name: Optional[str] = None, 
                     tool_params: Dict = None, reason: Optional[str] = None,
                     user_message: Optional[str] = None):
        """Adiciona uma decisão ao histórico"""
        self.decision_history.append(
            DecisionRecord(
                decision=decision,
                tool_name=tool_name,
                tool_params=tool_params or {},
                reason=reason,
                user_message=user_message
            )
        )
    
    def get_recent_decisions(self, limit: int = 10) -> List[DecisionRecord]:
        """Retorna últimas N decisões"""
        return self.decision_history[-limit:]
    
    def get_decision_summary(self) -> str:
        """Retorna resumo das decisões recentes para o prompt"""
        if not self.decision_history:
            return "Nenhuma decisão anterior registrada."
        
        recent = self.get_recent_decisions(limit=5)
        summary_lines = []
        
        for idx, decision in enumerate(recent, 1):
            line = f"[{idx}] {decision.decision}"
            if decision.tool_name:
                line += f" → Tool: {decision.tool_name}"
            if decision.reason:
                line += f" (Razão: {decision.reason})"
            summary_lines.append(line)
        
        return "\n".join(summary_lines)
    
    # ========== SERIALIZAÇÃO PARA REDIS ==========
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializa o contexto para dicionário (para salvar no Redis)"""
        return {
            "sender_id": self.sender_id,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat()
                }
                for msg in self.messages
            ],
            "tool_results": self.tool_results,
            "active_flow": self._flow_to_dict(self.active_flow) if self.active_flow else None,
            "flow_history": [self._flow_to_dict(f) for f in self.flow_history],
            "decision_history": [
                {
                    "decision": d.decision,
                    "tool_name": d.tool_name,
                    "tool_params": d.tool_params,
                    "reason": d.reason,
                    "timestamp": d.timestamp.isoformat(),
                    "user_message": d.user_message
                }
                for d in self.decision_history
            ]
        }
    
    def _flow_to_dict(self, flow: FlowIntent) -> Dict[str, Any]:
        """Serializa um FlowIntent para dicionário"""
        if not flow:
            return None
        return {
            "flow_id": flow.flow_id,
            "primary_intent": flow.primary_intent,
            "sub_intent": flow.sub_intent,
            "status": flow.status,
            "current_step": flow.current_step,
            "resolved_params": flow.resolved_params,
            "pending_params": flow.pending_params,
            "created_at": flow.created_at.isoformat(),
            "last_updated": flow.last_updated.isoformat(),
            "ttl_seconds": flow.ttl_seconds
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationContext':
        """Deserializa um dicionário para ConversationContext"""
        context = cls(sender_id=data["sender_id"])
        
        # Restaura mensagens
        for msg_data in data.get("messages", []):
            context.messages.append(
                Message(
                    role=msg_data["role"],
                    content=msg_data["content"],
                    timestamp=datetime.fromisoformat(msg_data["timestamp"])
                )
            )
        
        # Restaura tool results
        context.tool_results = data.get("tool_results", [])
        
        # Restaura active flow
        if data.get("active_flow"):
            context.active_flow = cls._flow_from_dict(data["active_flow"])
        
        # Restaura flow history
        context.flow_history = [
            cls._flow_from_dict(f) for f in data.get("flow_history", [])
        ]
        
        # Restaura decision history
        for decision_data in data.get("decision_history", []):
            context.decision_history.append(
                DecisionRecord(
                    decision=decision_data["decision"],
                    tool_name=decision_data.get("tool_name"),
                    tool_params=decision_data.get("tool_params", {}),
                    reason=decision_data.get("reason"),
                    timestamp=datetime.fromisoformat(decision_data["timestamp"]),
                    user_message=decision_data.get("user_message")
                )
            )
        
        return context
    
    @classmethod
    def _flow_from_dict(cls, data: Dict[str, Any]) -> FlowIntent:
        """Deserializa um dicionário para FlowIntent"""
        return FlowIntent(
            flow_id=data["flow_id"],
            primary_intent=data["primary_intent"],
            sub_intent=data.get("sub_intent"),
            status=data["status"],
            current_step=data["current_step"],
            resolved_params=data.get("resolved_params", {}),
            pending_params=data.get("pending_params", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_updated=datetime.fromisoformat(data["last_updated"]),
            ttl_seconds=data.get("ttl_seconds", 1800)
        )