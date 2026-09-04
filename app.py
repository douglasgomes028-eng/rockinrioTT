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

THEME_CSS = {
    "escuro": """
<style>
    :root {
        --rir-bg: #0b0f14;
        --rir-card: #151b24;
        --rir-sidebar: #10151d;
        --rir-ink: #f8fafc;
        --rir-muted: #8b949e;
        --rir-border: rgba(148,163,184,0.14);
        --rir-blue: #0095ff;
        --rir-blue-soft: rgba(0,149,255,0.16);
        --rir-top: #0a0c10;
        --rir-hint: #6b7280;
        --rir-bar-track: rgba(148,163,184,0.16);
        --rir-shadow: 0 1px 2px rgba(0,0,0,0.25), 0 10px 28px rgba(0,0,0,0.22);
        --rir-rank-default: #7dd3fc;
        --rir-hover: rgba(0,149,255,0.45);
    }
</style>
""",
    "claro": """
<style>
    :root {
        --rir-bg: #f3f4f6;
        --rir-card: #ffffff;
        --rir-sidebar: #ffffff;
        --rir-ink: #111827;
        --rir-muted: #6b7280;
        --rir-border: #e5e7eb;
        --rir-blue: #0095ff;
        --rir-blue-soft: #dbe8ff;
        --rir-top: #1a1a1a;
        --rir-hint: #9ca3af;
        --rir-bar-track: #eef2ff;
        --rir-shadow: 0 1px 2px rgba(16,24,40,0.04), 0 8px 24px rgba(16,24,40,0.06);
        --rir-rank-default: #1d4ed8;
        --rir-hover: #bfdbfe;
    }
</style>
""",
}

BASE_CSS = """
<style>
    .stApp { background: var(--rir-bg); color: var(--rir-ink); }
    [data-testid="stHeader"] { background: var(--rir-top); }
    section[data-testid="stSidebar"] {
        background: var(--rir-sidebar);
        border-right: 1px solid var(--rir-border);
    }
    section[data-testid="stSidebar"] .stButton > button {
        border-radius: 10px;
        font-weight: 600;
    }
    .block-container { padding-top: 1.35rem; padding-bottom: 2rem; }

    .theme-toggle {
        display: flex;
        gap: 0.4rem;
        margin: 0.35rem 0 0.9rem;
    }

    .topbar-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        background: color-mix(in srgb, var(--rir-card) 88%, #000 12%);
        color: var(--rir-ink);
        border: 1px solid var(--rir-border);
        border-radius: 999px;
        padding: 0.35rem 0.8rem;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        margin-bottom: 0.9rem;
    }
    .topbar-badge span { color: #fbbf24; }

    .header-title {
        font-size: 1.85rem;
        font-weight: 760;
        color: var(--rir-ink);
        margin-bottom: 0.15rem;
        letter-spacing: -0.02em;
    }
    .header-subtitle {
        color: var(--rir-muted);
        margin-bottom: 1.35rem;
        font-size: 0.92rem;
    }

    .metric-card {
        background: var(--rir-card);
        border-radius: 14px;
        padding: 1.05rem 1.15rem 1.1rem;
        border: 1px solid var(--rir-border);
        box-shadow: var(--rir-shadow);
        min-height: 112px;
    }
    .metric-label {
        color: var(--rir-muted);
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-bottom: 0.45rem;
    }
    .metric-value {
        color: var(--rir-ink);
        font-size: 1.7rem;
        font-weight: 760;
        line-height: 1.15;
        letter-spacing: -0.02em;
    }
    .metric-hint {
        color: var(--rir-hint);
        font-size: 0.78rem;
        margin-top: 0.45rem;
    }

    .panel-title {
        color: var(--rir-ink);
        font-size: 1.05rem;
        font-weight: 720;
        margin-bottom: 0.15rem;
    }
    .panel-caption {
        color: var(--rir-muted);
        font-size: 0.84rem;
        margin-bottom: 0.6rem;
    }

    .ranking-card {
        background: var(--rir-card);
        border: 1px solid var(--rir-border);
        border-radius: 14px;
        box-shadow: var(--rir-shadow);
        padding: 0.95rem 1.05rem;
        margin-bottom: 0.65rem;
        display: flex;
        align-items: center;
        gap: 1rem;
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .ranking-card:hover {
        transform: translateX(3px);
        border-color: var(--rir-hover);
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
    .ranking-pos.silver { background: linear-gradient(135deg, #e5e7eb, #9ca3af); }
    .ranking-pos.bronze { background: linear-gradient(135deg, #fdba74, #ea580c); }
    .ranking-pos.default { background: var(--rir-blue-soft); color: var(--rir-rank-default); }
    .ranking-info { flex: 1; min-width: 0; }
    .ranking-name {
        color: var(--rir-ink);
        font-weight: 720;
        font-size: 1.02rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .ranking-meta { color: var(--rir-muted); font-size: 0.82rem; margin-top: 0.15rem; }
    .ranking-bar-wrap {
        margin-top: 0.45rem;
        background: var(--rir-bar-track);
        border-radius: 999px;
        height: 8px;
        overflow: hidden;
    }
    .ranking-bar {
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #38bdf8, #0095ff);
    }
    .ranking-value {
        color: var(--rir-ink);
        font-weight: 780;
        font-size: 1.08rem;
        white-space: nowrap;
        text-align: right;
        min-width: 120px;
    }
    .ranking-share { color: var(--rir-muted); font-size: 0.78rem; text-align: right; }

    div[data-testid="stExpander"] {
        background: var(--rir-card);
        border: 1px solid var(--rir-border);
        border-radius: 14px;
        box-shadow: var(--rir-shadow);
    }
</style>
"""


