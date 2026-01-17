from pydantic import BaseModel,Field
from typing import List, Optional


class MediaItem(BaseModel):
    """Item de mídia para enviar"""
    type: str  # "document", "image", "audio", "video"
    path: str  # Caminho do arquivo
    caption: Optional[str] = None
    mimetype: Optional[str] = None


class ResponsePackageEntity(BaseModel):
    """Pacote completo de resposta para o usuário"""
    text: Optional[str] = None  # Mensagem de texto
    media_items: List[MediaItem] = Field(default_factory=list)  # PDFs, imagens, etc
    
    def add_document(self, path: str, caption: str = None):
        """Adiciona documento (PDF, DOCX, etc)"""
        self.media_items.append(MediaItem(
            type="document",
            path=path,
            caption=caption,
            mimetype="application/pdf"  # ajustar conforme necessário
        ))
    
    def add_image(self, path: str, caption: str = None):
        """Adiciona imagem"""
        self.media_items.append(MediaItem(
            type="image",
            path=path,
            caption=caption,
            mimetype="image/jpeg"
        ))
    
    def add_audio(self, path: str):
        """Adiciona áudio"""
        self.media_items.append(MediaItem(
            type="audio",
            path=path,
            mimetype="audio/ogg"
        ))
    
    def has_media(self) -> bool:
        """Verifica se tem mídia para enviar"""
        return len(self.media_items) > 0