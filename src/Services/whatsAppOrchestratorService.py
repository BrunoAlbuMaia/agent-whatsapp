import logging
import os
from src.Domain import ResponsePackageEntity,IWhatsAppOrchestratorService
from src.Infrastructure import WhatsAppClient

logger = logging.getLogger(__name__)

class WhatsAppOrchestratorService(IWhatsAppOrchestratorService):
    """
    Decide como enviar a resposta pro WhatsApp
    (texto, documento, imagem, combinações, etc)
    """
    
    def __init__(self):
        self.whatsapp_client = WhatsAppClient()
    
    async def send_response(
        self,
        agent_name: str,
        phone_number: str,
        response_package: ResponsePackageEntity
    ):
        """
        Envia resposta completa pro WhatsApp
        
        :param agent_name: Nome do agente/instância
        :param phone_number: Número do destinatário
        :param response_package: Pacote com texto + mídias
        """
        try:
            # 1. Envia texto primeiro (se houver)
            if response_package.text:
                logger.info(f"Enviando texto para {phone_number}")
                await self.whatsapp_client.send_text(
                    agent_name=agent_name,
                    phone_number=phone_number,
                    message=response_package.text
                )
            
            # 2. Envia mídias (documentos, imagens, áudios)
            # for media_item in response_package.media_items:
            #     if not os.path.exists(media_item.path):
            #         logger.warning(f"Arquivo não encontrado: {media_item.path}")
            #         continue
                
            #     logger.info(f"Enviando {media_item.type} para {phone_number}: {media_item.path}")
                
            #     if media_item.type == "document":
            #         await self.whatsapp_client.send_document(
            #             agent_name=agent_name,
            #             phone_number=phone_number,
            #             file_path=media_item.path,
            #             caption=media_item.caption
            #         )
                
            #     elif media_item.type == "image":
            #         await self.whatsapp_client.send_image(
            #             agent_name=agent_name,
            #             phone_number=phone_number,
            #             file_path=media_item.path,
            #             caption=media_item.caption
            #         )
                
            #     elif media_item.type == "audio":
            #         await self.whatsapp_client.send_audio(
            #             agent_name=agent_name,
            #             phone_number=phone_number,
            #             file_path=media_item.path
            #         )
                
                
            #     # try:
                #     os.remove(media_item.path)
                #     logger.info(f"Arquivo removido: {media_item.path}")
                # except Exception as e:
                #     logger.warning(f"Erro ao remover arquivo {media_item.path}: {e}")
            
            logger.info(f"Resposta completa enviada para {phone_number}")
            
        except Exception as e:
            logger.error(f"Erro ao enviar resposta: {e}", exc_info=True)
            raise
    