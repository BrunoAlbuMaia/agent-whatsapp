from dependency_injector import containers,providers

from src.Domain import (
                           #SERVICES
                           IWhatsAppOrchestratorService,
                           IConversationService,
                           IOpenAiClient,
                           IAgentPrompts,

                           #INFRASTRUCTURE
                           IConversationRepository,
                           IMessageRepository,
                           IRedisRepository,
                           IAgentConfigRepository
                        )
from src.Services import (
                           ConversationService,
                           WhatsAppOrchestratorService
                         )
from src.Services.agentConfigService import AgentConfigService
from src.Orchestrator.agentOrchestrator import AgentOrchestrator

from src.Infrastructure import (
                                 ConversationRepository,
                                 MessageRepository,
                                 RedisRepository,
                                 OpenAIClient,
                                 AgentPrompts
                               )
from src.Infrastructure.data.postgres.repository.AgentConfigRepository import AgentConfigRepository


class Dependecie(containers.DeclarativeContainer):
    
   # ========== INFRASTRUCTURE ==========
   
   # Repositories
   conversationRepository: providers.Singleton[IConversationRepository] = \
   providers.Singleton(ConversationRepository)
   
   messageRepository: providers.Singleton[IMessageRepository] = \
   providers.Singleton(MessageRepository)
   
   redisRepository: providers.Singleton[IRedisRepository] = \
   providers.Singleton(RedisRepository)
   
   agentConfigRepository: providers.Singleton[IAgentConfigRepository] = \
   providers.Singleton(AgentConfigRepository)
   
   # ========== SERVICES ==========
   
   # Agent Config Service
   agentConfigService: providers.Singleton[AgentConfigService] = \
   providers.Singleton(
       AgentConfigService,
       agent_config_repo=agentConfigRepository
   )
   
   # WhatsApp Orchestrator Service
   whatsAppOrchestratorService: providers.Singleton[IWhatsAppOrchestratorService] = \
   providers.Singleton(WhatsAppOrchestratorService)   
   
   # Conversation Service (agora com AgentConfigService)
   conversationService: providers.Singleton[IConversationService] = \
   providers.Singleton(
       ConversationService,
       conversation_repo=conversationRepository,
       message_repo=messageRepository,
       redis=redisRepository,
       agent_config_service=agentConfigRepository
   )
