from dependency_injector import containers,providers

from src.Domain import (
                           #SERVICES
                           IWhatsAppOrchestratorService,
                           IToolExecutorService,
                           IDecisionService,
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
                           WhatsAppOrchestratorService,
                           ToolExecutor,
                           DecisionService
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
   
   # Cross-cutting
   openaiClient: providers.Singleton[IOpenAiClient] = \
   providers.Singleton(OpenAIClient)
   
   agentsPrompts: providers.Singleton[IAgentPrompts] = \
   providers.Singleton(AgentPrompts)
   
   # ========== SERVICES ==========
   whatsAppOrchestratorService: providers.Singleton[IWhatsAppOrchestratorService] = \
   providers.Singleton(WhatsAppOrchestratorService)

   
   # ========== CONVERSATION SERVICE ==========
   
   conversationService: providers.Singleton[IConversationService] = \
   providers.Singleton(
       ConversationService,
       conversation_repo=conversationRepository,
       message_repo=messageRepository,
       redis=redisRepository
   )
