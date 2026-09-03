"""Dashboard de vendas Zig/NetPDV."""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from metrics import compute_metrics
from zig_session import get_config, get_zig_client

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
    client = get_zig_client(username, password, event_id, partner_code)
    # Garante o evento atual caso o ID mude na sidebar
    client.config.event_id = event_id

    try:
        period_start, period_end = client.get_event_period()
        event_name = client.get_event_name()
        transactions = client.fetch_transactions(period_start, period_end)
        pending_prints = client.fetch_pending_prints()
        indicators = client.fetch_dashboard_indicators(period_start, period_end)
    except Exception:
        # Sessão pode ter expirado — reloga uma vez e tenta de novo
        get_zig_client.clear()
        client = get_zig_client(username, password, event_id, partner_code)
        client.config.event_id = event_id
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
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={"displayModeBar": False},
            key="brand_ranking_chart",
        )

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


def build_top_products_by_point(
    transactions: list[dict],
    top_n: int = 5,
) -> dict[str, pd.DataFrame]:
    if not transactions:
        return {}

    df = pd.DataFrame(transactions)
    required = {"nome_ponto", "produto", "quantidade", "valor"}
    if not required.issubset(df.columns):
        return {}

    df = df.copy()
    df["produto"] = df["produto"].fillna("").astype(str).str.strip()
    df["nome_ponto"] = df["nome_ponto"].fillna("").astype(str).str.strip()
    df = df[(df["produto"] != "") & (df["nome_ponto"] != "")]

    status = df.get("status", pd.Series([""] * len(df))).astype(str).str.lower()
    operacao = df.get("operacao", pd.Series([""] * len(df))).astype(str).str.lower()
    cancel_mask = status.str.contains("cancel|estorn|devol", regex=True) | operacao.str.contains(
        "cancel|estorn|devol",
        regex=True,
    )
    df = df[~cancel_mask]
    if df.empty:
        return {}

    result: dict[str, pd.DataFrame] = {}
    pontos = (
        df.groupby("nome_ponto", as_index=False)["valor"]
        .sum()
        .sort_values("valor", ascending=False)["nome_ponto"]
        .tolist()
    )

    for ponto in pontos:
        ponto_df = df[df["nome_ponto"] == ponto]
        top = (
            ponto_df.groupby("produto", as_index=False)
            .agg(
                quantidade=("quantidade", "sum"),
                valor=("valor", "sum"),
                vendas=("produto", "count"),
                categoria=("categoria", "first"),
            )
            .sort_values(["quantidade", "valor"], ascending=False)
            .head(top_n)
            .reset_index(drop=True)
        )
        if top.empty:
            continue
        top["posicao"] = top.index + 1
        top["valor_formatado"] = top["valor"].map(format_currency)
        top["label"] = top.apply(
            lambda row: f"#{int(row['posicao'])} {row['produto']}",
            axis=1,
        )
        result[ponto] = top

    return result


def render_top_products_by_point(transactions: list[dict]) -> None:
    products_by_point = build_top_products_by_point(transactions, top_n=5)
    if not products_by_point:
        st.info("Sem dados de produtos por ponto de venda.")
        return

    st.subheader("🍔 Top 5 produtos mais vendidos por ponto")
    st.caption("Ranking em tempo real com base na quantidade vendida em cada PDV.")

    pontos = list(products_by_point.keys())
    cols = st.columns(2)

    for idx, ponto in enumerate(pontos):
        top = products_by_point[ponto]
        chart_df = top.sort_values("quantidade", ascending=True)

        with cols[idx % 2]:
            st.markdown(f"**{ponto}**")
            fig = px.bar(
                chart_df,
                x="quantidade",
                y="label",
                orientation="h",
                text="quantidade",
                color="quantidade",
                color_continuous_scale="Teal",
                custom_data=["produto", "valor_formatado", "vendas", "categoria"],
                labels={"quantidade": "Quantidade", "label": "Produto"},
            )
            fig.update_traces(
                textposition="outside",
                textfont=dict(size=12, color="#f8fafc"),
                cliponaxis=False,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Quantidade: %{x}<br>"
                    "Faturamento: %{customdata[1]}<br>"
                    "Vendas: %{customdata[2]}<br>"
                    "Categoria: %{customdata[3]}<extra></extra>"
                ),
            )
            fig.update_layout(
                height=max(280, 48 * len(chart_df) + 90),
                showlegend=False,
                margin=dict(l=10, r=60, t=10, b=30),
                coloraxis_showscale=False,
                xaxis=dict(rangemode="tozero", title="Quantidade"),
                yaxis=dict(title=""),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0", size=12),
            )
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"displayModeBar": False},
                key=f"top_products_chart_{idx}_{ponto}",
            )


