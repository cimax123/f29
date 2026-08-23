import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from sii_client import SIIClient

# Configuración de página
st.set_page_config(
    page_title="Dashboard Tributario | F29 SII",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados para tarjetas y métricas limpias
st.markdown("""
<style>
    .kpi-box {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .kpi-title {
        font-size: 0.82rem;
        color: #6c757d;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    .kpi-value {
        font-size: 1.6rem;
        color: #1a1a1a;
        font-weight: 700;
        line-height: 1.2;
    }
    .kpi-sub {
        font-size: 0.78rem;
        color: #adb5bd;
        margin-top: 4px;
    }
    .badge-primary {
        background-color: #0d6efd;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# 1. Credenciales
RUT = st.secrets.get("SII_RUT", "").strip()
CLAVE = st.secrets.get("SII_CLAVE", "").strip()

if not RUT or not CLAVE:
    st.warning("⚠️ Debes configurar `SII_RUT` y `SII_CLAVE` en Settings > Secrets de Streamlit Cloud.")
    st.stop()

# 2. Barra lateral con controles
with st.sidebar:
    st.title("⚙️ Parámetros F29")
    
    tasa_ppm_pct = st.number_input(
        "Tasa PPM (%):",
        min_value=0.000,
        max_value=10.000,
        value=float(st.secrets.get("TASA_PPM", 0.125)),
        step=0.025,
        format="%.3f"
    )
    tasa_ppm = tasa_ppm_pct / 100.0

    remanente_anterior = st.number_input(
        "Remanente Mes Anterior ($):",
        min_value=0,
        value=0,
        step=10000,
        help="Remanente de Crédito Fiscal proveniente del mes anterior (Cód. 77)."
    )

    anio_actual = datetime.now().year
    mes_actual = datetime.now().month
    opciones_periodo = [f"{anio_actual}{m:02d}" for m in range(mes_actual, max(0, mes_actual - 6), -1)]
    periodo_seleccionado = st.selectbox("Periodo Tributario (AAAAMM):", opciones_periodo, index=0)

    st.markdown("---")
    if st.button("🔄 Forzar Actualización", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# 3. Lógica de consulta y cálculos
@st.cache_data(ttl=1800, show_spinner=False)
def cargar_datos_f29(rut, clave, periodo, tasa, rem_ant):
    client = SIIClient(rut=rut, clave=clave)
    if not client.autenticar():
        return None, "Error de autenticación con el SII. Verifica tu RUT y Clave Tributaria."
    
    neto_ventas, debito_iva, raw_ventas = client.obtener_resumen_rcv(periodo=periodo, operacion="VENTA")
    _, credito_iva, raw_compras = client.obtener_resumen_rcv(periodo=periodo, operacion="COMPRA")
    ret_honorarios, cant_bhe, _ = client.obtener_resumen_honorarios(periodo=periodo)
    
    credito_total_disponible = credito_iva + rem_ant
    
    if debito_iva >= credito_total_disponible:
        iva_determinado = debito_iva - credito_total_disponible
        nuevo_remanente = 0.0
    else:
        iva_determinado = 0.0
        nuevo_remanente = credito_total_disponible - debito_iva

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

# Header Principal
st.subheader("🏛️ Monitor Tributario: Liquidación Provisional F29")
st.markdown(f"Contribuyente: **{RUT}** &nbsp;|&nbsp; Periodo: **{periodo_seleccionado}** &nbsp;|&nbsp; Tasa PPM: **{tasa_ppm_pct:.3f}%**")

with st.spinner("Sincronizando información con el SII..."):
    datos, error = cargar_datos_f29(RUT, CLAVE, periodo_seleccionado, tasa_ppm, remanente_anterior)

if error:
    st.error(error)
else:
    # 4. Tarjetas KPI superiores
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(f"""
        <div class="kpi-box" style="border-left: 5px solid #0d6efd;">
            <div class="kpi-title">Total F29 Proyectado</div>
            <div class="kpi-value">${datos['total_f29']:,.0f}</div>
            <div class="kpi-sub">Obligación estimada</div>
        </div>
        """.replace(",", "."), unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="kpi-box" style="border-left: 5px solid #dc3545;">
            <div class="kpi-title">IVA Determinado</div>
            <div class="kpi-value">${datos['iva_a_pagar']:,.0f}</div>
            <div class="kpi-sub">Débito menos Créditos</div>
        </div>
        """.replace(",", "."), unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="kpi-box" style="border-left: 5px solid #198754;">
            <div class="kpi-title">Remanente a Favor</div>
            <div class="kpi-value">${datos['nuevo_remanente_proximo_mes']:,.0f}</div>
            <div class="kpi-sub">Pasa al mes siguiente</div>
        </div>
        """.replace(",", "."), unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="kpi-box" style="border-left: 5px solid #ffc107;">
            <div class="kpi-title">PPM Proyectado</div>
            <div class="kpi-value">${datos['ppm']:,.0f}</div>
            <div class="kpi-sub">Base: ${datos['ventas_netas']:,.0f}</div>
        </div>
        """.replace(",", "."), unsafe_allow_html=True)

    with col5:
        st.markdown(f"""
        <div class="kpi-box" style="border-left: 5px solid #6f42c1;">
            <div class="kpi-title">Ret. Honorarios</div>
            <div class="kpi-value">${datos['retencion_honorarios']:,.0f}</div>
            <div class="kpi-sub">{datos['cantidad_bhe']} boletas recibidas</div>
        </div>
        """.replace(",", "."), unsafe_allow_html=True)

    # Estado tributario
    if datos['total_f29'] == 0 and datos['nuevo_remanente_proximo_mes'] > 0:
        st.success(f"✅ **Sin pago de F29 proyectado.** Tienes un Remanente de Crédito Fiscal disponible de **${datos['nuevo_remanente_proximo_mes']:,.0f}** para el próximo periodo.".replace(",", "."))
    else:
        st.info(f"💡 **Total estimado a pagar al SII el próximo mes:** **${datos['total_f29']:,.0f}**".replace(",", "."))

    st.markdown("---")

    # 5. Visualización Gráfica + Tabla
    tab_grafico, tab_tabla, tab_raw = st.tabs(["📊 Flujo de Liquidación (Waterfall)", "📋 Tabla Detallada F29", "🔍 Auditoría SII (Raw Data)"])

    with tab_grafico:
        # Construcción del gráfico Cascada (Waterfall)
        wf_labels = ["IVA Débito (+)", "IVA Compras (-)", "Remanente Ant. (-)", "IVA Neto", "PPM (+)", "Ret. BHE (+)", "Total F29"]
        wf_values = [
            datos["debito_fiscal"],
            -min(datos["credito_fiscal_mes"], datos["debito_fiscal"]),
            -min(datos["remanente_anterior"], max(0, datos["debito_fiscal"] - datos["credito_fiscal_mes"])),
            datos["iva_a_pagar"],
            datos["ppm"],
            datos["retencion_honorarios"],
            datos["total_f29"]
        ]
        
        fig = go.Figure(go.Waterfall(
            name="F29",
            orientation="v",
            measure=["relative", "relative", "relative", "total", "relative", "relative", "total"],
            x=wf_labels,
            textposition="outside",
            text=[f"${abs(v):,.0f}".replace(",", ".") for v in wf_values],
            y=wf_values,
            connector={"line": {"color": "#6c757d"}},
            decreasing={"marker": {"color": "#198754"}},  # Verde: rebaja el impuesto
            increasing={"marker": {"color": "#dc3545"}},  # Rojo: suma impuesto
            totals={"marker": {"color": "#0d6efd"}}        # Azul: subtotales y total
        ))

        fig.update_layout(
            title="Composición y Flujo de Impuestos a Pagar",
            waterfallgap=0.3,
            plot_bgcolor="rgba(0,0,0,0)",
            height=420,
            margin=dict(l=20, r=20, t=50, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab_tabla:
        detalle = [
            {"Sección": "1. Base Imponible", "Línea / Concepto": "Ventas Netas del Mes", "Monto": f"${datos['ventas_netas']:,.0f}".replace(",", ".")},
            {"Sección": "2. Impuesto al Valor Agregado", "Línea / Concepto": "(+) Débito Fiscal del Mes (Ventas)", "Monto": f"${datos['debito_fiscal']:,.0f}".replace(",", ".")},
            {"Sección": "2. Impuesto al Valor Agregado", "Línea / Concepto": "(-) Crédito Fiscal del Mes (Compras)", "Monto": f"-${datos['credito_fiscal_mes']:,.0f}".replace(",", ".")},
            {"Sección": "2. Impuesto al Valor Agregado", "Línea / Concepto": "(-) Remanente Mes Anterior (Cód. 77)", "Monto": f"-${datos['remanente_anterior']:,.0f}".replace(",", ".")},
            {"Sección": "2. Impuesto al Valor Agregado", "Línea / Concepto": "(=) IVA Determinado a Pagar (Cód. 89)", "Monto": f"${datos['iva_a_pagar']:,.0f}".replace(",", ".")},
            {"Sección": "2. Impuesto al Valor Agregado", "Línea / Concepto": "(=) Nuevo Remanente Mes Siguiente (Cód. 504)", "Monto": f"${datos['nuevo_remanente_proximo_mes']:,.0f}".replace(",", ".")},
            {"Sección": "3. Pagos Provisionales", "Línea / Concepto": f"(+) PPM Régimen ({tasa_ppm_pct:.3f}%) (Cód. 62)", "Monto": f"${datos['ppm']:,.0f}".replace(",", ".")},
            {"Sección": "4. Retenciones 2da Cat.", "Línea / Concepto": f"(+) Retención Boletas Honorarios ({datos['cantidad_bhe']} docs) (Cód. 151)", "Monto": f"${datos['retencion_honorarios']:,.0f}".replace(",", ".")},
            {"Sección": "5. Liquidación Final", "Línea / Concepto": "TOTAL A PAGAR F29 PROYECTADO", "Monto": f"${datos['total_f29']:,.0f}".replace(",", ".")}
        ]
        df_tab = pd.DataFrame(detalle)
        st.dataframe(df_tab, use_container_width=True, hide_index=True)

    with tab_raw:
        c_v, c_c = st.columns(2)
        with c_v:
            st.markdown("**Documentos de Venta (RCV):**")
            st.json(datos["raw_ventas"])
        with c_c:
            st.markdown("**Documentos de Compra (RCV):**")
            st.json(datos["raw_compras"])
