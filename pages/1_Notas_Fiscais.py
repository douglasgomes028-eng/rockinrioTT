"""Página isolada de notas fiscais (DANFE) para atendimento."""
from __future__ import annotations

from datetime import date, datetime, time
import re

import pandas as pd
import streamlit as st

from zig_session import clear_zig_client_cache, get_config, get_zig_client


def _parse_event_date(value: str) -> date:
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return date.today()


def _period_bounds(value: date | tuple[date, ...] | list[date]) -> tuple[date, date]:
    if isinstance(value, date):
        return value, value
    if len(value) >= 2:
        return value[0], value[1]
    if len(value) == 1:
        return value[0], value[0]
    today = date.today()
    return today, today


def _format_hm(value: time) -> str:
    return value.strftime("%H:%M")


@st.cache_data(ttl=600, show_spinner=False)
def load_terminal_serials(
    username: str,
    password: str,
    event_id: int,
    partner_code: str,
    period_start: str,
    period_end: str,
) -> list[str]:
    client = get_zig_client(username, password, event_id, partner_code)
    client.config.event_id = event_id
    if not hasattr(client, "list_invoice_terminals"):
        clear_zig_client_cache()
        client = get_zig_client(username, password, event_id, partner_code)
        client.config.event_id = event_id
    return client.list_invoice_terminals(period_start, period_end)


def _terminal_label(serial: str) -> str:
    return f"terminal: {serial}"


st.set_page_config(
    page_title="Notas Fiscais · Grupo Impettus",
    page_icon="🧾",
    layout="wide",
)

config = get_config()
if not config.username or not config.password:
    st.warning("Configure as credenciais Zig nos secrets do Streamlit.")
    st.stop()

with st.sidebar:
    if st.button("📊 Voltar ao dashboard", use_container_width=True):
        st.switch_page("app.py")
    st.caption("TEMA")
    _selected = st.radio(
        "Tema notas",
        options=["Claro", "Escuro"],
        index=0 if st.session_state.get("ui_theme", "escuro") == "claro" else 1,
        horizontal=True,
        label_visibility="collapsed",
        key="ui_theme_radio_notas",
    )
    st.session_state.ui_theme = "claro" if _selected == "Claro" else "escuro"
    st.subheader("Filtros")
    event_id = int(st.number_input("ID do Evento", value=config.event_id, step=1))
    st.markdown(
        """
        **Campos do comprovante para busca**
        - **Data + horário** da venda
        - **Serial do terminal** (seleção na lista)
        - **Código de controle**
        - **ID da transação Zig**
        - **ID da nota** ou **número da NF**
        """
    )

_theme = st.session_state.get("ui_theme", "escuro")
if _theme == "claro":
    _vars = """
        --rir-bg: #f3f4f6; --rir-card: #ffffff; --rir-sidebar: #ffffff;
        --rir-border: #e5e7eb; --rir-top: #1a1a1a;
    """
else:
    _vars = """
        --rir-bg: #0b0f14; --rir-card: #151b24; --rir-sidebar: #10151d;
        --rir-border: rgba(148,163,184,0.14); --rir-top: #0a0c10;
    """

