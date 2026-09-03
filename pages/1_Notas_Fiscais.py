"""Página isolada de notas fiscais (DANFE) para atendimento."""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

from zig_session import get_config, get_zig_client


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
        - **Serial do terminal** (15 dígitos)
        - **Código de controle**
        - **ID da transação Zig**
        - **ID da nota** ou **número da NF**
        - **Data da venda** no período abaixo
        """
    )

try:
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

query = st.text_input(
    "Busca rápida pelo comprovante",
    placeholder="Ex.: 869122080155908  ·  Controle 34  ·  Transação 220046404",
)
periodo = st.date_input(
    "Período da transação",
    value=(today, today),
    min_value=event_start,
    max_value=event_end,
    format="DD/MM/YYYY",
    help="Filtra as notas pela data da venda, no mesmo formato da gestão de notas da Zig.",
)
start_day, end_day = _period_bounds(periodo)
if start_day > end_day:
    start_day, end_day = end_day, start_day

period_start = f"{start_day.strftime('%d/%m/%Y')} 00:00"
period_end = f"{end_day.strftime('%d/%m/%Y')} 23:59"
st.caption(f"Consultando de {period_start} até {period_end}.")

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
            )
        st.session_state.invoice_rows = rows
        st.session_state.invoice_total = total
        st.session_state.invoice_period = f"{period_start} — {period_end}"
    except Exception as exc:
        st.error(f"Não foi possível carregar as notas: {exc}")
        st.stop()

rows = st.session_state.invoice_rows
total = st.session_state.invoice_total

if not rows:
    st.info(
        "Informe um ID do comprovante e clique em Buscar, ou liste as notas do período selecionado."
    )
    st.stop()

periodo_label = st.session_state.get("invoice_period", f"{period_start} — {period_end}")
st.success(
    f"{len(rows)} nota(s) exibida(s) de {total} encontrada(s) no retaguarda "
    f"({periodo_label})."
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
