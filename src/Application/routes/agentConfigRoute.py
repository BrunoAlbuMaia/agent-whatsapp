from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel, Field
from uuid import UUID
import logging

from src.Application.dependecie import Dependecie

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["Agent Management"])
dependencies = Dependecie()


# ========== DTOs (Data Transfer Objects) ==========

class AgentConfigCreateDTO(BaseModel):
    """DTO para criar novo agente"""
    name: str = Field(..., min_length=1, max_length=100, description="Nome do agente")
    description: str = Field(..., description="Descrição do agente")
    personality: str = Field(..., max_length=50, description="Personalidade (ex: profissional, persuasivo)")
    flow_decision_prompt: str = Field(..., description="Prompt para decisões de fluxo")
    response_prompt: str = Field(..., description="Prompt para respostas")
    available_tools: List[str] = Field(default_factory=list, description="Lista de tools permitidas")
    is_active: bool = Field(default=True, description="Se o agente está ativo")


class AgentConfigUpdateDTO(BaseModel):
    """DTO para atualizar agente existente"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    personality: Optional[str] = Field(None, max_length=50)
    flow_decision_prompt: Optional[str] = None
    response_prompt: Optional[str] = None
    available_tools: Optional[List[str]] = None
    is_active: Optional[bool] = None


class AgentConfigResponseDTO(BaseModel):
    """DTO para resposta de agente"""
    id: str
    name: str
    description: str
    personality: str
    available_tools: List[str]
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class PhoneMappingCreateDTO(BaseModel):
    """DTO para criar mapeamento de número"""
    phone_number: str = Field(..., description="Número do WhatsApp (instance)")
    agent_id: str = Field(..., description="ID do agente")


class PhoneMappingResponseDTO(BaseModel):
    """DTO para resposta de mapeamento"""
    id: str
    phone_number: str
    agent_id: str
    is_active: bool
    created_at: str


# ========== ENDPOINTS DE AGENTES ==========

@router.get("/", response_model=List[AgentConfigResponseDTO])
async def list_agents(active_only: bool = True):
    """
    Lista todos os agentes.
    
    - **active_only**: Se True, retorna apenas agentes ativos
    """
    try:
        repo = dependencies.agentConfigRepository()
        
        if active_only:
            agents = await repo.list_active()
        else:
            # TODO: Implementar list_all no repositório se necessário
            agents = await repo.list_active()
        
        return [
            AgentConfigResponseDTO(
                id=str(agent.id),
                name=agent.name,
                description=agent.description,
                personality=agent.personality,
                available_tools=agent.available_tools,
                is_active=agent.is_active,
                created_at=agent.created_at.isoformat(),
                updated_at=agent.updated_at.isoformat()
            )
            for agent in agents
        ]
    except Exception as e:
        logger.error(f"Erro ao listar agentes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar agentes: {str(e)}"
        )


@router.get("/{agent_id}", response_model=AgentConfigResponseDTO)
async def get_agent(agent_id: str):
    """
    Busca um agente específico por ID.
    """
    try:
        repo = dependencies.agentConfigRepository()
        agent = await repo.get_by_id(UUID(agent_id))
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agente com ID {agent_id} não encontrado"
            )
        
        return AgentConfigResponseDTO(
            id=str(agent.id),
            name=agent.name,
            description=agent.description,
            personality=agent.personality,
            available_tools=agent.available_tools,
            is_active=agent.is_active,
            created_at=agent.created_at.isoformat(),
            updated_at=agent.updated_at.isoformat()
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID inválido"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar agente: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar agente: {str(e)}"
        )


@router.post("/", response_model=AgentConfigResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_agent(agent_data: AgentConfigCreateDTO):
    """
    Cria um novo agente.
    """
    try:
        from src.Domain import AgentConfigEntity
        
        repo = dependencies.agentConfigRepository()
        config_service = dependencies.agentConfigService()
        
        # Cria entidade
        agent = AgentConfigEntity(
            name=agent_data.name,
            description=agent_data.description,
            personality=agent_data.personality,
            flow_decision_prompt=agent_data.flow_decision_prompt,
            response_prompt=agent_data.response_prompt,
            available_tools=agent_data.available_tools,
            is_active=agent_data.is_active
        )
        
        # Salva no banco
        created_agent = await repo.create(agent)
        
        # Limpa cache para forçar reload
        config_service.clear_cache()
        
        logger.info(f"✅ Agente '{created_agent.name}' criado com sucesso (ID: {created_agent.id})")
        
        return AgentConfigResponseDTO(
            id=str(created_agent.id),
            name=created_agent.name,
            description=created_agent.description,
            personality=created_agent.personality,
            available_tools=created_agent.available_tools,
            is_active=created_agent.is_active,
            created_at=created_agent.created_at.isoformat(),
            updated_at=created_agent.updated_at.isoformat()
        )
    except Exception as e:
        logger.error(f"Erro ao criar agente: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar agente: {str(e)}"
        )


@router.put("/{agent_id}", response_model=AgentConfigResponseDTO)
async def update_agent(agent_id: str, agent_data: AgentConfigUpdateDTO):
    """
    Atualiza um agente existente.
    Apenas os campos fornecidos serão atualizados.
    """
    try:
        repo = dependencies.agentConfigRepository()
        config_service = dependencies.agentConfigService()
        
        # Busca agente existente
        agent = await repo.get_by_id(UUID(agent_id))
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agente com ID {agent_id} não encontrado"
            )
        
        # Atualiza apenas campos fornecidos
        if agent_data.name is not None:
            agent.name = agent_data.name
        if agent_data.description is not None:
            agent.description = agent_data.description
        if agent_data.personality is not None:
            agent.personality = agent_data.personality
        if agent_data.flow_decision_prompt is not None:
            agent.flow_decision_prompt = agent_data.flow_decision_prompt
        if agent_data.response_prompt is not None:
            agent.response_prompt = agent_data.response_prompt
        if agent_data.available_tools is not None:
            agent.available_tools = agent_data.available_tools
        if agent_data.is_active is not None:
            agent.is_active = agent_data.is_active
        
        # Salva no banco
        updated_agent = await repo.update(agent)
        
        # Limpa cache para forçar reload
        config_service.clear_cache()
        
        logger.info(f"✅ Agente '{updated_agent.name}' atualizado com sucesso")
        
        return AgentConfigResponseDTO(
            id=str(updated_agent.id),
            name=updated_agent.name,
            description=updated_agent.description,
            personality=updated_agent.personality,
            available_tools=updated_agent.available_tools,
            is_active=updated_agent.is_active,
            created_at=updated_agent.created_at.isoformat(),
            updated_at=updated_agent.updated_at.isoformat()
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID inválido"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao atualizar agente: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar agente: {str(e)}"
        )


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_agent(agent_id: str):
    """
    Desativa um agente (soft delete).
    O agente não será deletado, apenas marcado como inativo.
    """
    try:
        repo = dependencies.agentConfigRepository()
        config_service = dependencies.agentConfigService()
        
        # Busca agente
        agent = await repo.get_by_id(UUID(agent_id))
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agente com ID {agent_id} não encontrado"
            )
        
        # Desativa
        agent.is_active = False
        await repo.update(agent)
        
        # Limpa cache
        config_service.clear_cache()
        
        logger.info(f"✅ Agente '{agent.name}' desativado com sucesso")
        
        return None
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID inválido"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao desativar agente: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao desativar agente: {str(e)}"
        )


# ========== ENDPOINTS DE MAPEAMENTO ==========

@router.post("/mappings", response_model=PhoneMappingResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_phone_mapping(mapping_data: PhoneMappingCreateDTO):
    """
    Cria um mapeamento de número para agente.
    """
    try:
        from src.Infrastructure import PostgresContext
        
        config_service = dependencies.agentConfigService()
        db = PostgresContext()
        cursor, connection = db.connect()
        
        try:
            # Verifica se agente existe
            cursor.execute(
                "SELECT id FROM agent_configs WHERE id = %s AND is_active = true",
                (mapping_data.agent_id,)
            )
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Agente com ID {mapping_data.agent_id} não encontrado ou inativo"
                )
            
            # Cria mapeamento
            cursor.execute("""
                INSERT INTO agent_phone_mappings (phone_number, agent_id, is_active)
                VALUES (%s, %s, true)
                RETURNING id, phone_number, agent_id, is_active, created_at
            """, (mapping_data.phone_number, mapping_data.agent_id))
            
            connection.commit()
            row = cursor.fetchone()
            
            # Limpa cache
            config_service.clear_cache()
            
            logger.info(f"✅ Mapeamento criado: {mapping_data.phone_number} → {mapping_data.agent_id}")
            
            return PhoneMappingResponseDTO(
                id=str(row[0]),
                phone_number=row[1],
                agent_id=str(row[2]),
                is_active=row[3],
                created_at=row[4].isoformat()
            )
        finally:
            db.disconnect(connection)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar mapeamento: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar mapeamento: {str(e)}"
        )


@router.get("/mappings/{phone_number}")
async def get_agent_by_phone(phone_number: str):
    """
    Busca qual agente está mapeado para um número.
    """
    try:
        repo = dependencies.agentConfigRepository()
        agent = await repo.get_by_phone_number(phone_number)
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nenhum agente mapeado para o número '{phone_number}'"
            )
        
        return AgentConfigResponseDTO(
            id=str(agent.id),
            name=agent.name,
            description=agent.description,
            personality=agent.personality,
            available_tools=agent.available_tools,
            is_active=agent.is_active,
            created_at=agent.created_at.isoformat(),
            updated_at=agent.updated_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar agente por número: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar agente: {str(e)}"
        )


# ========== ENDPOINTS DE CACHE ==========

@router.post("/cache/clear", status_code=status.HTTP_200_OK)
async def clear_cache():
    """
    Limpa o cache de agentes.
    Útil após fazer alterações diretas no banco de dados.
    """
    try:
        config_service = dependencies.agentConfigService()
        config_service.clear_cache()
        
        logger.info("✅ Cache de agentes limpo com sucesso")
        
        return {"message": "Cache limpo com sucesso"}
    except Exception as e:
        logger.error(f"Erro ao limpar cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao limpar cache: {str(e)}"
        )


@router.post("/cache/reload/{phone_number}", status_code=status.HTTP_200_OK)
async def reload_agent_cache(phone_number: str):
    """
    Recarrega o cache de um agente específico.
    """
    try:
        config_service = dependencies.agentConfigService()
        await config_service.reload_agent(phone_number)
        
        logger.info(f"✅ Cache do agente para '{phone_number}' recarregado")
        
        return {"message": f"Cache do agente para '{phone_number}' recarregado"}
    except Exception as e:
        logger.error(f"Erro ao recarregar cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao recarregar cache: {str(e)}"
        )
