from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict
import uuid

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


class ConversationContext:
    """Contexto de conversa com gerenciamento de fluxo"""
    
    def __init__(self, sender_id: str):
        self.sender_id = sender_id
        self.messages: List[Message] = []
        self.tool_results: List[dict] = []
        
        # ✅ NOVO: gerenciamento de fluxo
        self.active_flow: Optional[FlowIntent] = None
        self.flow_history: List[FlowIntent] = []
    
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