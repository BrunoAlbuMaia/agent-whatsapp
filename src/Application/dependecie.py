from dependency_injector import containers,providers

from src.Domain import IAgentOrchestratorService \
                      ,IWhatsAppOrchestratorService
from src.Services import AgentOrchestratorService \
                      ,WhatsAppOrchestratorService


class Dependecie(containers.DeclarativeContainer):
    agentOrchestratorService:providers.Singleton[IAgentOrchestratorService] = \
    providers.Singleton(
                          AgentOrchestratorService
                       )

    whatsAppOrchestratorService:providers.Singleton[IWhatsAppOrchestratorService] = \
    providers.Singleton(
                          WhatsAppOrchestratorService
                       )


