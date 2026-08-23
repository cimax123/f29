import streamlit as st
import pandas as pd
from datetime import datetime
from sii_client import SIIClient

st.set_page_config(page_title="Dashboard F29 - Provisión", layout="wide", page_icon="📈")

st.title("🏛️ Provisión F29 en Vivo (SII Chile)")

# 1. Credenciales desde Secrets
RUT = st.secrets.get("SII_RUT", "").strip()
CLAVE = st.secrets.get("SII_CLAVE", "").strip()

if not RUT or not CLAVE:
    st.warning("⚠️ Debes configurar `SII_RUT` y `SII_CLAVE` en Settings > Secrets de Streamlit Cloud.")
    st.stop()

# 2. Configuración y Parámetros en Barra Lateral
st.sidebar.header("⚙️ Parámetros Tributarios")

# Factor PPM editable (por defecto 0.125%)
tasa_ppm_pct = st.sidebar.number_input(
    "Tasa PPM (%):",
    min_value=0.000,
    max_value=10.000,
    value=float(st.secrets.get("TASA_PPM", 0.125)),
    step=0.025,
    format="%.3f"
)
tasa_ppm = tasa_ppm_pct / 100.0

# Remanente del mes anterior (arrastrado de meses previos como junio/julio)
remanente_anterior = st.sidebar.number_input(
    "Remanente Crédito Fiscal mes anterior ($):",
    min_value=0,
    value=0,
    step=10000,
    help="Ingresa el remanente de IVA acumulado proveniente del F29 del mes anterior (Cód. 77)."
)

# Selector de periodo
anio_actual = datetime.now().year
mes_actual = datetime.now().month
opciones_periodo = [f"{anio_actual}{m:02d}" for m in range(mes_actual, max(0, mes_actual - 6), -1)]
periodo_seleccionado = st.selectbox("Periodo Tributario (AAAAMM):", opciones_periodo, index=0)

st.caption(f"RUT Contribuyente: **{RUT}** | Periodo: **{periodo_seleccionado}** | Tasa PPM: **{tasa_ppm_pct:.3f}%**")

# 3. Función de extracción y cálculo
@st.cache_data(ttl=1800, show_spinner=False)
def cargar_datos_f29(rut, clave, periodo, tasa, rem_ant):
    client = SIIClient(rut=rut, clave=clave)
    if not client.autenticar():
        return None, "Error de autenticación con el SII. Verifica tu RUT y Clave Tributaria."
    
    # Consultas RCV y BHE
    neto_ventas, debito_iva, raw_ventas = client.obtener_resumen_rcv(periodo=periodo, operacion="VENTA")
    _, credito_iva, raw_compras = client.obtener_resumen_rcv(periodo=periodo, operacion="COMPRA")
    ret_honorarios, cant_bhe, _ = client.obtener_resumen_honorarios(periodo=periodo)
    
    # ─── LÓGICA DE LIQUIDACIÓN IVA (F29) ───
    # Total crédito disponible = Compras del mes + Remanente arrastrado
    credito_total_disponible = credito_iva + rem_ant
    
    if debito_iva >= credito_total_disponible:
        iva_determinado = debito_iva - credito_total_disponible
        nuevo_remanente = 0.0
    else:
        iva_determinado = 0.0
        nuevo_remanente = credito_total_disponible - debito_iva

    # PPM y Retenciones
    ppm = neto_ventas * tasa
    total_f29 = iva_determinado + ppm + ret_honorarios

    return {
        "ventas_netas": neto_ventas,
        "debito_fiscal": debito_iva,
        "credito_fiscal_mes": credito_iva,
        "remanente_anterior": rem_ant,
        "credito_total_disponible": credito_total_disponible,
        "iva_a_pagar": iva_determinado,
        "nuevo_remanente_proximo_mes": nuevo_remanente,
        "ppm": ppm,
        "retencion_honorarios": ret_honorarios,
        "cantidad_bhe": cant_bhe,
        "total_f29": total_f29,
        "raw_ventas": raw_ventas,
        "raw_compras": raw_compras
    }, None

with st.spinner("Consultando datos en el SII..."):
    datos, error = cargar_datos_f29(RUT, CLAVE, periodo_seleccionado, tasa_ppm, remanente_anterior)

if error:
    st.error(error)
else:
    # 4. Tarjetas KPI
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total F29 Estimado", f"${datos['total_f29']:,.0f}".replace(",", "."))
    k2.metric("IVA Débito (+)", f"${datos['debito_fiscal']:,.0f}".replace(",", "."))
    k3.metric("IVA Crédito Total (-)", f"${datos['credito_total_disponible']:,.0f}".replace(",", "."))
    k4.metric(f"PPM ({tasa_ppm_pct:.3f}%)", f"${datos['ppm']:,.0f}".replace(",", "."))
    k5.metric("Remanente a favor próx. mes", f"${datos['nuevo_remanente_proximo_mes']:,.0f}".replace(",", "."))

    st.divider()

    # 5. Desglose detallado del F29
    st.subheader("📋 Composición y Arrastre de Crédito Fiscal")
    
    detalle = [
        {"Concepto": "Ventas Netas del Periodo (Base PPM)", "Monto": f"${datos['ventas_netas']:,.0f}".replace(",", ".")},
        {"Concepto": "(+) Débito Fiscal del Mes (Ventas)", "Monto": f"${datos['debito_fiscal']:,.0f}".replace(",", ".")},
        {"Concepto": "(-) Crédito Fiscal del Mes (Compras)", "Monto": f"-${datos['credito_fiscal_mes']:,.0f}".replace(",", ".")},
        {"Concepto": "(-) Remanente Crédito Fiscal Mes Anterior (Cód. 77)", "Monto": f"-${datos['remanente_anterior']:,.0f}".replace(",", ".")},
        {"Concepto": "(=) IVA Determinado a Pagar (Cód. 89)", "Monto": f"${datos['iva_a_pagar']:,.0f}".replace(",", ".")},
        {"Concepto": "(=) Remanente Crédito para Mes Siguiente (Cód. 504)", "Monto": f"${datos['nuevo_remanente_proximo_mes']:,.0f}".replace(",", ".")},
        {"Concepto": f"(+) PPM Determinado ({tasa_ppm_pct:.3f}%) (Cód. 62)", "Monto": f"${datos['ppm']:,.0f}".replace(",", ".")},
        {"Concepto": f"(+) Retención Boletas Honorarios ({datos['cantidad_bhe']} docs) (Cód. 151)", "Monto": f"${datos['retencion_honorarios']:,.0f}".replace(",", ".")},
        {"Concepto": "TOTAL A PAGAR F29 PROYECTADO", "Monto": f"${datos['total_f29']:,.0f}".replace(",", ".")}
    ]
    st.dataframe(pd.DataFrame(detalle), use_container_width=True, hide_index=True)

if st.button("🔄 Actualizar Datos"):
    st.cache_data.clear()
    st.rerun()
