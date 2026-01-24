from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime
from uuid import UUID

class ConversationEntity(BaseModel):
    id: Optional[UUID] = Field(
        default=None,
        description="Identificador único da conversa"
    )

    sender_id: str = Field(
        ...,
        max_length=100,
        description="Identificador de quem está enviando a mensagem"
    )

    instance: str = Field(
        ...,
        max_length=50,
        description="Identidade da origem da conversa (bot / número / agente)"
    )

    channel: str = Field(
        ...,
        max_length=30,
        description="Canal de comunicação (whatsapp, web, telegram, etc)"
    )

    started_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        description="Horário da primeira interação"
    )

    ended_at: Optional[datetime] = Field(
        default=None,
        description="Horário de encerramento da conversa"
    )

    last_message_at: Optional[datetime] = Field(
        default=None,
        description="Horário da última mensagem"
    )

    metadata: Optional[Dict] = Field(
        default=None,
        description="Dados adicionais da conversa (tags, campanha, origem, etc)"
    )