def render_charts(transactions: list[dict]) -> None:
    if not transactions:
        st.info("Sem transações para exibir nos gráficos.")
        return

    render_brand_ranking(transactions)
    st.divider()
    render_top_products_by_point(transactions)

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
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={"displayModeBar": False},
            key="operacao_pie_chart",
        )


def render_dashboard_content(data: dict, sync_status: str = "") -> None:
    metrics = data["metrics"]

    st.markdown(
        '<div class="header-title">📊 Dashboard Vendas Grupo Impettus - RIR 2026</div>',
        unsafe_allow_html=True,
    )
    subtitle = (
        f'{data["event_name"]} · '
        f'Período: {data["period_start"]} até {data["period_end"]} · '
        f'Atualizado: {data["updated_at"]}'
    )
    if sync_status:
        subtitle += f" · {sync_status}"
    st.markdown(f'<div class="header-subtitle">{subtitle}</div>', unsafe_allow_html=True)

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
                    "produto",
                    "quantidade",
                    "valor",
                    "status",
                    "terminal",
                ]
                if col in df.columns
            ]
            st.dataframe(
                df[display_cols].head(100),
                use_container_width=True,
                key="recent_transactions_table",
            )
        else:
            st.info("Nenhuma transação encontrada no período.")


def fetch_dashboard_snapshot(
    username: str,
    password: str,
    event_id: int,
    partner_code: str,
    force: bool = False,
) -> dict:
    if force:
        load_dashboard_data.clear()
    return load_dashboard_data(username, password, event_id, partner_code)


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

        event_id = int(st.number_input("ID do Evento", value=config.event_id, step=1))
        refresh_seconds = st.selectbox(
            "Atualização automática",
            options=[0, 30, 60, 120],
            format_func=lambda s: "Desligada" if s == 0 else f"A cada {s}s",
            index=2,
            key="refresh_seconds",
        )
        refresh = st.button("🔄 Atualizar agora", use_container_width=True)
        st.caption("Para DANFE / notas fiscais, abra a página **Notas Fiscais** no menu.")

    if not config.username or not config.password:
        st.stop()

    # Carga inicial (ou manual): única vez que mostra o loading completo
    if "dashboard_data" not in st.session_state or refresh:
        try:
            with st.spinner("Carregando dados do retaguarda Zig..."):
                st.session_state.dashboard_data = fetch_dashboard_snapshot(
                    config.username,
                    config.password,
                    event_id,
                    config.partner_code,
                    force=True,
                )
            st.session_state.dashboard_error = None
            st.session_state.skip_next_fragment_fetch = True
        except Exception as exc:
            if "dashboard_data" not in st.session_state:
                st.error(f"Erro ao carregar dados: {exc}")
                st.stop()
            st.session_state.dashboard_error = str(exc)

    run_every = timedelta(seconds=refresh_seconds) if refresh_seconds > 0 else None

    @st.fragment(run_every=run_every)
    def live_dashboard() -> None:
        skip_fetch = st.session_state.pop("skip_next_fragment_fetch", False)

        # Evita renderizar os mesmos elementos 2x no mesmo ciclo (DuplicateElementId)
        if not skip_fetch and refresh_seconds > 0:
            render_dashboard_content(
                st.session_state.dashboard_data,
                sync_status="sincronizando…",
            )
            try:
                st.session_state.dashboard_data = fetch_dashboard_snapshot(
                    config.username,
                    config.password,
                    event_id,
                    config.partner_code,
                    force=True,
                )
                st.session_state.dashboard_error = None
            except Exception:
                st.session_state.dashboard_error = "sync_failed"

            st.session_state.skip_next_fragment_fetch = True
            st.rerun(scope="fragment")
            return

        sync_status = ""
        if st.session_state.get("dashboard_error") == "sync_failed":
            sync_status = "falha na sincronização · exibindo último snapshot"

        render_dashboard_content(
            st.session_state.dashboard_data,
            sync_status=sync_status,
        )

    live_dashboard()


if __name__ == "__main__":
    main()
