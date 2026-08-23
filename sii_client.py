import requests
import json
from datetime import datetime

class SIIClient:
    def __init__(self, rut: str, clave: str):
        self.rut = rut.replace(".", "").replace("-", "").strip()
        self.rut_cuerpo = self.rut[:-1]
        self.dv = self.rut[-1].upper()
        self.clave = clave.strip()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-CL,es;q=0.9",
            "Referer": "https://misiir.sii.cl/cgi_misii/IEntrada.cgi"
        })

    def autenticar(self) -> bool:
        """Autenticación en SII obteniendo la cookie TOKEN."""
        login_url = "https://zeusr.sii.cl/cgi_AUT2000/CAutInicio.cgi"
        payload = {
            "rut": self.rut_cuerpo,
            "dv": self.dv,
            "referencia": "https://misiir.sii.cl/cgi_misii/IEntrada.cgi",
            "clave": self.clave
        }
        try:
            resp = self.session.post(login_url, data=payload, timeout=15)
            cookies = self.session.cookies.get_dict()
            return "TOKEN" in cookies or len(cookies) > 0
        except Exception:
            return False

    def _extraer_lista(self, resp_json) -> list:
        """Busca recursivamente listas de documentos dentro del JSON del SII."""
        if isinstance(resp_json, list):
            return resp_json
        if isinstance(resp_json, dict):
            # Probar llaves comunes del backend del SII
            data = resp_json.get("data")
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                for k in ["resumen", "detalles", "listaResumen", "listaDoc", "detalle"]:
                    if k in data and isinstance(data[k], list):
                        return data[k]
                return [data]
        return []

    def obtener_resumen_rcv(self, periodo: str = None, operacion: str = "VENTA") -> tuple[float, float, list]:
        """
        Retorna (monto_neto, monto_iva, raw_data_list)
        """
        if not periodo:
            periodo = datetime.now().strftime("%Y%m")

        url = "https://www4.sii.cl/consdcvinternetui/services/data/facadeService/getResumen"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Referer": "https://www4.sii.cl/consdcvinternetui/"
        }
        
        # El SII acepta tanto el namespace clásico como el de DIII
        data = {
            "metaData": {
                "namespace": "cl.sii.sdi.lob.diii.consdcv.data.api.interfaces.FacadeService/getResumen",
                "conversationId": self.session.cookies.get("TOKEN", ""),
                "transactionId": "1"
            },
            "data": {
                "rutEmisor": self.rut_cuerpo,
                "dvEmisor": self.dv,
                "ptributario": periodo,
                "operacion": operacion.upper(),
                "estadoContab": "REGISTRO"
            }
        }

        try:
            resp = self.session.post(url, headers=headers, json=data, timeout=15)
            if resp.status_code != 200:
                # Fallback al namespace secundario si el primero devuelve error
                data["metaData"]["namespace"] = "cl.sii.sdi.lob.dcv.cons.data.facade.interfaces.CommonDataFacadeService/getResumen"
                resp = self.session.post(url, headers=headers, json=data, timeout=15)

            if resp.status_code == 200:
                raw_list = self._extraer_lista(resp.json())
                
                total_neto = 0.0
                total_iva = 0.0
                
                for doc in raw_list:
                    if isinstance(doc, dict):
                        # Mapeo de IVA (incluyendo crédito recuperable en compras)
                        iva_val = (
                            doc.get("totalMntIvaRecuperable") or
                            doc.get("totalMntIva") or
                            doc.get("totalIvaRecuperable") or
                            doc.get("totalIva") or
                            doc.get("mntIva") or
                            doc.get("iva") or 0
                        )
                        # Mapeo de Neto
                        neto_val = (
                            doc.get("totalMntNeto") or
                            doc.get("totalNeto") or
                            doc.get("mntNeto") or
                            doc.get("neto") or 0
                        )
                        
                        # Tipo de DTE (Notas de Crédito tipo 61 restan)
                        tipo_dte = str(doc.get("tipoDoc") or doc.get("tipoDte") or "")
                        factor = -1.0 if tipo_dte in ["61", "Nota de Credito", "NC"] else 1.0
                        
                        total_iva += float(iva_val) * factor
                        total_neto += float(neto_val) * factor

                return max(0.0, total_neto), max(0.0, total_iva), raw_list
            return 0.0, 0.0, []
        except Exception:
            return 0.0, 0.0, []

    def obtener_resumen_honorarios(self, periodo: str = None) -> tuple[float, int, dict]:
        """
        Retorna (total_retencion, cantidad_docs, raw_dict)
        """
        if not periodo:
            periodo = datetime.now().strftime("%Y%m")

        anio = periodo[:4]
        mes = str(int(periodo[4:]))

        url = "https://www4.sii.cl/consbheinternetui/services/data/facadeService/getConsultaRecibidasMensual"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Referer": "https://www4.sii.cl/consbheinternetui/"
        }
        data = {
            "metaData": {
                "namespace": "cl.sii.sdi.lob.bhe.cons.data.facade.interfaces.CommonDataFacadeService/getConsultaRecibidasMensual",
                "conversationId": self.session.cookies.get("TOKEN", ""),
                "transactionId": "1"
            },
            "data": {
                "rutReceptor": self.rut_cuerpo,
                "dvReceptor": self.dv,
                "ano": anio,
                "mes": mes
            }
        }

        try:
            resp = self.session.post(url, headers=headers, json=data, timeout=15)
            if resp.status_code == 200:
                res = resp.json()
                data_dict = res.get("data", {}) if isinstance(res.get("data"), dict) else {}
                retencion = float(
                    data_dict.get("totalMntRetencion") or
                    data_dict.get("totalRetencion") or
                    data_dict.get("mntRetencion") or 0
                )
                docs = int(data_dict.get("totalDocumentos") or data_dict.get("cantidad") or 0)
                return retencion, docs, data_dict
            return 0.0, 0, {}
        except Exception:
            return 0.0, 0, {}
