import logging
from typing import Optional, Dict
from src.Domain import (
    IAgentConfigRepository,
    AgentConfigEntity
)

logger = logging.getLogger(__name__)


class AgentConfigService:
    """
    Serviço para gerenciar configurações de agentes.
    Implementa cache em memória para performance.
    """

    def __init__(self, agent_config_repo: IAgentConfigRepository):
        self.agent_config_repo = agent_config_repo
        self._cache: Dict[str, AgentConfigEntity] = {}
        self._default_agent: Optional[AgentConfigEntity] = None

    async def get_agent_for_phone(self, phone_number: str) -> AgentConfigEntity:
        """
        Retorna o agente configurado para um número de telefone.
        Se não encontrar, retorna o agente padrão.
        
        Args:
            phone_number: Número do WhatsApp (instance)
            
        Returns:
            AgentConfigEntity configurado para o número ou agente padrão
        """
        # Verifica cache primeiro
        if phone_number in self._cache:
            logger.info(f"[AgentConfig] ✅ Agente para '{phone_number}' encontrado no cache: {self._cache[phone_number].name}")
            return self._cache[phone_number]

        # Busca no banco
        try:
            agent = await self.agent_config_repo.get_by_phone_number(phone_number)
            
            if agent:
                # Armazena no cache
                self._cache[phone_number] = agent
                logger.info(f"[AgentConfig] ✅ Agente para '{phone_number}' carregado do DB: {agent.name}")
                return agent
            else:
                logger.warning(f"[AgentConfig] ⚠️ Nenhum agente mapeado para '{phone_number}', usando agente padrão")
                return await self.get_default_agent()
                
        except Exception as e:
            logger.error(f"[AgentConfig] ❌ Erro ao buscar agente para '{phone_number}': {e}")
            return await self.get_default_agent()

    async def get_default_agent(self) -> AgentConfigEntity:
        """
        Retorna o agente padrão (fallback).
        Se não houver agente padrão no banco, cria um em memória.
        
        Returns:
            AgentConfigEntity padrão
        """
        # Verifica cache
        if self._default_agent:
            return self._default_agent

        # Busca no banco
        try:
            agent = await self.agent_config_repo.get_default_agent()
            
            if agent:
                self._default_agent = agent
                logger.info(f"[AgentConfig] ✅ Agente padrão carregado: {agent.name}")
                return agent
            else:
                # Cria agente padrão em memória (fallback de emergência)
                logger.warning("[AgentConfig] ⚠️ Nenhum agente padrão no banco, criando fallback em memória")
                return self._create_fallback_agent()
                
        except Exception as e:
            logger.error(f"[AgentConfig] ❌ Erro ao buscar agente padrão: {e}")
            return self._create_fallback_agent()

    def _create_fallback_agent(self) -> AgentConfigEntity:
        """
        Cria um agente padrão em memória como último recurso.
        Este agente usa os prompts originais do sistema.
        """
        from src.Infrastructure import AgentPrompts
        
        prompts = AgentPrompts()
        
        fallback_agent = AgentConfigEntity(
            name="Assistente Padrão (Fallback)",
            description="Agente padrão criado automaticamente",
            personality="profissional e prestativo",
            flow_decision_prompt=prompts.get_flow_decision_prompt(),
            response_prompt=prompts.get_response_prompt(),
            available_tools=["buscar_informacao", "consultar_ipva"],  # Todas as tools disponíveis
            is_active=True
        )
        
        self._default_agent = fallback_agent
        logger.info("[AgentConfig] ✅ Agente fallback criado em memória")
        
        return fallback_agent

    def clear_cache(self):
        """Limpa o cache de agentes (útil para recarregar configurações)"""
        self._cache.clear()
        self._default_agent = None
        logger.info("[AgentConfig] 🔄 Cache de agentes limpo")

    async def reload_agent(self, phone_number: str):
        """Recarrega um agente específico do banco"""
        if phone_number in self._cache:
            del self._cache[phone_number]
        await self.get_agent_for_phone(phone_number)
