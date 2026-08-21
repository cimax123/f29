import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Dashboard Tributario", layout="wide", page_icon="📊")

st.title("📊 Monitor de Provisión de Impuestos (F29)")
st.caption(f"Última actualización del sistema: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")

# Caché con tiempo de expiración de 1 hora (3600 segundos)
@st.cache_data(ttl=3600)
def cargar_calculos():
    # Aquí conectas tus datos o lees tu archivo
    # Simulamos los datos del periodo:
    ventas_netas = 12500000
    debito_fiscal = ventas_netas * 0.19
    credito_fiscal = 1450000
    tasa_ppm = 0.015
    ppm = ventas_netas * tasa_ppm
    retencion_honorarios = 320000
    
    iva_neto = max(0, debito_fiscal - credito_fiscal)
    total_f29 = iva_neto + ppm + retencion_honorarios
    
    return {
        "ventas_netas": ventas_netas,
        "debito_fiscal": debito_fiscal,
        "credito_fiscal": credito_fiscal,
        "iva_neto": iva_neto,
        "ppm": ppm,
        "retencion_honorarios": retencion_honorarios,
        "total_f29": total_f29
    }

datos = cargar_calculos()

# KPIs Principales
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total F29 Estimado", f"${datos['total_f29']:,.0f}".replace(",", "."))
col2.metric("IVA Determinado", f"${datos['iva_neto']:,.0f}".replace(",", "."))
col3.metric("PPM Proyectado", f"${datos['ppm']:,.0f}".replace(",", "."))
col4.metric("Retención Honorarios", f"${datos['retencion_honorarios']:,.0f}".replace(",", "."))

st.divider()

# Desglose en tabla
st.subheader("Desglose de la Liquidación Provisional")
df_resumen = pd.DataFrame([
    {"Concepto": "IVA Débito Fiscal (+)", "Monto": datos["debito_fiscal"]},
    {"Concepto": "IVA Crédito Fiscal (-)", "Monto": datos["credito_fiscal"]},
    {"Concepto": "IVA a Pagar", "Monto": datos["iva_neto"]},
    {"Concepto": "PPM Régimen General", "Monto": datos["ppm"]},
    {"Concepto": "Retención Boletas 2da Cat.", "Monto": datos["retencion_honorarios"]},
])
df_resumen["Monto Formateado"] = df_resumen["Monto"].apply(lambda x: f"${x:,.0f}".replace(",", "."))
st.dataframe(df_resumen[["Concepto", "Monto Formateado"]], use_container_width=True, hide_index=True)

if st.button("🔄 Forzar actualización ahora"):
    st.cache_data.clear()
    st.rerun()