"""Dashboard de vendas Zig/NetPDV."""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from metrics import compute_metrics
from zig_client import ZigClient, ZigConfig

st.set_page_config(
    page_title="Dashboard Zig",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 1.2rem 1.4rem;
        border: 1px solid rgba(255,255,255,0.08);
        min-height: 120px;
    }
    .metric-label {
        color: #94a3b8;
        font-size: 0.85rem;
        margin-bottom: 0.3rem;
    }
    .metric-value {
        color: #f8fafc;
        font-size: 1.8rem;
        font-weight: 700;
        line-height: 1.2;
    }
    .header-title {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .header-subtitle {
        color: #64748b;
        margin-bottom: 1.5rem;
    }
</style>
"""


def get_config() -> ZigConfig:
    try:
        secrets = st.secrets
        username = secrets["ZIG_USERNAME"]
        password = secrets["ZIG_PASSWORD"]
        event_id = int(secrets.get("ZIG_EVENT_ID", 38049))
        partner_code = secrets.get("ZIG_PARTNER_CODE", "09C7DF1421")
    except Exception:
        username = os.getenv("ZIG_USERNAME", "")
        password = os.getenv("ZIG_PASSWORD", "")
        event_id = int(os.getenv("ZIG_EVENT_ID", "38049"))
        partner_code = os.getenv("ZIG_PARTNER_CODE", "09C7DF1421")

    return ZigConfig(
        username=username,
        password=password,
        event_id=event_id,
        partner_code=partner_code,
    )


def format_currency(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def metric_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=300, show_spinner=False)
def load_dashboard_data(
    username: str,
    password: str,
    event_id: int,
    partner_code: str,
) -> dict:
    config = ZigConfig(
        username=username,
        password=password,
        event_id=event_id,
        partner_code=partner_code,
    )
    client = ZigClient(config)
    client.login()

    period_start, period_end = client.get_event_period()
    event_name = client.get_event_name()
    transactions = client.fetch_transactions(period_start, period_end)
    pending_prints = client.fetch_pending_prints()
    indicators = client.fetch_dashboard_indicators(period_start, period_end)
    metrics = compute_metrics(transactions, pending_prints, indicators)

    return {
        "event_name": event_name,
        "period_start": period_start,
        "period_end": period_end,
        "transactions": transactions,
        "pending_prints": pending_prints,
        "metrics": metrics.as_dict(),
        "updated_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }


def render_charts(transactions: list[dict]) -> None:
    if not transactions:
        st.info("Sem transações para exibir nos gráficos.")
        return

    df = pd.DataFrame(transactions)
    col1, col2 = st.columns(2)

    with col1:
        if "nome_ponto" in df.columns and "valor" in df.columns:
            by_point = (
                df.groupby("nome_ponto", as_index=False)["valor"]
                .sum()
                .sort_values("valor", ascending=False)
                .head(10)
            )
            if not by_point.empty:
                by_point["valor_formatado"] = by_point["valor"].map(format_currency)
                fig = px.bar(
                    by_point,
                    x="nome_ponto",
                    y="valor",
                    title="Top 10 pontos por faturamento",
                    labels={"nome_ponto": "Ponto", "valor": "Valor (R$)"},
                    color="valor",
                    color_continuous_scale="Blues",
                    text="valor_formatado",
                )
                fig.update_traces(
                    textposition="outside",
                    textfont=dict(size=12, color="#f8fafc"),
                    cliponaxis=False,
                )
                fig.update_layout(
                    showlegend=False,
                    height=420,
                    margin=dict(t=80, b=80),
                    yaxis=dict(rangemode="tozero"),
                )
                fig.update_yaxes(tickprefix="R$ ")
                st.plotly_chart(fig, use_container_width=True)

    with col2:
        if "operacao" in df.columns:
            by_operation = df["operacao"].value_counts().reset_index()
            by_operation.columns = ["operacao", "quantidade"]
            fig = px.pie(
                by_operation,
                names="operacao",
                values="quantidade",
                title="Distribuição por operação",
                hole=0.45,
            )
            fig.update_layout(height=380)
            st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    config = get_config()

    with st.sidebar:
        st.title("⚙️ Configurações")
        st.caption("Credenciais via Streamlit Secrets ou variáveis de ambiente.")

        if not config.username or not config.password:
            st.warning("Configure ZIG_USERNAME e ZIG_PASSWORD nos secrets.")
            st.code(
                """[secrets]
ZIG_USERNAME = "seu.usuario"
ZIG_PASSWORD = "sua_senha"
ZIG_EVENT_ID = "38049"
ZIG_PARTNER_CODE = "09C7DF1421"
""",
                language="toml",
            )

        event_id = st.number_input("ID do Evento", value=config.event_id, step=1)
        auto_refresh = st.toggle("Atualização automática (5 min)", value=False)
        refresh = st.button("🔄 Atualizar agora", use_container_width=True)

    if not config.username or not config.password:
        st.stop()

    if refresh:
        load_dashboard_data.clear()

    try:
        with st.spinner("Carregando dados do retaguarda Zig..."):
            data = load_dashboard_data(
                config.username,
                config.password,
                int(event_id),
                config.partner_code,
            )
    except Exception as exc:
        st.error(f"Erro ao carregar dados: {exc}")
        st.stop()

    metrics = data["metrics"]

    st.markdown('<div class="header-title">📊 Dashboard de Vendas Zig</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="header-subtitle">{data["event_name"]} · '
        f'Período: {data["period_start"]} até {data["period_end"]} · '
        f'Atualizado: {data["updated_at"]}</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c5, c6, c7 = st.columns(3)

    with c1:
        metric_card("Receita Bruta", format_currency(metrics["receita_bruta"]))
    with c2:
        metric_card("Quantidade de Vendas", f'{metrics["quantidade_vendas"]:,}'.replace(",", "."))
    with c3:
        metric_card("Ticket Médio", format_currency(metrics["ticket_medio"]))
    with c4:
        metric_card(
            "Itens Vendidos",
            f'{metrics["quantidade_itens_vendidos"]:,}'.replace(",", "."),
        )
    with c5:
        metric_card(
            "Itens Cancelados",
            f'{metrics["quantidade_itens_cancelados"]:,}'.replace(",", "."),
        )
    with c6:
        metric_card("Reimpressões", str(metrics["reimpressoes"]))
    with c7:
        metric_card(
            "Dispositivos Vendendo",
            str(metrics["quantidade_dispositivos_vendendo"]),
        )

    st.divider()
    render_charts(data["transactions"])

    with st.expander("Ver transações recentes"):
        if data["transactions"]:
            df = pd.DataFrame(data["transactions"])
            display_cols = [
                col
                for col in [
                    "transacao_id",
                    "data_realizacao",
                    "operacao",
                    "nome_ponto",
                    "quantidade",
                    "valor",
                    "status",
                    "terminal",
                ]
                if col in df.columns
            ]
            st.dataframe(df[display_cols].head(100), use_container_width=True)
        else:
            st.info("Nenhuma transação encontrada no período.")

    if auto_refresh:
        import time

        time.sleep(300)
        st.rerun()


if __name__ == "__main__":
    main()
