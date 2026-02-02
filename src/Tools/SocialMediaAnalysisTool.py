from .baseTool import BaseTool
from typing import Dict, Any, List
import base64
import json
import logging
from openai import OpenAI
import os

logger = logging.getLogger(__name__)

class SocialMediaAnalysisTool(BaseTool):
    """
    Tool para extração de dados estruturados de relatórios de redes sociais em PDF.
    Usa GPT-4o Vision para OCR e extração de métricas.
    
    IMPORTANTE: Esta tool APENAS extrai dados. O agente do orchestrator é responsável
    por interpretar e responder ao usuário.
    """
    
    def __init__(self):
        """Inicializa o cliente OpenAI"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY não encontrada nas variáveis de ambiente")
        self.client = OpenAI(api_key=api_key)
    
    @property
    def name(self) -> str:
        return "extrair_dados_relatorio_redes_sociais"
    
    @property
    def description(self) -> str:
        return """
        Extrai dados estruturados de relatórios de redes sociais (Instagram, Facebook, etc.) em formato PDF.
        
        FUNCIONALIDADE:
        - Converte PDF em imagens de alta qualidade
        - Usa GPT-4o Vision para extrair dados estruturados
        - Retorna JSON com métricas, demografia, performance de conteúdo
        
        DADOS EXTRAÍDOS:
        - Período do relatório
        - Métricas gerais (alcance, engajamento, visualizações)
        - Dados de seguidores (novos, perdidos, total)
        - Demografia (gênero, idade, países, cidades)
        - Performance de Stories (total, visualizações, top posts)
        - Performance de Reels (total, visualizações, top posts)
        - Performance de Posts (total, interações, top posts)
        
        IMPORTANTE: Esta tool apenas extrai dados. O agente deve interpretar e responder.
        """
    
    def _get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "caminho_pdf": {
                    "type": "string",
                    "description": "Caminho completo do arquivo PDF do relatório de redes sociais"
                }
            },
            "required": ["caminho_pdf"],
            "additionalProperties": False
        }
    
    async def execute(self, caminho_pdf: str) -> Dict[str, Any]:
        """
        Extrai dados estruturados do relatório de redes sociais.
        
        Args:
            caminho_pdf: Caminho do arquivo PDF
        
        Returns:
            Dict com dados extraídos ou erro
        """
        try:
            # Valida se o arquivo existe
            if not os.path.exists(caminho_pdf):
                return {
                    "success": False,
                    "error": f"Arquivo não encontrado: {caminho_pdf}"
                }
            
            # Valida extensão
            if not caminho_pdf.lower().endswith('.pdf'):
                return {
                    "success": False,
                    "error": "O arquivo deve ser um PDF"
                }
            
            logger.info(f"[SocialMediaTool] Iniciando extração de: {caminho_pdf}")
            
            # 1. Converte PDF para imagens base64
            imagens_base64 = self._pdf_para_base64_imagens(caminho_pdf)
            
            if not imagens_base64:
                return {
                    "success": False,
                    "error": "Não foi possível converter o PDF em imagens"
                }
            
            logger.info(f"[SocialMediaTool] PDF convertido em {len(imagens_base64)} páginas")
            
            # 2. Extrai dados estruturados usando Vision
            dados_extraidos = await self._extrair_dados_relatorio(imagens_base64)
            
            if not dados_extraidos:
                return {
                    "success": False,
                    "error": "Não foi possível extrair dados do relatório"
                }
            
            logger.info("[SocialMediaTool] ✅ Dados extraídos com sucesso")
            
            # Retorna apenas os dados extraídos
            return {
                "success": True,
                "dados": dados_extraidos
            }
            
        except Exception as e:
            logger.error(f"[SocialMediaTool] ❌ Erro na extração: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def _pdf_para_base64_imagens(self, caminho_pdf: str) -> List[str]:
        """
        Converte páginas do PDF para lista de strings base64.
        Usa PyMuPDF (fitz) para renderização de alta qualidade.
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("[SocialMediaTool] PyMuPDF não instalado. Execute: pip install PyMuPDF")
            return []
        
        imagens_base64 = []
        
        try:
            doc = fitz.open(caminho_pdf)
            
            for pagina_num in range(len(doc)):
                pagina = doc.load_page(pagina_num)
                # Zoom de 2x para melhor qualidade de OCR
                pix = pagina.get_pixmap(matrix=fitz.Matrix(2, 2))
                
                # Converte para bytes PNG
                img_bytes = pix.tobytes("png")
                
                # Converte para base64
                base64_str = base64.b64encode(img_bytes).decode('utf-8')
                imagens_base64.append(base64_str)
            
            doc.close()
            
        except Exception as e:
            logger.error(f"[SocialMediaTool] Erro ao converter PDF: {e}")
            return []
        
        return imagens_base64
    
    async def _extrair_dados_relatorio(self, imagens_base64: List[str]) -> Dict[str, Any]:
        """
        Extrai dados estruturados do relatório usando GPT-4o Vision.
        """
        # Monta mensagens para o modelo de visão
        mensagens_conteudo = [
            {
                "type": "text",
                "text": """Analise estas imagens do relatório de redes sociais e extraia TODOS os dados possíveis em formato JSON estruturado.

EXTRAIA:
1. PERÍODO: Data início, fim, mês de referência
2. RESUMO GERAL: Alcance, engajamento, visualizações, interações, taxa de engajamento
3. SEGUIDORES: Novos seguidores, perdidos, total, taxa de crescimento
4. DEMOGRAFIA: Gênero (%), faixa etária (%), países (%), cidades (%)
5. STORIES: Total, visualizações, média, melhor tipo, top 20 (data, descrição, visualizações, alcance)
6. REELS: Total, visualizações, média, top 20 (data, descrição, curtidas, comentários, visualizações, engajamento)
7. POSTS: Total, interações, média, melhor tipo, top 20 (data, tipo, curtidas, comentários, alcance, visualizações)

Seja PRECISO com números, datas, tabelas e gráficos.
Retorne um JSON estruturado e completo."""
            }
        ]
        
        # Adiciona cada página como imagem
        for img_b64 in imagens_base64:
            mensagens_conteudo.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_b64}",
                    "detail": "high"
                }
            })
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "Você é um especialista em análise de dados de redes sociais e OCR visual avançado. Extraia dados de forma precisa e estruturada."
                    },
                    {
                        "role": "user",
                        "content": mensagens_conteudo
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0
            )
            
            dados = json.loads(response.choices[0].message.content)
            return dados
            
        except Exception as e:
            logger.error(f"[SocialMediaTool] Erro ao extrair dados com Vision API: {e}")
            return {}
