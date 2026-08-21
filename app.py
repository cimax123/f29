import streamlit as st
import pandas as pd
from datetime import datetime
from sii_client import SIIClient

st.set_page_config(page_title="Dashboard F29 en Vivo", layout="wide", page_icon="📈")

st.title("🏛️ Provisión F29 en Vivo (SII Chile)")

# 1. Validación temprana de Secrets
rut_secret = st.secrets.get("SII_RUT", "").strip()
clave_secret = st.secrets.get("SII_CLAVE", "").strip()
tasa_ppm = float(st.secrets.get("TASA_PPM", 0.015))

if not rut_secret or not clave_secret:
    st.warning("⚠️ **Faltan las credenciales en Streamlit Cloud.**")
    st.info("""
    Para configurarlas:
    1. Ve a la esquina inferior derecha: **Manage app** > **Settings** > **Secrets**.
    2. Agrega las claves `SII_RUT`, `SII_CLAVE` y `TASA_PPM`.
    """)
    st.stop()

st.caption(f"RUT Contribuyente: **{rut_secret}** | Periodo: **{datetime.now().strftime('%m/%Y')}** | Actualización horaria")

@st.cache_data(ttl=3600, show_spinner=False)
def consultar_impuestos_sii(rut, clave, ppm_rate):
    client = SIIClient(rut=rut, clave=clave)
    
    if not client.autenticar():
        return None, "Error de autenticación: el SII rechazó el RUT o la Clave Tributaria, o bloqueó la conexión desde el servidor."
    
    periodo_actual = datetime.now().strftime("%Y%m")
    
    # RCV Ventas y Compras
    resumen_ventas = client.obtener_resumen_rcv(periodo=periodo_actual, operacion="VENTA") or []
    resumen_compras = client.obtener_resumen_rcv(periodo=periodo_actual, operacion="COMPRA") or []
    
    debito_fiscal = 0.0
    ventas_netas = 0.0
    if isinstance(resumen_ventas, list):
        for doc in resumen_ventas:
            if isinstance(doc, dict):
                debito_fiscal += float(doc.get("totalIva", 0) or 0)
                ventas_netas += float(doc.get("totalMntNeto", 0) or 0)
        
    credito_fiscal = 0.0
    if isinstance(resumen_compras, list):
        for doc in resumen_compras:
            if isinstance(doc, dict):
                iva_rec = doc.get("totalIvaRecuperable")
                if iva_rec is None:
                    iva_rec = doc.get("totalIva", 0)
                credito_fiscal += float(iva_rec or 0)
        
    iva_neto = max(0.0, debito_fiscal - credito_fiscal)
    remanente = max(0.0, credito_fiscal - debito_fiscal)
    ppm_proyectado = ventas_netas * ppm_rate

    # Boletas de Honorarios Recibidas
    bhe_data = client.obtener_resumen_honorarios_recibidas(periodo=periodo_actual) or {}
    total_retencion = float(bhe_data.get("totalMntRetencion", 0) or 0) if isinstance(bhe_data, dict) else 0.0
    cantidad_bhe = int(bhe_data.get("totalDocumentos", 0) or 0) if isinstance(bhe_data, dict) else 0

    total_f29 = iva_neto + ppm_proyectado + total_retencion

    return {
        "periodo": periodo_actual,
        "ventas_netas": ventas_netas,
        "debito_fiscal": debito_fiscal,
        "credito_fiscal": credito_fiscal,
        "iva_neto": iva_neto,
        "remanente": remanente,
        "ppm": ppm_proyectado,
        "retencion_honorarios": total_retencion,
        "cantidad_bhe": cantidad_bhe,
        "total_f29": total_f29
    }, None

with st.spinner("Conectando con el SII y calculando liquidación F29..."):
    datos, error = consultar_impuestos_sii(rut_secret, clave_secret, tasa_ppm)

if error:
    st.error(error)
else:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total F29 Estimado", f"${datos['total_f29']:,.0f}".replace(",", "."))
    c2.metric("IVA Débito", f"${datos['debito_fiscal']:,.0f}".replace(",", "."))
    c3.metric("IVA Crédito", f"${datos['credito_fiscal']:,.0f}".replace(",", "."))
    c4.metric("PPM", f"${datos['ppm']:,.0f}".replace(",", "."))
    c5.metric("Ret. Honorarios", f"${datos['retencion_honorarios']:,.0f}".replace(",", "."))

    st.divider()

    st.subheader("📋 Resumen de la Provisión")
    detalle = [
        {"Línea": "Ventas Netas del Mes", "Monto": f"${datos['ventas_netas']:,.0f}".replace(",", ".")},
        {"Línea": "IVA Débito Fiscal (+)", "Monto": f"${datos['debito_fiscal']:,.0f}".replace(",", ".")},
        {"Línea": "IVA Crédito Fiscal (-)", "Monto": f"${datos['credito_fiscal']:,.0f}".replace(",", ".")},
        {"Línea": "IVA a Pagar (Cód. 89)", "Monto": f"${datos['iva_neto']:,.0f}".replace(",", ".")},
        {"Línea": f"PPM Régimen ({tasa_ppm*100:.2f}%) (Cód. 62)", "Monto": f"${datos['ppm']:,.0f}".replace(",", ".")},
        {"Línea": f"Retención Honorarios ({datos['cantidad_bhe']} docs) (Cód. 151)", "Monto": f"${datos['retencion_honorarios']:,.0f}".replace(",", ".")},
        {"Línea": "TOTAL A PAGAR F29 (Cód. 91)", "Monto": f"${datos['total_f29']:,.0f}".replace(",", ".")}
    ]
    st.dataframe(pd.DataFrame(detalle), use_container_width=True, hide_index=True)

if st.button("🔄 Actualizar Datos"):
    st.cache_data.clear()
    st.rerun()
