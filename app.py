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
    page_title="Dashboard Vendas Grupo Impettus - RIR 2026",
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
    .ranking-card {
        background: linear-gradient(135deg, #111827 0%, #1e293b 100%);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.6rem;
        display: flex;
        align-items: center;
        gap: 1rem;
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .ranking-card:hover {
        transform: translateX(4px);
        border-color: rgba(59,130,246,0.45);
    }
    .ranking-pos {
        width: 42px;
        height: 42px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        font-size: 1rem;
        flex-shrink: 0;
        color: #0f172a;
    }
    .ranking-pos.gold { background: linear-gradient(135deg, #fbbf24, #f59e0b); }
    .ranking-pos.silver { background: linear-gradient(135deg, #e2e8f0, #94a3b8); }
    .ranking-pos.bronze { background: linear-gradient(135deg, #fdba74, #ea580c); }
    .ranking-pos.default { background: #334155; color: #f8fafc; }
    .ranking-info { flex: 1; min-width: 0; }
    .ranking-name {
        color: #f8fafc;
        font-weight: 700;
        font-size: 1.05rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .ranking-meta { color: #94a3b8; font-size: 0.82rem; margin-top: 0.15rem; }
    .ranking-bar-wrap {
        margin-top: 0.45rem;
        background: rgba(148,163,184,0.18);
        border-radius: 999px;
        height: 10px;
        overflow: hidden;
    }
    .ranking-bar {
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #60a5fa, #2563eb);
    }
    .ranking-value {
        color: #f8fafc;
        font-weight: 800;
        font-size: 1.15rem;
        white-space: nowrap;
        text-align: right;
        min-width: 130px;
    }
    .ranking-share {
        color: #94a3b8;
        font-size: 0.8rem;
        text-align: right;
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


@st.cache_data(ttl=60, show_spinner=False)
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


def build_brand_ranking(transactions: list[dict], top_n: int = 10) -> pd.DataFrame:
    if not transactions:
        return pd.DataFrame()

    df = pd.DataFrame(transactions)
    if "nome_ponto" not in df.columns or "valor" not in df.columns:
        return pd.DataFrame()

    ranking = (
        df.groupby("nome_ponto", as_index=False)
        .agg(
            valor=("valor", "sum"),
            vendas=("valor", "count"),
            itens=("quantidade", "sum"),
        )
        .sort_values("valor", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    if ranking.empty:
        return ranking

    total = ranking["valor"].sum()
    ranking["posicao"] = ranking.index + 1
    ranking["share"] = ranking["valor"].apply(lambda v: (v / total * 100) if total else 0)
    ranking["valor_formatado"] = ranking["valor"].map(format_currency)
    ranking["label"] = ranking.apply(
        lambda row: f"#{int(row['posicao'])} {row['nome_ponto']}",
        axis=1,
    )
    return ranking


def render_brand_ranking(transactions: list[dict]) -> None:
    ranking = build_brand_ranking(transactions, top_n=10)
    if ranking.empty:
        st.info("Sem dados para o ranking de faturamento por marca.")
        return

    st.subheader("🏆 Ranking em tempo real · Faturamento por marca")
    st.caption("Atualiza automaticamente conforme as vendas entram no retaguarda Zig.")

    chart_tab, cards_tab = st.tabs(["Gráfico interativo", "Lista de ranking"])

    with chart_tab:
        chart_df = ranking.sort_values("valor", ascending=True)
        fig = px.bar(
            chart_df,
            x="valor",
            y="label",
            orientation="h",
            text="valor_formatado",
            color="valor",
            color_continuous_scale="Blues",
            custom_data=["posicao", "vendas", "itens", "share"],
            labels={"valor": "Faturamento (R$)", "label": "Marca / Ponto"},
        )
        fig.update_traces(
            textposition="outside",
            textfont=dict(size=13, color="#f8fafc"),
            cliponaxis=False,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Posição: #%{customdata[0]}<br>"
                "Faturamento: %{text}<br>"
                "Vendas: %{customdata[1]}<br>"
                "Itens: %{customdata[2]}<br>"
                "Participação: %{customdata[3]:.1f}%<extra></extra>"
            ),
        )
        fig.update_layout(
            height=max(420, 55 * len(chart_df) + 120),
            showlegend=False,
            margin=dict(l=20, r=120, t=30, b=40),
            coloraxis_showscale=False,
            xaxis=dict(tickprefix="R$ ", rangemode="tozero"),
            yaxis=dict(title=""),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0"),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with cards_tab:
        max_valor = float(ranking["valor"].max() or 1)
        for _, row in ranking.iterrows():
            pos = int(row["posicao"])
            medal = "gold" if pos == 1 else "silver" if pos == 2 else "bronze" if pos == 3 else "default"
            width = max(4.0, float(row["valor"]) / max_valor * 100)
            st.markdown(
                f"""
                <div class="ranking-card">
                    <div class="ranking-pos {medal}">{pos}</div>
                    <div class="ranking-info">
                        <div class="ranking-name">{row["nome_ponto"]}</div>
                        <div class="ranking-meta">{int(row["vendas"])} vendas · {int(row["itens"])} itens</div>
                        <div class="ranking-bar-wrap">
                            <div class="ranking-bar" style="width:{width:.2f}%"></div>
                        </div>
                    </div>
                    <div>
                        <div class="ranking-value">{row["valor_formatado"]}</div>
                        <div class="ranking-share">{row["share"]:.1f}% do total</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_charts(transactions: list[dict]) -> None:
    if not transactions:
        st.info("Sem transações para exibir nos gráficos.")
        return

    render_brand_ranking(transactions)

    df = pd.DataFrame(transactions)
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
        refresh_seconds = st.selectbox(
            "Atualização automática",
            options=[0, 30, 60, 120],
            format_func=lambda s: "Desligada" if s == 0 else f"A cada {s}s",
            index=2,
        )
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

    st.markdown('<div class="header-title">📊 Dashboard Vendas Grupo Impettus - RIR 2026</div>', unsafe_allow_html=True)
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

    if refresh_seconds > 0:
        import time

        time.sleep(refresh_seconds)
        load_dashboard_data.clear()
        st.rerun()


if __name__ == "__main__":
    main()
