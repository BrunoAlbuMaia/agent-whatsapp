
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

