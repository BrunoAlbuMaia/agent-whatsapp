import httpx
from src.config import settings


class WhatsAppClient:
    def __init__(self):
        self.base_url = settings.BASE_URL_EVOLUTION.rstrip("/")
        self.api_key = settings.API_KEY_EVOLUITON

        self.headers = {
            "Content-Type": "application/json",
            "apikey": self.api_key,
        }

    async def send_text(
        self,
        agent_name: str,
        phone_number: str,
        message: str,
    ) -> dict:
        """
        Envia uma mensagem de texto via Evolution API

        :param agent_name: Nome do agente (ex: AgentBruno)
        :param phone_number: Número com DDI e DDD (ex: 5585988970670)
        :param message: Texto da mensagem
        """

        url = f"{self.base_url}/message/sendText/{agent_name}"

        payload = {
            "number": phone_number,
            "text": message,
            "delay":1200
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                headers=self.headers,
                json=payload,
            )

        response.raise_for_status()
        return response.json()

    async def send_document():...

    async def send_image():...
    
    async def send_audio():...