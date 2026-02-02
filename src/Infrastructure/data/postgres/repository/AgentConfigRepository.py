import json
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from src.Domain import (
    IAgentConfigRepository,
    AgentConfigEntity
)
from src.Infrastructure import PostgresContext


class AgentConfigRepository(IAgentConfigRepository):
    """Repositório PostgreSQL para configurações de agentes"""

    def __init__(self):
        self.db = PostgresContext()

    async def get_by_id(self, agent_id: UUID) -> Optional[AgentConfigEntity]:
        """Busca agente por ID"""
        cursor, connection = self.db.connect()
        try:
            cursor.execute("""
                SELECT 
                    id, name, description, personality,
                    flow_decision_prompt, response_prompt,
                    available_tools, is_active, created_at, updated_at
                FROM agent_configs
                WHERE id = %s
            """, (str(agent_id),))

            row = cursor.fetchone()
            if not row:
                return None

            return AgentConfigEntity(
                id=UUID(row[0]),
                name=row[1],
                description=row[2],
                personality=row[3],
                flow_decision_prompt=row[4],
                response_prompt=row[5],
                available_tools=row[6] if isinstance(row[6], list) else json.loads(row[6]),
                is_active=row[7],
                created_at=row[8],
                updated_at=row[9]
            )
        finally:
            self.db.disconnect(connection)

    async def get_by_phone_number(self, phone_number: str) -> Optional[AgentConfigEntity]:
        """Busca agente mapeado para um número de telefone"""
        cursor, connection = self.db.connect()
        try:
            cursor.execute("""
                SELECT 
                    ac.id, ac.name, ac.description, ac.personality,
                    ac.flow_decision_prompt, ac.response_prompt,
                    ac.available_tools, ac.is_active, ac.created_at, ac.updated_at
                FROM agent_configs ac
                INNER JOIN agent_phone_mappings apm ON ac.id = apm.agent_id
                WHERE apm.phone_number = %s
                  AND apm.is_active = true
                  AND ac.is_active = true
                LIMIT 1
            """, (phone_number,))

            row = cursor.fetchone()
            if not row:
                return None

            return AgentConfigEntity(
                id=UUID(row[0]),
                name=row[1],
                description=row[2],
                personality=row[3],
                flow_decision_prompt=row[4],
                response_prompt=row[5],
                available_tools=row[6] if isinstance(row[6], list) else json.loads(row[6]),
                is_active=row[7],
                created_at=row[8],
                updated_at=row[9]
            )
        finally:
            self.db.disconnect(connection)

    async def list_active(self) -> List[AgentConfigEntity]:
        """Lista todos os agentes ativos"""
        cursor, connection = self.db.connect()
        try:
            cursor.execute("""
                SELECT 
                    id, name, description, personality,
                    flow_decision_prompt, response_prompt,
                    available_tools, is_active, created_at, updated_at
                FROM agent_configs
                WHERE is_active = true
                ORDER BY created_at DESC
            """)

            rows = cursor.fetchall()
            return [
                AgentConfigEntity(
                    id=UUID(row[0]),
                    name=row[1],
                    description=row[2],
                    personality=row[3],
                    flow_decision_prompt=row[4],
                    response_prompt=row[5],
                    available_tools=row[6] if isinstance(row[6], list) else json.loads(row[6]),
                    is_active=row[7],
                    created_at=row[8],
                    updated_at=row[9]
                )
                for row in rows
            ]
        finally:
            self.db.disconnect(connection)

    async def create(self, agent_config: AgentConfigEntity) -> AgentConfigEntity:
        """Cria novo agente"""
        cursor, connection = self.db.connect()
        try:
            cursor.execute("""
                INSERT INTO agent_configs (
                    name, description, personality,
                    flow_decision_prompt, response_prompt,
                    available_tools, is_active
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at, updated_at
            """, (
                agent_config.name,
                agent_config.description,
                agent_config.personality,
                agent_config.flow_decision_prompt,
                agent_config.response_prompt,
                json.dumps(agent_config.available_tools),
                agent_config.is_active
            ))

            connection.commit()
            row = cursor.fetchone()
            agent_config.id = UUID(row[0])
            agent_config.created_at = row[1]
            agent_config.updated_at = row[2]
            return agent_config
        finally:
            self.db.disconnect(connection)

    async def update(self, agent_config: AgentConfigEntity) -> AgentConfigEntity:
        """Atualiza agente existente"""
        cursor, connection = self.db.connect()
        try:
            cursor.execute("""
                UPDATE agent_configs
                SET name = %s,
                    description = %s,
                    personality = %s,
                    flow_decision_prompt = %s,
                    response_prompt = %s,
                    available_tools = %s,
                    is_active = %s,
                    updated_at = %s
                WHERE id = %s
                RETURNING updated_at
            """, (
                agent_config.name,
                agent_config.description,
                agent_config.personality,
                agent_config.flow_decision_prompt,
                agent_config.response_prompt,
                json.dumps(agent_config.available_tools),
                agent_config.is_active,
                datetime.now(),
                str(agent_config.id)
            ))

            connection.commit()
            row = cursor.fetchone()
            if row:
                agent_config.updated_at = row[0]
            return agent_config
        finally:
            self.db.disconnect(connection)

    async def get_default_agent(self) -> Optional[AgentConfigEntity]:
        """Retorna o agente padrão (primeiro ativo ou com nome 'default')"""
        cursor, connection = self.db.connect()
        try:
            # Tenta buscar um agente com nome 'default' ou 'padrão'
            cursor.execute("""
                SELECT 
                    id, name, description, personality,
                    flow_decision_prompt, response_prompt,
                    available_tools, is_active, created_at, updated_at
                FROM agent_configs
                WHERE is_active = true
                  AND (LOWER(name) = 'default' OR LOWER(name) = 'padrão' OR LOWER(name) = 'assistente geral')
                LIMIT 1
            """)

            row = cursor.fetchone()
            
            # Se não encontrar, pega o primeiro agente ativo
            if not row:
                cursor.execute("""
                    SELECT 
                        id, name, description, personality,
                        flow_decision_prompt, response_prompt,
                        available_tools, is_active, created_at, updated_at
                    FROM agent_configs
                    WHERE is_active = true
                    ORDER BY created_at ASC
                    LIMIT 1
                """)
                row = cursor.fetchone()

            if not row:
                return None

            return AgentConfigEntity(
                id=UUID(row[0]),
                name=row[1],
                description=row[2],
                personality=row[3],
                flow_decision_prompt=row[4],
                response_prompt=row[5],
                available_tools=row[6] if isinstance(row[6], list) else json.loads(row[6]),
                is_active=row[7],
                created_at=row[8],
                updated_at=row[9]
            )
        finally:
            self.db.disconnect(connection)
