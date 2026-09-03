"""Página isolada de notas fiscais (DANFE) para atendimento."""
from __future__ import annotations

from datetime import date, datetime, time

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

st.title("🧾 Notas fiscais (DANFE)")
st.caption(
    "Página para relacionamento: busque a venda pelos dados do comprovante e baixe a DANFE."
)

config = get_config()
if not config.username or not config.password:
    st.warning("Configure as credenciais Zig nos secrets do Streamlit.")
    st.stop()

with st.sidebar:
    if st.button("📊 Voltar ao dashboard", use_container_width=True):
        st.switch_page("app.py")
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

if terminal_options:
    selected_terminal = st.selectbox(
        "Serial do terminal",
        options=terminal_options,
        format_func=_terminal_label,
        index=None,
        placeholder="Selecione o terminal",
        help="Todos os terminais com nota fiscal neste evento. Escolha o serial do comprovante.",
    )
    st.caption(f"{len(terminal_options)} terminais disponíveis no evento.")
    terminal = selected_terminal or ""
else:
    st.warning(
        "Nenhum terminal encontrado no evento. Você ainda pode listar notas só com data/hora "
        "ou informar a busca adicional."
    )
    terminal = ""

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