def get_ui_theme() -> str:
    theme = st.session_state.get("ui_theme", "escuro")
    return theme if theme in ("claro", "escuro") else "escuro"


def apply_theme(theme: str | None = None) -> str:
    current = theme or get_ui_theme()
    st.session_state.ui_theme = current
    st.markdown(THEME_CSS[current], unsafe_allow_html=True)
    st.markdown(BASE_CSS, unsafe_allow_html=True)
    return current


def render_theme_toggle() -> str:
    current = get_ui_theme()
    st.caption("TEMA")
    selected = st.radio(
        "Tema",
        options=["Claro", "Escuro"],
        index=0 if current == "claro" else 1,
        horizontal=True,
        label_visibility="collapsed",
        key="ui_theme_radio",
    )
    theme = "claro" if selected == "Claro" else "escuro"
    st.session_state.ui_theme = theme
    return theme


def format_currency(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def metric_card(label: str, value: str, hint: str = "backup Zig · ao vivo") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-hint">{hint}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_chart_layout(theme: str | None = None) -> dict:
    current = theme or get_ui_theme()
    font_color = "#374151" if current == "claro" else "#cbd5e1"
    return {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": dict(color=font_color, family="sans-serif", size=12),
    }


def get_chart_palette(theme: str | None = None) -> dict:
    current = theme or get_ui_theme()
    if current == "claro":
        return {
            "bar_brand": ["#dbe8ff", "#0095ff"],
            "bar_products": ["#cffafe", "#0d9488"],
            "text": "#1f2937",
            "grid": "#e5e7eb",
        }
    return {
        "bar_brand": ["#0b3a66", "#0095ff"],
        "bar_products": ["#134e4a", "#14b8a6"],
        "text": "#e2e8f0",
        "grid": "rgba(148,163,184,0.18)",
    }


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

    st.markdown('<div class="panel-title">🏆 Ranking em tempo real · Faturamento por marca</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="panel-caption">Atualiza automaticamente conforme as vendas entram no retaguarda Zig.</div>',
        unsafe_allow_html=True,
    )

    chart_tab, cards_tab = st.tabs(["Gráfico interativo", "Lista de ranking"])

    with chart_tab:
        chart_df = ranking.sort_values("valor", ascending=True)
        palette = get_chart_palette()
        fig = px.bar(
            chart_df,
            x="valor",
            y="label",
            orientation="h",
            text="valor_formatado",
            color="valor",
            color_continuous_scale=palette["bar_brand"],
            custom_data=["posicao", "vendas", "itens", "share"],
            labels={"valor": "Faturamento (R$)", "label": "Marca / Ponto"},
        )
        fig.update_traces(
            textposition="outside",
            textfont=dict(size=13, color=palette["text"]),
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
            xaxis=dict(tickprefix="R$ ", rangemode="tozero", gridcolor=palette["grid"]),
            yaxis=dict(title=""),
            **get_chart_layout(),
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

    st.markdown('<div class="panel-title">🍔 Top 5 produtos mais vendidos por ponto</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="panel-caption">Ranking em tempo real com base na quantidade vendida em cada PDV.</div>',
        unsafe_allow_html=True,
    )

    pontos = list(products_by_point.keys())
    cols = st.columns(2)

    for idx, ponto in enumerate(pontos):
        top = products_by_point[ponto]
        chart_df = top.sort_values("quantidade", ascending=True)

        with cols[idx % 2]:
            st.markdown(f"**{ponto}**")
            palette = get_chart_palette()
            fig = px.bar(
                chart_df,
                x="quantidade",
                y="label",
                orientation="h",
                text="quantidade",
                color="quantidade",
                color_continuous_scale=palette["bar_products"],
                custom_data=["produto", "valor_formatado", "vendas", "categoria"],
                labels={"quantidade": "Quantidade", "label": "Produto"},
            )
            fig.update_traces(
                textposition="outside",
                textfont=dict(size=12, color=palette["text"]),
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
                xaxis=dict(rangemode="tozero", title="Quantidade", gridcolor=palette["grid"]),
                yaxis=dict(title=""),
                **get_chart_layout(),
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
            color_discrete_sequence=["#0095ff", "#14b8a6", "#f59e0b", "#ef4444", "#8b5cf6", "#64748b"],
        )
        fig.update_layout(height=380, **get_chart_layout())
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={"displayModeBar": False},
            key="operacao_pie_chart",
        )


def render_dashboard_content(data: dict, sync_status: str = "") -> None:
    metrics = data["metrics"]

    st.markdown(
        '<div class="topbar-badge"><span>⚡</span> Análise de Vendas · backup Zig</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="header-title">RIR 2026 — Vendas ao vivo</div>',
        unsafe_allow_html=True,
    )
    subtitle = (
        f'{data["event_name"]} · '
        f'Período: {data["period_start"]} até {data["period_end"]} · '
        f'atualizado {data["updated_at"]}'
    )
    if sync_status:
        subtitle += f" · {sync_status}"
    st.markdown(f'<div class="header-subtitle">{subtitle}</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c5, c6, c7 = st.columns(3)

    with c1:
        metric_card("Faturamento", format_currency(metrics["receita_bruta"]))
    with c2:
        metric_card("Transações", f'{metrics["quantidade_vendas"]:,}'.replace(",", "."))
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

    st.write("")
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
    config = get_config()

    with st.sidebar:
        st.markdown("### Controles")
        st.caption("Dashboard backup · mesma fonte Zig do painel principal.")
        theme = render_theme_toggle()
        apply_theme(theme)

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
        refresh = st.button("Atualizar agora", type="primary", use_container_width=True)
        st.divider()
        if st.button("Notas fiscais (DANFE)", use_container_width=True):
            st.switch_page("pages/1_Notas_Fiscais.py")
        st.caption("status · backup Zig")

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
