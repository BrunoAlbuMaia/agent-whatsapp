
from fastapi import APIRouter, Request, BackgroundTasks
import logging
from src.Application.mapper.whatsappMessageMapper import map_webhook_to_incoming_message
from src.Domain import MessageupsertEntity
from src.Application.dependecie import Dependecie
from src.Application.useCase.agentOrchestrator import AgentOrchestrator 

logger = logging.getLogger("webhook")
logging.basicConfig(level=logging.INFO)
router = APIRouter()
dependencies = Dependecie()



@router.post("/messages-upsert")
async def messages_upsert(request: Request):
    raw_body = await request.json()

    #O Json capturado, é transformado na entidade MessageupsertEntity#
    messageupsertEntity:MessageupsertEntity = map_webhook_to_incoming_message(raw_body)

    if not raw_body:
        logger.warning("Body vazio")
        return {"status": "ignored"}
    agentOrchestrator = dependencies.agentOrchestrator()
    whatsAppOrchestratorService = dependencies.whatsAppOrchestratorService()
    try:
        # 1. Envia para o agente processar o que será feito!
        response_package = await agentOrchestrator.process_message(messageupsertEntity.sender_id,messageupsertEntity.text)
        
        # # 2. Envia com WhatsApp Orchestrator
        await whatsAppOrchestratorService.send_response(
            agent_name=messageupsertEntity.instance,
            phone_number=messageupsertEntity.sender_id,
            response_package=response_package
        )
        
        return {"status": "ok"}
    except Exception as ex:
        raise ex

    