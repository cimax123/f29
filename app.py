import streamlit as st
import pandas as pd
from datetime import datetime
from sii_client import SIIClient

st.set_page_config(page_title="Dashboard F29 en Vivo", layout="wide", page_icon="📈")

# Credenciales seguras
RUT = st.secrets.get("SII_RUT", "")
CLAVE = st.secrets.get("SII_CLAVE", "")
TASA_PPM = float(st.secrets.get("TASA_PPM", 0.015))

@st.cache_data(ttl=3600)
def consultar_impuestos_sii():
    client = SIIClient(rut=RUT, clave=CLAVE)
    if not client.autenticar():
        return None, "Error de autenticación en SII: revisa RUT y Clave Tributaria."
    
    periodo_actual = datetime.now().strftime("%Y%m")
    
    # 1. RCV Ventas y Compras
    resumen_ventas = client.obtener_resumen_rcv(periodo=periodo_actual, operacion="VENTA")
    resumen_compras = client.obtener_resumen_rcv(periodo=periodo_actual, operacion="COMPRA")
    
    debito_fiscal = 0
    ventas_netas = 0
    for doc in resumen_ventas:
        debito_fiscal += doc.get("totalIva", 0)
        ventas_netas += doc.get("totalMntNeto", 0)
        
    credito_fiscal = 0
    for doc in resumen_compras:
        credito_fiscal += doc.get("totalIvaRecuperable", doc.get("totalIva", 0))
        
    iva_neto = max(0, debito_fiscal - credito_fiscal)
    remanente = max(0, credito_fiscal - debito_fiscal)
    ppm_proyectado = ventas_netas * TASA_PPM

    # 2. Boletas de Honorarios Recibidas (Segunda Categoría)
    bhe_data = client.obtener_resumen_honorarios_recibidas(periodo=periodo_actual)
    total_honorarios_bruto = bhe_data.get("totalMntBruto", 0) if isinstance(bhe_data, dict) else 0
    total_retencion_honorarios = bhe_data.get("totalMntRetencion", 0) if isinstance(bhe_data, dict) else 0
    cantidad_bhe = bhe_data.get("totalDocumentos", 0) if isinstance(bhe_data, dict) else 0

    # 3. Total Consolidado F29
    total_f29 = iva_neto + ppm_proyectado + total_retencion_honorarios

    return {
        "periodo": periodo_actual,
        "ventas_netas": ventas_netas,
        "debito_fiscal": debito_fiscal,
        "credito_fiscal": credito_fiscal,
        "iva_neto": iva_neto,
        "remanente": remanente,
        "ppm": ppm_proyectado,
        "honorarios_bruto": total_honorarios_bruto,
        "retencion_honorarios": total_retencion_honorarios,
        "cantidad_bhe": cantidad_bhe,
        "total_f29": total_f29
    }, None

st.title("🏛️ Provisión F29 en Vivo (SII Chile)")
st.caption(f"RUT: **{RUT}** | Periodo: **{datetime.now().strftime('%m/%Y')}** | Actualización automática cada 1 hora")

datos, error = consultar_impuestos_sii()

if error:
    st.error(error)
else:
    # Métricas Principales (5 columnas)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total F29 Estimado", f"${datos['total_f29']:,.0f}".replace(",", "."))
    c2.metric("IVA Determinado", f"${datos['iva_neto']:,.0f}".replace(",", "."))
    c3.metric("PPM Proyectado", f"${datos['ppm']:,.0f}".replace(",", "."))
    c4.metric("Retención Honorarios", f"${datos['retencion_honorarios']:,.0f}".replace(",", "."))
    c5.metric("Remanente IVA Crédito", f"${datos['remanente']:,.0f}".replace(",", "."))

    st.divider()

    # Tabla Desglose F29
    st.subheader("📋 Composición de la Liquidación Provisional")
    detalle = [
        {"Línea / Concepto": "Ventas Netas del Mes (Base Imponible PPM)", "Monto": f"${datos['ventas_netas']:,.0f}".replace(",", ".")},
        {"Línea / Concepto": "IVA Débito Fiscal (+)", "Monto": f"${datos['debito_fiscal']:,.0f}".replace(",", ".")},
        {"Línea / Concepto": "IVA Crédito Fiscal (-)", "Monto": f"${datos['credito_fiscal']:,.0f}".replace(",", ".")},
        {"Línea / Concepto": "IVA a Pagar (Cód. 89)", "Monto": f"${datos['iva_neto']:,.0f}".replace(",", ".")},
        {"Línea / Concepto": f"PPM Régimen General ({TASA_PPM*100:.2f}%) (Cód. 62)", "Monto": f"${datos['ppm']:,.0f}".replace(",", ".")},
        {"Línea / Concepto": f"Retención Boletas 2da Cat. ({datos['cantidad_bhe']} docs) (Cód. 151)", "Monto": f"${datos['retencion_honorarios']:,.0f}".replace(",", ".")},
        {"Línea / Concepto": "TOTAL A PAGAR ESTIMADO F29 (Cód. 91)", "Monto": f"${datos['total_f29']:,.0f}".replace(",", ".")}
    ]
    st.dataframe(pd.DataFrame(detalle), use_container_width=True, hide_index=True)

if st.button("🔄 Forzar actualización desde SII"):
    st.cache_data.clear()
    st.rerun()
