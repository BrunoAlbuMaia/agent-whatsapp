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
                           IRedisRepository
                        )
from src.Services import (
                           ConversationService,
                           WhatsAppOrchestratorService
                         )
from src.Orchestrator.agentOrchestrator import AgentOrchestrator

from src.Infrastructure import (
                                 ConversationRepository,
                                 MessageRepository,
                                 RedisRepository,
                                 OpenAIClient,
                                 AgentPrompts
                               )


class Dependecie(containers.DeclarativeContainer):
    
   # ========== INFRASTRUCTURE ==========
   
   # Repositories
   conversationRepository: providers.Singleton[IConversationRepository] = \
   providers.Singleton(ConversationRepository)
   
   messageRepository: providers.Singleton[IMessageRepository] = \
   providers.Singleton(MessageRepository)
   
   redisRepository: providers.Singleton[IRedisRepository] = \
   providers.Singleton(RedisRepository)
   
   # ========== SERVICES ==========
   whatsAppOrchestratorService: providers.Singleton[IWhatsAppOrchestratorService] = \
   providers.Singleton(WhatsAppOrchestratorService)   
   
   conversationService: providers.Singleton[IConversationService] = \
   providers.Singleton(
       ConversationService,
       conversation_repo=conversationRepository,
       message_repo=messageRepository,
       redis=redisRepository
   )
