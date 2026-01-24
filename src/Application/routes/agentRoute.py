
from fastapi import APIRouter, Request, BackgroundTasks
import logging
from src.Application.mapper.whatsappMessageMapper import map_webhook_to_incoming_message
from src.Domain import MessageupsertEntity
from src.Application.dependecie import Dependecie
# from src.Application.useCase.agentOrchestrator import AgentOrchestrator 

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
    conversationService = dependencies.conversationService()
    whatsAppOrchestratorService = dependencies.whatsAppOrchestratorService()
    
    try:
        # 1. Processa mensagem com o agente
        response_package = await conversationService.process_message(
            sender_id=messageupsertEntity.sender_id,
            instance=messageupsertEntity.instance or "default",
            channel="whatsapp",
            text=messageupsertEntity.text
        )
        
        # # 2. Envia resposta via WhatsApp
        await whatsAppOrchestratorService.send_response(
            agent_name=messageupsertEntity.instance or "default",
            phone_number=messageupsertEntity.sender_id,
            response_package=response_package
        )
        
        return {"status": "ok", "message": "Processado com sucesso"}
    except Exception as ex:
        logger.error(f"Erro ao processar mensagem: {ex}", exc_info=True)
        raise ex

    