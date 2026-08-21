import requests
import json
from datetime import datetime

class SIIClient:
    def __init__(self, rut: str, clave: str):
        self.rut = rut.replace(".", "").replace("-", "")
        self.rut_cuerpo = self.rut[:-1]
        self.dv = self.rut[-1].upper()
        self.clave = clave
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://zeus.sii.cl/"
        })

    def autenticar(self) -> bool:
        """Inicia sesión en el portal del SII con Clave Tributaria."""
        login_url = "https://zeusr.sii.cl/cgi_AUT2000/CAutInicio.cgi"
        payload = {
            "rut": self.rut_cuerpo,
            "dv": self.dv,
            "referencia": "https://misiir.sii.cl/cgi_misii/IEntrada.cgi",
            "clave": self.clave
        }
        
        self.session.post(login_url, data=payload)
        cookies = self.session.cookies.get_dict()
        return "TOKEN" in cookies or len(cookies) > 0

    def obtener_resumen_rcv(self, periodo: str = None, operacion: str = "VENTA") -> list:
        """
        Consulta el resumen de compras o ventas del RCV.
        - periodo: 'YYYYMM'
        - operacion: 'VENTA' o 'COMPRA'
        """
        if not periodo:
            periodo = datetime.now().strftime("%Y%m")

        url = "https://www4.sii.cl/consdcvinternetui/services/data/facadeService/getResumen"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*"
        }
        data = {
            "metaData": {
                "namespace": "cl.sii.sdi.lob.dcv.cons.data.facade.interfaces.CommonDataFacadeService/getResumen",
                "conversationId": self.session.cookies.get("TOKEN", ""),
                "transactionId": "1"
            },
            "data": {
                "rutEmisor": self.rut_cuerpo,
                "dvEmisor": self.dv,
                "ptributario": periodo,
                "operacion": operacion,
                "estadoContab": "REGISTRO"
            }
        }

        try:
            resp = self.session.post(url, headers=headers, json=data, timeout=15)
            if resp.status_code == 200:
                res = resp.json()
                return res.get("data", [])
        except Exception:
            return []
        return []

    def obtener_resumen_honorarios_recibidas(self, periodo: str = None) -> dict:
        """
        Consulta el resumen de Boletas de Honorarios Electrónicas recibidas (con retención retenida por la empresa).
        - periodo: 'YYYYMM'
        """
        if not periodo:
            periodo = datetime.now().strftime("%Y%m")
        
        anio = periodo[:4]
        mes = str(int(periodo[4:]))  # '04' -> '4' o '08' -> '8'

        url = "https://www4.sii.cl/consbheinternetui/services/data/facadeService/getConsultaRecibidasMensual"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*"
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
                return res.get("data", {})
        except Exception:
            return {}
        return {}