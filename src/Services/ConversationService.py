import logging
from typing import Optional
from src.Domain import (
    IConversationService,
    ConversationEntity,
    ConversationContext,
    IConversationRepository,
    IRedisRepository,
    IAgentConfigRepository,
    IMessageRepository,
    MessageEntity,
    ResponsePackageEntity
)
from src.Orchestrator import AgentOrchestrator
from src.Infrastructure import OpenAIClient
# from src.Services.agentConfigService import AgentConfigService

logger = logging.getLogger(__name__)

class ConversationService(IConversationService):

    def __init__(
        self,
        conversation_repo: IConversationRepository,
        message_repo: IMessageRepository,
        redis: IRedisRepository,
        agent_config_service: IAgentConfigRepository
    ):
        """
        Inicializa o serviço de conversação.
        
        Args:
            conversation_repo: Repositório de conversas
            message_repo: Repositório de mensagens
            redis: Repositório Redis para cache
            agent_config_service: Serviço para resolver configuração de agentes
        """
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo
        self.redis = redis
        self.agent_config_service = agent_config_service
        self.llm_client = OpenAIClient()
        
        logger.info("[ConversationService] ✅ Inicializado com suporte a multi-agentes")

    def _get_redis_key(self, sender_id: str, instance: str) -> str:
        """Gera chave única para Redis"""
        return f"conversation:{sender_id}:{instance}"

    async def _load_context_from_redis(self, sender_id: str, instance: str) -> Optional[ConversationContext]:
        """Carrega contexto do Redis"""
        try:
            key = self._get_redis_key(sender_id, instance)
            context_data = self.redis.get(key)
            
            if context_data:
                context = ConversationContext.from_dict(context_data)
                logger.info(f"[{sender_id}] ✅ Contexto carregado do Redis")
                return context
            return None
        except Exception as e:
            logger.error(f"[{sender_id}] ❌ Erro ao carregar do Redis: {e}")
            return None

    async def _save_context_to_redis(self, context: ConversationContext, instance: str, ttl_seconds: int = 86400):
        """Salva contexto no Redis com TTL"""
        try:
            key = self._get_redis_key(context.sender_id, instance)
            context_dict = context.to_dict()
            self.redis.set(key, context_dict, ttl_seconds=ttl_seconds)
            logger.info(f"[{context.sender_id}] ✅ Contexto salvo no Redis (TTL: {ttl_seconds}s)")
        except Exception as e:
            logger.error(f"[{context.sender_id}] ❌ Erro ao salvar no Redis: {e}")

    async def _load_or_create_conversation(
        self, 
        sender_id: str, 
        instance: str, 
        channel: str
    ) -> ConversationEntity:
        """Carrega conversa existente ou cria nova"""
        conversation = await self.conversation_repo.get_active_conversation(
            sender_id=sender_id,
            instance=instance,
            channel=channel
        )
        
        if not conversation:
            conversation = await self.conversation_repo.create(
                ConversationEntity(
                    sender_id=sender_id,
                    instance=instance,
                    channel=channel
                )
            )
            logger.info(f"[{sender_id}] ✅ Nova conversa criada: {conversation.id}")
        else:
            # Atualiza timestamp da última mensagem
            await self.conversation_repo.touch(conversation.id)
            logger.info(f"[{sender_id}] ✅ Conversa existente carregada: {conversation.id}")
        
        return conversation

    async def _load_historical_messages(
        self, 
        context: ConversationContext, 
        conversation_id
    ):
        """Carrega mensagens históricas do PostgreSQL e adiciona ao contexto"""
        try:
            messages = await self.message_repo.list_by_conversation(
                conversation_id=conversation_id,
                limit=50  # Últimas 50 mensagens
            )
            
            # Adiciona mensagens ao contexto (apenas se não estiverem já lá)
            existing_count = len(context.messages)
            for msg in messages:
                # Verifica se já existe (evita duplicatas)
                if not any(
                    m.role == msg.role and m.content == msg.content 
                    for m in context.messages
                ):
                    from src.Domain.entities.conversationContextEntity import Message
                    context.messages.append(
                        Message(
                            role=msg.role,
                            content=msg.content,
                            timestamp=msg.created_at
                        )
                    )
            
            if len(context.messages) > existing_count:
                logger.info(
                    f"[{context.sender_id}] ✅ {len(context.messages) - existing_count} mensagens históricas carregadas"
                )
        except Exception as e:
            logger.error(f"[{context.sender_id}] ❌ Erro ao carregar mensagens históricas: {e}")

    async def _save_messages_to_db(
        self,
        conversation_id,
        user_message: str,
        assistant_message: str
    ):
        """Salva mensagens do usuário e assistente no PostgreSQL"""
        try:
            # Salva mensagem do usuário
            await self.message_repo.create(
                MessageEntity(
                    conversation_id= conversation_id,
                    role="user",
                    content=user_message
                )
            )
            
            # Salva mensagem do assistente
            await self.message_repo.create(
                MessageEntity(
                    conversation_id= conversation_id,
                    role="assistant",
                    content=assistant_message
                )
            )
            
            logger.info(f"[Conversation {conversation_id}] ✅ Mensagens salvas no PostgreSQL")
        except Exception as e:
            logger.error(f"[Conversation {conversation_id}] ❌ Erro ao salvar mensagens: {e}")

    async def process_message(
        self,
        sender_id: str,
        instance: str,
        channel: str,
        text: str
    ) -> ResponsePackageEntity:
        """
        Processa mensagem completa:
        1. Resolve qual agente usar baseado no instance (número)
        2. Carrega contexto do Redis
        3. Carrega/cria conversa no PostgreSQL
        4. Carrega mensagens históricas se necessário
        5. Processa com agente específico
        6. Salva tudo (Redis + PostgreSQL)
        """
        logger.info(f"[{sender_id}] 📨 Processando mensagem: {text[:100]}...")
        
        # ========== 1. RESOLVE QUAL AGENTE USAR ==========
        agent_config = await self.agent_config_service.get_by_phone_number(instance)
        logger.info(f"[{sender_id}] 🤖 Usando agente: {agent_config.name} (personalidade: {agent_config.personality})")
        
        # ========== 2. CRIA ORCHESTRATOR COM CONFIG ESPECÍFICA ==========
        agent = AgentOrchestrator(
            llm_client=self.llm_client,
            agent_config=agent_config
        )
        
        # ========== 3. CARREGA CONTEXTO DO REDIS ==========
        context = await self._load_context_from_redis(sender_id, instance)
        
        # ========== 4. CARREGA/CRIA CONVERSA NO POSTGRESQL ==========
        conversation = await self._load_or_create_conversation(
            sender_id=sender_id,
            instance=instance,
            channel=channel
        )
        
        # ========== 5. INICIALIZA CONTEXTO SE NÃO EXISTIR ==========
        if not context:
            context = ConversationContext(sender_id=sender_id)
            logger.info(f"[{sender_id}] ✅ Novo contexto criado")
            
            # Carrega mensagens históricas da conversa
            await self._load_historical_messages(context, conversation.id)
        else:
            # Mesmo com contexto no Redis, pode haver mensagens novas no DB
            # (em caso de múltiplas instâncias ou recuperação)
            await self._load_historical_messages(context, conversation.id)
        
        # ========== 6. PROCESSA MENSAGEM COM AGENTE ESPECÍFICO ==========
        response_package = await agent.process_message(context, text)
        
        # ========== 7. SALVA CONTEXTO NO REDIS ==========
        await self._save_context_to_redis(context, instance, ttl_seconds=86400)
        
        # ========== 8. SALVA MENSAGENS NO POSTGRESQL ==========
        await self._save_messages_to_db(
            conversation_id=conversation.id,
            user_message=text,
            assistant_message=response_package.text
        )
        
        logger.info(f"[{sender_id}] ✅ Processamento completo com agente '{agent_config.name}'")
        
        return response_package
