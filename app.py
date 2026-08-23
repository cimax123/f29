import streamlit as st
import pandas as pd
from datetime import datetime
from sii_client import SIIClient

st.set_page_config(page_title="Dashboard F29 - SII", layout="wide", page_icon="📈")

st.title("🏛️ Provisión F29 en Vivo (SII Chile)")

RUT = st.secrets.get("SII_RUT", "").strip()
CLAVE = st.secrets.get("SII_CLAVE", "").strip()
TASA_PPM = float(st.secrets.get("TASA_PPM", 0.015))

if not RUT or not CLAVE:
    st.warning("⚠️ Debes configurar `SII_RUT` y `SII_CLAVE` en Settings > Secrets de Streamlit Cloud.")
    st.stop()

# Selector de periodo (por defecto mes actual)
col_sel1, col_sel2 = st.columns([1, 3])
with col_sel1:
    anio_actual = datetime.now().year
    mes_actual = datetime.now().month
    
    opciones_periodo = []
    # Generar últimos 6 meses para testing
    for m in range(mes_actual, max(0, mes_actual - 6), -1):
        opciones_periodo.append(f"{anio_actual}{m:02d}")
        
    periodo_seleccionado = st.selectbox("Seleccionar Periodo Tributario (AAAAMM):", opciones_periodo, index=0)

st.caption(f"RUT Contribuyente: **{RUT}** | Periodo: **{periodo_seleccionado}**")

@st.cache_data(ttl=1800, show_spinner=False)
def cargar_datos_f29(rut, clave, periodo, tasa_ppm):
    client = SIIClient(rut=rut, clave=clave)
    if not client.autenticar():
        return None, "Error de autenticación con el SII. Verifica tu RUT y Clave Tributaria."
    
    # Consultas
    neto_ventas, debito_iva, raw_ventas = client.obtener_resumen_rcv(periodo=periodo, operacion="VENTA")
    _, credito_iva, raw_compras = client.obtener_resumen_rcv(periodo=periodo, operacion="COMPRA")
    ret_honorarios, cant_bhe, raw_bhe = client.obtener_resumen_honorarios(periodo=periodo)
    
    iva_neto = max(0.0, debito_iva - credito_iva)
    remanente = max(0.0, credito_iva - debito_iva)
    ppm = neto_ventas * tasa_ppm
    total_f29 = iva_neto + ppm + ret_honorarios

    return {
        "ventas_netas": neto_ventas,
        "debito_fiscal": debito_iva,
        "credito_fiscal": credito_iva,
        "iva_neto": iva_neto,
        "remanente": remanente,
        "ppm": ppm,
        "retencion_honorarios": ret_honorarios,
        "cantidad_bhe": cant_bhe,
        "total_f29": total_f29,
        "raw_ventas": raw_ventas,
        "raw_compras": raw_compras,
        "raw_bhe": raw_bhe
    }, None

with st.spinner("Consultando Registro de Compras y Ventas en el SII..."):
    datos, error = cargar_datos_f29(RUT, CLAVE, periodo_seleccionado, TASA_PPM)

if error:
    st.error(error)
else:
    # Tarjetas KPI
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("Total F29 Estimado", f"${datos['total_f29']:,.0f}".replace(",", "."))
    kpi2.metric("IVA Débito (+)", f"${datos['debito_fiscal']:,.0f}".replace(",", "."))
    kpi3.metric("IVA Crédito (-)", f"${datos['credito_fiscal']:,.0f}".replace(",", "."))
    kpi4.metric(f"PPM ({TASA_PPM*100:.2f}%)", f"${datos['ppm']:,.0f}".replace(",", "."))
    kpi5.metric("Ret. Honorarios", f"${datos['retencion_honorarios']:,.0f}".replace(",", "."))

    st.divider()

    tab_resumen, tab_raw = st.tabs(["📊 Liquidación F29", "🔍 Diagnóstico Datos SII (Raw Data)"])

    with tab_resumen:
        detalle = [
            {"Concepto": "Ventas Netas (Base PPM)", "Monto": f"${datos['ventas_netas']:,.0f}".replace(",", ".")},
            {"Concepto": "IVA Débito Fiscal (+)", "Monto": f"${datos['debito_fiscal']:,.0f}".replace(",", ".")},
            {"Concepto": "IVA Crédito Fiscal (-)", "Monto": f"${datos['credito_fiscal']:,.0f}".replace(",", ".")},
            {"Concepto": "IVA Determinado a Pagar", "Monto": f"${datos['iva_neto']:,.0f}".replace(",", ".")},
            {"Concepto": "Remanente Crédito próx. mes", "Monto": f"${datos['remanente']:,.0f}".replace(",", ".")},
            {"Concepto": f"PPM Proyectado ({TASA_PPM*100:.2f}%)", "Monto": f"${datos['ppm']:,.0f}".replace(",", ".")},
            {"Concepto": f"Retención Honorarios ({datos['cantidad_bhe']} docs)", "Monto": f"${datos['retencion_honorarios']:,.0f}".replace(",", ".")},
            {"Concepto": "TOTAL A PAGAR F29", "Monto": f"${datos['total_f29']:,.0f}".replace(",", ".")}
        ]
        st.dataframe(pd.DataFrame(detalle), use_container_width=True, hide_index=True)

    with tab_raw:
        st.write("Si los montos salen en 0, revisa si el SII devolvió registros en estas listas:")
        c_v, c_c = st.columns(2)
        with c_v:
            st.markdown("**Respuesta RCV Ventas:**")
            st.json(datos["raw_ventas"] if datos["raw_ventas"] else {"estado": "Lista vacía o sin ventas en este periodo"})
        with c_c:
            st.markdown("**Respuesta RCV Compras:**")
            st.json(datos["raw_compras"] if datos["raw_compras"] else {"estado": "Lista vacía o sin compras en este periodo"})

if st.button("🔄 Actualizar Ahora"):
    st.cache_data.clear()
    st.rerun()
