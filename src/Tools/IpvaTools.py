# Application/tools/ipvaTool.py

from .baseTool import BaseTool
from typing import Dict, Any, List
import httpx
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class IpvaTool(BaseTool):
    BASE_URL = "https://ipva.sefaz.ce.gov.br/api"
    
    @property
    def name(self) -> str:
        return "consultar_ipva"
    
    @property
    def description(self) -> str:
        return """
                   EXCLUSIVO para IPVA do Ceará (SEFAZ-CE).
                    Esta ferramenta obtém AUTOMATICAMENTE valores, vencimentos e códigos de barras.
                    
                    REGRAS DE USO:
                    1. Requer APENAS 'placa' e 'renavam'. 
                    2. NUNCA peça ao usuário: valor da parcela, número de contrato, banco ou data de vencimento.
                    3. Se o usuário quiser 'emitir_boleto', você deve 'consultar' primeiro para obter a lista de parcelas disponíveis, a menos que ele já tenha especificado o número da parcela (ex: 1, 2).
                """

    
    def _get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "placa": {
                    "type": "string",
                    "description": "Placa do veículo. Formato AAA1234. Não peça outros dados aqui."
                },
                "renavam": {
                    "type": "string",
                    "description": "Renavam de 11 dígitos. Não confunda com número de contrato ou serviço."
                },
                "action": {
                    "type": "string",
                    "enum": ["consultar", "emitir_boleto"],
                    "description": "Use 'consultar' para ver o que deve. Use 'emitir_boleto' para gerar o pagamento."
                },
                "parcelas": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Lista de números (ex: [1]). Se o usuário não disser a parcela, NÃO invente valores, apenas execute a consulta."
                }
            },
            "required": ["placa", "renavam", "action"],
            "additionalProperties": False  # Isso impede que o modelo tente injetar campos fantasmas
        }
    
    async def execute(
        self, 
        placa: str, 
        renavam: str, 
        action: str = "consultar",
        parcelas: list = None
    ) -> Dict[str, Any]:
        """Executa consulta ou emissão de IPVA"""
        try:
            if action == "consultar":
                return await self._consultar_veiculo(placa, renavam)
            
            elif action == "emitir_boleto":
                if not parcelas:
                    return {
                        "success": False,
                        "error": "Preciso saber qual(is) parcela(s) você quer emitir"
                    }
                return await self._emitir_dae(placa, renavam, parcelas)
            
            else:
                return {"success": False, "error": "Ação inválida"}
                
        except Exception as e:
            logger.error(f"Erro IPVA tool: {e}")
            return {"success": False, "error": str(e)}
    
    def _filtrar_debitos_abertos(self, debitos: List[dict], ano_ipva: int) -> List[dict]:
        """Filtra apenas débitos em aberto do ano corrente"""
        debitos_abertos = []
        
        for debito in debitos:
            if (debito.get("exercicio") == ano_ipva and 
                debito.get("codigoSituacao") == 99):
                debitos_abertos.append({
                    "id": debito.get("id"),
                    "parcela": debito.get("parcela"),
                    "vencimento": debito.get("vencimento"),
                    "valor_original": debito.get("vlrPrincipal"),
                    "valor_pagar": debito.get("totalPagarParcela"),
                    "valor_cota_unica": debito.get("totalPagarCotaUnica"),
                    "desconto_cota_unica": debito.get("totalDesconto"),
                    "tem_desconto": debito.get("percentualDescontoCotaUnica", 0) > 0
                })
        
        return debitos_abertos
    
    async def _consultar_veiculo(self, placa: str, renavam: str) -> Dict[str, Any]:
        """Consulta veículo na SEFAZ-CE"""
        url = f"{self.BASE_URL}/ipva/v1/emissaoDae/pesquisarVeiculo"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params={"placa": placa.upper(), "renavam": renavam},
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            
            if not data or "veiculo" not in data:
                return {
                    "success": False,
                    "message": "Veículo não encontrado"
                }
            
            veiculo = data.get("veiculo", {})
            debitos_raw = data.get("debitosDoVeiculo", [])
            ano_ipva = data.get("anoIpva", 2026)
            
            debitos_abertos = self._filtrar_debitos_abertos(debitos_raw, ano_ipva)
            
            if not debitos_abertos:
                return {
                    "success": True,
                    "sem_debitos": True,
                    "veiculo": {
                        "placa": veiculo.get("placa"),
                        "marca_modelo": veiculo.get("marcaModelo"),
                        "ano": f"{veiculo.get('anoFabricacao')}/{veiculo.get('anoModelo')}"
                    },
                    "message": f"Veículo encontrado mas sem débitos em aberto para {ano_ipva}"
                }
            
            total_parcelado = sum(d["valor_pagar"] for d in debitos_abertos)
            total_cota_unica = sum(d["valor_cota_unica"] for d in debitos_abertos)
            desconto_total = total_parcelado - total_cota_unica if total_cota_unica < total_parcelado else 0
            
            return {
                "success": True,
                "veiculo_id": veiculo.get("id"),
                "veiculo": {
                    "placa": veiculo.get("placa"),
                    "renavam": veiculo.get("renavam"),
                    "marca_modelo": veiculo.get("marcaModelo"),
                    "ano": f"{veiculo.get('anoFabricacao')}/{veiculo.get('anoModelo')}",
                    "tipo": veiculo.get("descricaoTipoVeiculo"),
                    "categoria": veiculo.get("descricaoCategoriaVeiculo"),
                    "municipio": veiculo.get("municipio")
                },
                "ano_ipva": ano_ipva,
                "debitos": debitos_abertos,
                "total_parcelado": total_parcelado,
                "total_cota_unica": total_cota_unica,
                "desconto_cota_unica": desconto_total,
                "percentual_desconto": data.get("descontoCotaUnica", 0),
                "quantidade_parcelas": len(debitos_abertos),
                "prazo_cota_unica": data.get("dataLimitePagamentoCotaUnica"),
                "prazo_parcelado": data.get("dataLimitePagamentoParcelado")
            }
    
    async def _emitir_dae_boleto(self,codigo_identificador,placa,parcelas):
         # 3. GERA PDF DO BOLETO (/impressaoDaes)
        logger.info(f"Gerando PDF do boleto para código {codigo_identificador}")
        
        url_gerar_pdf = f"{self.BASE_URL}/receita/v1/receitas/impressaoDaes/ipva/?qrCode=true"
        pdf_path = None
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url_gerar_pdf,
                    json=[codigo_identificador],
                    headers={
                        "Content-Type": "application/json",
                        "referer": "https://ipva.sefaz.ce.gov.br/"
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                
                # O PDF vem como bytes
                pdf_bytes = response.content
                
                # Salva o PDF localmente (simulação)
                # Em produção, você pode salvar em S3, storage temporário, etc
                pdf_filename = f"ipva_{placa}_{'-'.join(map(str, parcelas))}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
                pdf_path = os.path.join(pdf_filename)  # ou outro diretório
                
                with open(pdf_path, "wb") as f:
                    f.write(pdf_bytes)
                
                logger.info(f"PDF salvo em: {pdf_path}")
                
                return pdf_path,pdf_filename
                
        except Exception as e:
            logger.error(f"Erro ao gerar PDF: {e}")
            # Mesmo sem PDF, retorna o PIX que já funciona

    async def _emitir_dae(self, placa: str, renavam: str, parcelas: list) -> Dict[str, Any]:
        """
        Emite DAE (PIX/Boleto) - FLUXO COMPLETO
        1. Consulta veículo
        2. Gera PIX (/imprimirdae) → retorna codigoIdentificador + emvPix
        3. Gera PDF do boleto (/impressaoDaes) → usa codigoIdentificador
        """
        
        # 1. Consulta dados do veículo
        consulta = await self._consultar_veiculo(placa, renavam)
        
        if not consulta.get("success"):
            return consulta
        
        if consulta.get("sem_debitos"):
            return {
                "success": False,
                "message": "Não há débitos em aberto para emitir"
            }
        
        veiculo_id = consulta["veiculo_id"]
        debitos = consulta.get("debitos", [])
        ano_ipva = consulta.get("ano_ipva", 2026)
        
        # Valida parcelas
        parcelas_disponiveis = [d["parcela"] for d in debitos]
        parcelas_invalidas = [p for p in parcelas if p not in parcelas_disponiveis]
        
        if parcelas_invalidas:
            return {
                "success": False,
                "message": f"Parcela(s) {parcelas_invalidas} não disponível(is). Disponíveis: {parcelas_disponiveis}"
            }
        
        # Coleta IDs e calcula valor total
        ids_emitir = []
        valor_total = 0
        
        for parcela_num in parcelas:
            for deb in debitos:
                if deb["parcela"] == parcela_num:
                    ids_emitir.append(str(deb["id"]))
                    valor_total += deb["valor_pagar"]
        
        # 2. GERA PIX (/imprimirdae)
        logger.info(f"Gerando PIX para parcelas {parcelas}")


        payload_pix = {
            "ids": ids_emitir,
            "parcelas": parcelas,
            "veiculoId": veiculo_id,
            "exercicios": [str(ano_ipva)],
            "exercicioCorrente": ano_ipva,
            "tipoEmissaoDae": 3,  # PIX
            "dataPagamento": debitos[0]["vencimento"],
            "valorDesconto": 0,
            "informacaoDesconto": "",
            "origem": 2
        }
        
        url_gerar_pix = f"{self.BASE_URL}/ipva/v1/emissaoDae/imprimirdae"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url_gerar_pix,
                json=payload_pix,
                headers={
                    "Content-Type": "application/json",
                    "accept":"application/json, text/plain, */*",
                    "sec-ch-ua":'''"Microsoft Edge";v="143", "Chromium";v="143", "Not A(Brand";v="24""''',
                    "referer": "https://ipva.sefaz.ce.gov.br/"
                },
                timeout=30.0
            )
            response.raise_for_status()
            pix_response = response.json()
        
        # Valida resposta do PIX
        if not pix_response or len(pix_response) == 0:
            return {
                "success": False,
                "message": "Erro ao gerar PIX"
            }
        
        # Extrai dados do PIX
        pix_data = pix_response[0]
        codigo_identificador = pix_data.get("codigoIdentificador")
        pix_copia_cola = pix_data.get("emvPix") or pix_data.get("emv")
        codigo_barras = pix_data.get("codigoBarras")
        valor_pix = pix_data.get("valorTotal")
        
        logger.info(f"PIX gerado! Código: {codigo_identificador}")
        
        # pdf_path,pdf_filename = await self._emitir_dae_boleto(codigo_identificador,placa,parcelas)
        
        # Retorna resultado completo
        return {
            "success": True,
            "codigo_identificador": codigo_identificador,
            "parcelas_emitidas": parcelas,
            "valor_total": float(valor_pix) if valor_pix else valor_total,
            "pix_copia_cola": pix_copia_cola,
            "codigo_barras": codigo_barras,
            # "pdf_path": pdf_path,  # Caminho do PDF salvo
            # "pdf_filename": pdf_filename if pdf_path else None,
            "message": "PIX e boleto gerados com sucesso!"
        }