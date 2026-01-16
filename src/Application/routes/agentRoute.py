
from fastapi import APIRouter, Request, BackgroundTasks
import logging
# import logging

logger = logging.getLogger("webhook")
logging.basicConfig(level=logging.INFO)
router = APIRouter()
# dependencies = Dependencies()


@router.post("/conversation")
async def post_conversation(
    request:Request
):
    payload = await request.json()
    print("Mensagem recebida:", payload)
    return request.json()


@router.post("/messages-upsert")
async def messages_upsert(request: Request):
    raw_body = await request.body()

    logger.info("messages-upsert chamado")
    logger.info("RAW BODY: %s", raw_body)

    if not raw_body:
        logger.warning("Body vazio")
        return {"status": "ignored"}

    return {"status": "ok"}