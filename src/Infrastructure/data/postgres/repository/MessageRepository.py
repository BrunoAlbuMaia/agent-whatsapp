# src/Infrastructure/data/postgres/repository/MessageRepository.py
import uuid
from datetime import datetime
from typing import List, Optional

from src.Domain import (
    IMessageRepository,
    MessageEntity
)
from src.Infrastructure import PostgresContext


class MessageRepository(IMessageRepository):

    def __init__(self):
        self.db = PostgresContext()

    async def create(self, message: MessageEntity) -> MessageEntity:
        """Cria uma nova mensagem no banco de dados"""
        cursor, connection = self.db.connect()
        try:
            
            created_at = message.created_at or datetime.utcnow()

            cursor.execute("""
                INSERT INTO messages (
                    conversation_id,
                    role,
                    content,
                    created_at,
                    metadata
                ) VALUES ( %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                
                str(message.conversation_id),
                message.role,
                message.content,
                created_at,
                message.metadata
            ))

            connection.commit()
            message.id = cursor.fetchone()[0]
            message.created_at = created_at
            return message
        finally:
            self.db.disconnect(connection)

    async def list_by_conversation(
        self,
        conversation_id: uuid.UUID,
        limit: int = 50
    ) -> List[MessageEntity]:
        """Lista mensagens de uma conversa"""
        cursor, connection = self.db.connect()
        try:
            cursor.execute("""
                SELECT 
                    id,
                    conversation_id,
                    role,
                    content,
                    created_at,
                    metadata
                FROM messages
                WHERE conversation_id = %s
                ORDER BY created_at ASC
                LIMIT %s
            """, (str(conversation_id), limit))

            rows = cursor.fetchall()

            return [
                MessageEntity(
                    id=row[0],
                    conversation_id=row[1],
                    role=row[2],
                    content=row[3],
                    created_at=row[4],
                    metadata=row[5]
                )
                for row in rows
            ]
        finally:
            self.db.disconnect(connection)
