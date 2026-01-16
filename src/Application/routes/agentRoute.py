
from fastapi import APIRouter, Request, BackgroundTasks

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
    payload = await request.json()
    print(payload)
    return payload
