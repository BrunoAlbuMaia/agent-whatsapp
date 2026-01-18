from dependency_injector import containers,providers

from src.Domain import (
                           IWhatsAppOrchestratorService,
                           IOpenAiClient,
                           IToolExecutorService
                        )
from src.Services import (
                           WhatsAppOrchestratorService,
                           ToolExecutor
                         
                         )

from src.Infrastructure import (
                                 OpenAIClient
                               )


class Dependecie(containers.DeclarativeContainer):
    
   # Infrastructure
   openaiClient:providers.Singleton[IOpenAiClient] = \
   providers.Singleton(
                        OpenAIClient
                       )
   
   #Service
   toolExecutorService:providers.Singleton[IToolExecutorService] = \
   providers.Singleton(
                        ToolExecutor
                     )
   whatsAppOrchestratorService:providers.Singleton[IWhatsAppOrchestratorService] = \
   providers.Singleton(
                          WhatsAppOrchestratorService
                       )


