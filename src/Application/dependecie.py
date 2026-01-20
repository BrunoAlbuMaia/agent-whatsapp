from dependency_injector import containers,providers
from src.Application.useCase.agentOrchestrator import AgentOrchestrator

from src.Domain import (
                           #SERVICES
                           IWhatsAppOrchestratorService,
                           IToolExecutorService,
                           IDecisionService,

                           #INFRASTRUCTURE
                           IOpenAiClient,
                           IAgentPrompts,
                           
                        )
from src.Services import (
                           WhatsAppOrchestratorService,
                           ToolExecutor,
                           DecisionService
                         
                         )

from src.Infrastructure import (
                                 OpenAIClient,
                                 AgentPrompts
                               )


class Dependecie(containers.DeclarativeContainer):



    
   # Infrastructure
   openaiClient:providers.Singleton[IOpenAiClient] = \
   providers.Singleton(
                        OpenAIClient
                       )
   agentsPrompts:providers.Singleton[IAgentPrompts] = \
   providers.Singleton(
                        AgentPrompts
                     )


   
   #Service
   toolExecutorService:providers.Singleton[IToolExecutorService] = \
   providers.Singleton(
                        ToolExecutor
                     )
   decisionService:providers.Singleton[IDecisionService] = \
   providers.Singleton(
                        DecisionService
                     )
   whatsAppOrchestratorService:providers.Singleton[IWhatsAppOrchestratorService] = \
   providers.Singleton(
                          WhatsAppOrchestratorService
                       )


   # Orchestrator
   agentOrchestrator = providers.Singleton(
                                             AgentOrchestrator,
                                             tool_excutor= toolExecutorService,
                                             llm_client= openaiClient, 
                                             agentsPrompts= agentsPrompts, 
                                             decision_service= decisionService
                                          )
