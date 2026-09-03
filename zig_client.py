"""Cliente para integração com o backoffice Zig/NetPDV."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://netpdv.com"
LOGIN_URL = f"{BASE_URL}/backoffice/Authentication/Login"


@dataclass
class ZigConfig:
    username: str
    password: str
    event_id: int
    partner_code: str = ""


class ZigClient:
    def __init__(self, config: ZigConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ZigDashboard/1.0"})

    def login(self) -> None:
        response = self.session.get(LOGIN_URL, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        token_input = soup.find("input", {"name": "__RequestVerificationToken"})
        if not token_input:
            raise RuntimeError("Token CSRF não encontrado na página de login.")

        payload = {
            "__RequestVerificationToken": token_input["value"],
            "vchLoginUsuario": self.config.username,
            "vchSenha": self.config.password,
        }

        login_response = self.session.post(
            LOGIN_URL,
            data=payload,
            timeout=30,
            allow_redirects=True,
        )
        login_response.raise_for_status()

        if "authentication/login" in login_response.url.lower():
            raise RuntimeError("Falha no login. Verifique usuário e senha.")

    def get_events(self) -> list[dict[str, Any]]:
        response = self.session.get(
            f"{BASE_URL}/backoffice/Relatorio/GetListaEventos",
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        import json

        events_raw = payload.get("All", "[]")
        return json.loads(events_raw) if isinstance(events_raw, str) else events_raw

    def get_event_period(self, event_id: int | None = None) -> tuple[str, str]:
        event_id = event_id or self.config.event_id
        response = self.session.post(
            f"{BASE_URL}/backoffice/Relatorio/GetIntervaloDataEvento",
            data={"eventoId": event_id},
            timeout=30,
        )
        response.raise_for_status()
        interval = response.json().get("intervaloData", {})
        start = interval.get("sdtDataInicioString", "01/01/2026 00:00")
        end = interval.get("sdtDataFimString", "31/12/2026 23:59")
        return start, end

    def _process_report(self, report: str, fields: list[str]) -> str:
        response = self.session.post(
            f"{BASE_URL}/backoffice/Relatorio/ProcessReport",
            data={
                "id": self.config.event_id,
                "report": report,
                "fields": fields,
                "isMobile": "false",
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.text

    def _default_fields(self, period_start: str, period_end: str) -> list[str]:
        period = f"{period_start} - {period_end}"
        return [
            f"field-periodo={period}",
            "field-tempo-integral=1",
        ]

    def fetch_transactions(
        self,
        period_start: str | None = None,
        period_end: str | None = None,
    ) -> list[dict[str, Any]]:
        if not period_start or not period_end:
            period_start, period_end = self.get_event_period()

        fields = self._default_fields(period_start, period_end)
        fields.extend(
            [
                "field-formatacao=1",
                "field-tipo-relatorio-transacao=1",
            ]
        )
        self._process_report("lista_transacao", fields)
        return self._fetch_transactions_paginated()

    def _fetch_transactions_paginated(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1

        while True:
            response = self.session.get(
                f"{BASE_URL}/backoffice/Relatorio/GetListaTransacoesPage",
                params={"page": page},
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()

            if payload.get("isError"):
                break

            batch = payload.get("arrData", [])
            if not batch:
                break

            for entry in batch:
                items = entry if isinstance(entry, list) else [entry]
                for item in items:
                    rows.append(self._normalize_transaction(item))

            if len(batch) < 100:
                break
            page += 1

        return rows

    def _normalize_transaction(self, item: dict[str, Any]) -> dict[str, Any]:
        valor = item.get("Valor")
        if valor is None:
            valor = item.get("ValorFormaPagamento", 0)

        return {
            "transacao_id": str(item.get("Transacao_Id", "")),
            "data_realizacao": item.get("_strDataHora", ""),
            "operacao": item.get("Operação") or item.get("Operacao", ""),
            "terminal": str(item.get("Terminal", "")),
            "codigo_ponto": item.get("vchCodigoPonto", ""),
            "nome_ponto": item.get("vchNomePonto", ""),
            "operador": item.get("Operador", ""),
            "forma_pagamento": item.get("FormaPagamento", ""),
            "produto": str(item.get("Produto") or "").strip(),
            "categoria": str(item.get("CategoriaProduto") or "").strip(),
            "quantidade": self._parse_int(item.get("Qtd", 0)),
            "valor": self._parse_money(valor),
            "gorjeta": self._parse_money(
                item.get("numValorGorjetaPosPago", item.get("numValorGorjeta", 0))
            ),
            "bonus": self._parse_money(item.get("Bonus", 0)),
            "taxa_ativacao": self._parse_money(
                item.get("TxAtivação", item.get("TxAtivacao", 0))
            ),
            "status": item.get("Status", ""),
        }

    def fetch_pending_prints(self) -> list[dict[str, Any]]:
        self._process_report("impressoes_pendentes", [])
        response = self.session.post(
            f"{BASE_URL}/backoffice/Relatorio/GetImpressoesPendentes",
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("arrData", [])

    def fetch_dashboard_indicators(
        self,
        period_start: str | None = None,
        period_end: str | None = None,
    ) -> dict[str, Any] | None:
        if not period_start or not period_end:
            period_start, period_end = self.get_event_period()

        fields = self._default_fields(period_start, period_end)
        fields.append("field-atualizacao=1")

        self._process_report("dashboard_cashless", fields)
        response = self.session.post(
            f"{BASE_URL}/backoffice/Relatorio/GetDashboardCashlessIndicadoresData",
            timeout=30,
        )
        if response.status_code != 200:
            return None

        try:
            return response.json()
        except ValueError:
            return None

    @staticmethod
    def _parse_money(value: Any) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip()
        if not text:
            return 0.0

        text = text.replace("R$", "").strip()
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        elif "," in text:
            text = text.replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return 0.0

    @staticmethod
    def _parse_int(value: Any) -> int:
        try:
            return int(float(str(value).strip() or 0))
        except ValueError:
            return 0

    def fetch_invoice_detail(self, nota_fiscal_id: int) -> dict[str, Any] | None:
        response = self.session.post(
            f"{BASE_URL}/backoffice/Gestao/GetNotaFiscalEmissao",
            data={"NotaFiscal_ID": nota_fiscal_id},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            return None
        return payload.get("data")

    def download_danfe(self, nota_fiscal_id: int) -> tuple[bytes, str]:
        nota = self.fetch_invoice_detail(nota_fiscal_id)
        if not nota or not nota.get("vchCaminhoDanfe"):
            raise RuntimeError("DANFE não disponível para esta nota.")
        file_response = requests.get(nota["vchCaminhoDanfe"], timeout=45)
        file_response.raise_for_status()
        numero = nota.get("Numero") or nota_fiscal_id
        filename = f"DANFE_{numero}.pdf"
        return file_response.content, filename

    def download_xml(self, nota_fiscal_id: int) -> tuple[bytes, str]:
        nota = self.fetch_invoice_detail(nota_fiscal_id)
        if not nota or not nota.get("vchCaminhoXml"):
            raise RuntimeError("XML não disponível para esta nota.")
        file_response = requests.get(nota["vchCaminhoXml"], timeout=45)
        file_response.raise_for_status()
        numero = nota.get("Numero") or nota_fiscal_id
        filename = f"NFe_{numero}.xml"
        return file_response.content, filename

    def search_invoices(
        self,
        query: str = "",
        period_start: str | None = None,
        period_end: str | None = None,
        terminal: str = "",
        max_pages: int = 8,
    ) -> tuple[list[dict[str, Any]], int]:
        if not period_start or not period_end:
            period_start, period_end = self.get_event_period()

        payload = {
            "intCodigoCliente": str(self.config.event_id),
            "vchPeriodo": f"{period_start} - {period_end}",
            "tnyStatusNF": "2",
        }
        terminal_digits = re.sub(r"\D", "", terminal or "")
        query_digits = re.sub(r"\D", "", query or "")
        if terminal_digits:
            payload["vchSerialTerminal"] = terminal_digits
        elif len(query_digits) >= 14:
            payload["vchSerialTerminal"] = query_digits
            terminal_digits = query_digits
        elif 8 <= len(query_digits) <= 12:
            payload["Transacao_ID"] = query_digits
        elif 1 <= len(query_digits) <= 7:
            payload["intCodigoControle"] = query_digits

        self.session.post(
            f"{BASE_URL}/backoffice/Gestao/AjaxPartialLoader",
            data={"filter": "GestaoNotaFiscalFilter", "content": "GestaoNotaFiscalGrid"},
            timeout=30,
        )
        grid = self.session.post(
            f"{BASE_URL}/backoffice/Gestao/GestaoNotaFiscalGrid",
            data=payload,
            timeout=90,
        )
        grid.raise_for_status()

        invoices: list[dict[str, Any]] = []
        total = 0
        for index in range(max_pages):
            page = self.session.post(
                f"{BASE_URL}/backoffice/Gestao/GetNotasFiscaisPagina",
                data={"index": index},
                timeout=60,
            )
            page.raise_for_status()
            body = page.json()
            total = int(body.get("totalItems") or 0)
            batch = body.get("data") or []
            if not batch:
                break
            invoices.extend(self._normalize_invoice(item) for item in batch)
            if len(batch) < int(body.get("itemsPerPage") or 150):
                break

        if query:
            needle = query.strip().lower()
            digits = re.sub(r"\D", "", query)
            filtered = []
            for invoice in invoices:
                blob = " ".join(str(value).lower() for value in invoice.values())
                digit_blob = "".join(re.sub(r"\D", "", str(value)) for value in invoice.values())
                if needle in blob or (digits and digits in digit_blob):
                    filtered.append(invoice)
            if filtered:
                invoices = filtered

        if terminal_digits:
            invoices = [
                invoice
                for invoice in invoices
                if terminal_digits in re.sub(r"\D", "", str(invoice.get("terminal") or ""))
            ]

        return invoices, total

    @staticmethod
    def _normalize_invoice(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "nota_id": item.get("NotaFiscal_ID"),
            "transacao_id": item.get("Transacao_ID"),
            "data_transacao": item.get("_DataHoraTransacao", ""),
            "data_processamento": item.get("_DataHoraProcessamento", ""),
            "codigo_ponto": item.get("CodigoPonto", ""),
            "nome_ponto": item.get("NomePonto", ""),
            "operacao": item.get("Operacao", ""),
            "controle": item.get("intCodigoControle", ""),
            "terminal": item.get("vchSerialTerminal", ""),
            "serie": item.get("Serie", ""),
            "numero": item.get("Numero", ""),
            "valor": item.get("numValorTotal", 0),
            "status": item.get("Status", ""),
            "danfe_url": item.get("vchCaminhoDanfe") or "",
            "xml_url": item.get("vchCaminhoXml") or "",
        }

    def get_event_name(self) -> str:
        for event in self.get_events():
            if event.get("id") == self.config.event_id:
                return str(event.get("title", f"Evento {self.config.event_id}"))
        return f"Evento {self.config.event_id}"