st.markdown(
    f"""
    <style>
        :root {{ {_vars} }}
        .stApp {{ background: var(--rir-bg); }}
        [data-testid="stHeader"] {{ background: var(--rir-top); }}
        section[data-testid="stSidebar"] {{
            background: var(--rir-sidebar);
            border-right: 1px solid var(--rir-border);
        }}
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background: var(--rir-card);
            border: 1px solid var(--rir-border) !important;
            border-radius: 14px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.18), 0 10px 28px rgba(0,0,0,0.12);
        }}
        .block-container {{ padding-top: 1.35rem; }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("### Notas fiscais (DANFE)")
st.caption(
    "Backup Zig · busque a venda pelos dados do comprovante e baixe a DANFE."
)

try:
    period_client = get_zig_client(
        config.username,
        config.password,
        event_id,
        config.partner_code,
    )
    # Sessão antiga em cache pode não ter o filtro de terminal; força reload.
    if "terminal" not in period_client.search_invoices.__code__.co_varnames:
        clear_zig_client_cache()
        period_client = get_zig_client(
            config.username,
            config.password,
            event_id,
            config.partner_code,
        )
    period_client.config.event_id = event_id
    event_start_str, event_end_str = period_client.get_event_period()
except Exception as exc:
    st.error(f"Não foi possível carregar o período do evento: {exc}")
    st.stop()

event_start = _parse_event_date(event_start_str)
event_end = _parse_event_date(event_end_str)
today = min(max(date.today(), event_start), event_end)

st.subheader("Filtros do comprovante")
periodo = st.date_input(
    "Data da transação",
    value=(today, today),
    min_value=event_start,
    max_value=event_end,
    format="DD/MM/YYYY",
    help="Use a data impressa no comprovante.",
)
start_day, end_day = _period_bounds(periodo)
if start_day > end_day:
    start_day, end_day = end_day, start_day

hora_col_a, hora_col_b = st.columns(2)
with hora_col_a:
    hora_inicio = st.time_input(
        "Horário inicial",
        value=time(0, 0),
        step=60,
        help="Horário da venda no comprovante (início do intervalo).",
    )
with hora_col_b:
    hora_fim = st.time_input(
        "Horário final",
        value=time(23, 59),
        step=60,
        help="Se souber o horário exato, estreite o intervalo (ex.: 12:55 a 13:00).",
    )

if (start_day, hora_inicio) > (end_day, hora_fim):
    st.warning("O horário inicial está depois do horário final. Ajuste o intervalo.")

period_start = f"{start_day.strftime('%d/%m/%Y')} {_format_hm(hora_inicio)}"
period_end = f"{end_day.strftime('%d/%m/%Y')} {_format_hm(hora_fim)}"
st.caption(f"Consultando de {period_start} até {period_end}.")

try:
    with st.spinner("Carregando todos os terminais do evento..."):
        terminal_options = load_terminal_serials(
            config.username,
            config.password,
            event_id,
            config.partner_code,
            event_start_str,
            event_end_str,
        )
except Exception as exc:
    st.warning(f"Não foi possível montar a lista de terminais: {exc}")
    terminal_options = []

typed_terminal = st.text_input(
    "Serial do terminal",
    placeholder="Digite para filtrar ou cole o serial do comprovante",
    help="Conforme você digita, a lista abaixo mostra os terminais correspondentes.",
    key="terminal_typed",
)
typed_clean = typed_terminal.strip()
typed_digits = re.sub(r"\D", "", typed_clean)
typed_lower = typed_clean.lower()

if terminal_options:
    if typed_clean:
        filtered_terminals = [
            serial
            for serial in terminal_options
            if typed_lower in serial.lower()
            or typed_lower in _terminal_label(serial).lower()
            or (typed_digits and typed_digits in re.sub(r"\D", "", serial))
        ]
    else:
        filtered_terminals = terminal_options

    if filtered_terminals:
        selected_terminal = st.selectbox(
            "Terminais encontrados",
            options=filtered_terminals,
            format_func=_terminal_label,
            index=0 if len(filtered_terminals) == 1 else None,
            placeholder="Selecione o terminal na lista",
            help="Lista filtrada conforme o texto digitado acima.",
            key="terminal_select",
        )
        st.caption(
            f"{len(filtered_terminals)} de {len(terminal_options)} terminais "
            f"{'filtrados' if typed_clean else 'disponíveis'}."
        )
        terminal = selected_terminal or typed_digits or typed_clean
    else:
        st.caption(
            "Nenhum terminal da lista corresponde ao texto. "
            "A busca usará exatamente o que foi digitado."
        )
        terminal = typed_digits or typed_clean
else:
    st.warning(
        "Nenhum terminal encontrado no evento. Você ainda pode digitar o serial "
        "manualmente ou listar notas só com data/hora."
    )
    terminal = typed_digits or typed_clean

query = st.text_input(
    "Busca adicional (opcional)",
    placeholder="Controle, transação Zig, ID ou número da NF",
    help="Use se quiser refinar ainda mais. O terminal tem campo próprio acima.",
)

col_a, col_b = st.columns(2)
with col_a:
    buscar = st.button("🔎 Buscar nota", type="primary", use_container_width=True)
with col_b:
    listar = st.button("📋 Listar notas do período", use_container_width=True)

if "invoice_rows" not in st.session_state:
    st.session_state.invoice_rows = []
    st.session_state.invoice_total = 0

if buscar or listar:
    try:
        client = get_zig_client(
            config.username,
            config.password,
            event_id,
            config.partner_code,
        )
        client.config.event_id = event_id
        with st.spinner("Consultando gestão de notas da Zig..."):
            rows, total = client.search_invoices(
                query=query.strip() if buscar else "",
                period_start=period_start,
                period_end=period_end,
                terminal=terminal,
            )
        st.session_state.invoice_rows = rows
        st.session_state.invoice_total = total
        label_bits = [f"{period_start} — {period_end}"]
        if terminal:
            label_bits.append(f"terminal {terminal}")
        st.session_state.invoice_period = " · ".join(label_bits)
        st.session_state.pop("danfe_zip_bytes", None)
        st.session_state.pop("danfe_zip_name", None)
        st.session_state.pop("danfe_zip_stats", None)
    except Exception as exc:
        st.error(f"Não foi possível carregar as notas: {exc}")
        st.stop()

rows = st.session_state.invoice_rows
total = st.session_state.invoice_total

if not rows:
    st.info(
        "Informe data/hora (e, se possível, o serial do terminal) e clique em Buscar, "
        "ou liste as notas do período selecionado."
    )
    st.stop()

periodo_label = st.session_state.get("invoice_period", f"{period_start} — {period_end}")
st.success(
    f"{len(rows)} nota(s) exibida(s) de {total} encontrada(s) no retaguarda "
    f"({periodo_label})."
)

danfe_ready = [invoice for invoice in rows if invoice.get("danfe_url")]
bulk_cols = st.columns([2, 2, 4])
with bulk_cols[0]:
    gerar_zip = st.button(
        f"📦 Gerar ZIP com {len(danfe_ready)} DANFE(s)",
        use_container_width=True,
        disabled=not danfe_ready,
        help="Baixa todas as DANFEs das notas listadas com o filtro atual e gera um arquivo ZIP.",
    )
with bulk_cols[1]:
    if st.session_state.get("danfe_zip_bytes"):
        st.download_button(
            "⬇️ Baixar ZIP",
            data=st.session_state.danfe_zip_bytes,
            file_name=st.session_state.get("danfe_zip_name", "DANFEs.zip"),
            mime="application/zip",
            use_container_width=True,
        )

if gerar_zip:
    if len(danfe_ready) > 400:
        st.warning(
            "Há muitas notas neste filtro. O ZIP pode demorar e o Streamlit Cloud "
            "pode estourar o tempo limite. Prefira estreitar data/hora ou terminal."
        )
    try:
        client = get_zig_client(
            config.username,
            config.password,
            event_id,
            config.partner_code,
        )
        client.config.event_id = event_id
        progress = st.progress(0.0, text="Preparando download das DANFEs...")

        def _on_progress(current: int, total_count: int) -> None:
            ratio = current / max(total_count, 1)
            progress.progress(ratio, text=f"Baixando DANFE {current} de {total_count}...")

        with st.spinner("Montando ZIP com as DANFEs do período filtrado..."):
            zip_bytes, zip_name, stats = client.download_danfes_zip(
                danfe_ready,
                progress_callback=_on_progress,
            )
        progress.empty()
        st.session_state.danfe_zip_bytes = zip_bytes
        st.session_state.danfe_zip_name = zip_name
        st.session_state.danfe_zip_stats = stats
        st.rerun()
    except Exception as exc:
        st.error(f"Não foi possível gerar o ZIP das DANFEs: {exc}")

zip_stats = st.session_state.get("danfe_zip_stats")
if zip_stats and st.session_state.get("danfe_zip_bytes"):
    st.info(
        f"ZIP pronto: {zip_stats['downloaded']} DANFE(s) incluída(s). "
        f"Ignoradas: {zip_stats['skipped']} · Falhas: {zip_stats['failed']}."
    )

for invoice in rows:
    nota_id = invoice.get("nota_id")
    with st.container(border=True):
        top = st.columns([2, 2, 2, 2, 1.3, 1.4])
        top[0].markdown(f"**Transação**  \n`{invoice['transacao_id']}`")
        top[1].markdown(f"**Controle**  \n`{invoice['controle']}`")
        top[2].markdown(f"**Terminal**  \n`{invoice['terminal']}`")
        top[3].markdown(f"**Ponto**  \n{invoice['nome_ponto']}")
        top[4].markdown(f"**NF**  \n{invoice['serie']}/{invoice['numero']}")
        valor = float(invoice["valor"] or 0)
        valor_fmt = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        top[5].markdown(f"**Valor**  \n{valor_fmt}")

        meta = st.columns([2, 2, 2, 2])
        meta[0].caption(f"ID nota: {nota_id}")
        meta[1].caption(f"Data: {invoice['data_transacao']}")
        meta[2].caption(f"Status: {invoice['status']}")
        meta[3].caption(f"Operação: {invoice['operacao']}")

        actions = st.columns([1, 1, 4])
        with actions[0]:
            if invoice.get("danfe_url"):
                st.link_button("⬇️ DANFE", invoice["danfe_url"], use_container_width=True)
            else:
                st.button("DANFE indisponível", disabled=True, key=f"danfe_off_{nota_id}")
        with actions[1]:
            if invoice.get("xml_url"):
                st.link_button("⬇️ XML", invoice["xml_url"], use_container_width=True)

st.divider()
df = pd.DataFrame(rows)
st.dataframe(
    df[
        [
            "nota_id",
            "transacao_id",
            "controle",
            "terminal",
            "nome_ponto",
            "data_transacao",
            "numero",
            "valor",
            "status",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)
