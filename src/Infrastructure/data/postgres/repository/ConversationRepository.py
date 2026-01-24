# src/Infrastructure/Persistence/ConversationPostgresRepository.py
import uuid
from datetime import datetime
from typing import Optional, List

from src.Domain import (
    IConversationRepository,
    ConversationEntity
)
from src.Infrastructure import PostgresContext


class ConversationRepository(IConversationRepository):

    def __init__(self):
        self.db = PostgresContext()

    async def get_conversations(self) -> List[ConversationEntity]:
        cursor, connection = self.db.connect()
        try:
            cursor.execute("""
                SELECT 
                    id,
                    sender_id,
                    instance,
                    channel,
                    started_at,
                    ended_at,
                    last_message_at,
                    metadata
                FROM conversations
            """)
            rows = cursor.fetchall()

            return [
                ConversationEntity(
                    id=row[0],
                    sender_id=row[1],
                    instance=row[2],
                    channel=row[3],
                    started_at=row[4],
                    ended_at=row[5],
                    last_message_at=row[6],
                    metadata=row[7]
                )
                for row in rows
            ]
        finally:
            self.db.disconnect(connection)

    async def get_active_conversation(
        self,
        sender_id: str,
        instance: str,
        channel: str
    ) -> Optional[ConversationEntity]:

        cursor, connection = self.db.connect()
        try:
            cursor.execute("""
                SELECT 
                    id,
                    sender_id,
                    instance,
                    channel,
                    started_at,
                    ended_at,
                    last_message_at,
                    metadata
                FROM conversations
                WHERE sender_id = %s
                  AND instance = %s
                  AND channel = %s
                  AND status = 'active'
                LIMIT 1
            """, (sender_id, instance, channel))

            row = cursor.fetchone()
            if not row:
                return None

            return ConversationEntity(
                id=row[0],
                sender_id=row[1],
                instance=row[2],
                channel=row[3],
                started_at=row[4],
                ended_at=row[5],
                last_message_at=row[6],
                metadata=row[7]
            )
        finally:
            self.db.disconnect(connection)

    async def create(self, conversation: ConversationEntity) -> ConversationEntity:
        cursor, connection = self.db.connect()
        try:
            cursor.execute("""
                INSERT INTO conversations (
                    sender_id,
                    instance,
                    channel,
                    started_at,
                    status,
                    metadata
                ) VALUES ( %s, %s, %s, %s, 'active', %s)
                RETURNING id
            """, (
                conversation.sender_id,
                conversation.instance,
                conversation.channel,
                conversation.started_at or datetime.utcnow(),
                conversation.metadata
            ))

            connection.commit()
            conversation.id = cursor.fetchone()[0]
            return conversation
        finally:
            self.db.disconnect(connection)

    async def touch(self, conversation_id):
        cursor, connection = self.db.connect()
        try:
            cursor.execute("""
                UPDATE conversations
                SET last_message_at = %s
                WHERE id = %s
            """, (datetime.utcnow(), str(conversation_id)))

            connection.commit()
        finally:
            self.db.disconnect(connection)

    async def close(self, conversation_id):
        cursor, connection = self.db.connect()
        try:
            cursor.execute("""
                UPDATE conversations
                SET status = 'closed',
                    ended_at = %s
                WHERE id = %s
            """, (datetime.utcnow(), conversation_id))

            connection.commit()
        finally:
            self.db.disconnect(connection)
