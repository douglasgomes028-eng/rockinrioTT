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
        fields.append("field-formatacao=0")
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
            "produto": item.get("Produto", ""),
            "categoria": item.get("CategoriaProduto", ""),
            "quantidade": self._parse_int(item.get("Qtd", 0)),
            "valor": self._parse_money(valor),
            "gorjeta": self._parse_money(item.get("numValorGorjetaPosPago", 0)),
            "bonus": self._parse_money(item.get("Bonus", 0)),
            "taxa_ativacao": self._parse_money(item.get("TxAtivação", 0)),
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

    def get_event_name(self) -> str:
        for event in self.get_events():
            if event.get("id") == self.config.event_id:
                return str(event.get("title", f"Evento {self.config.event_id}"))
        return f"Evento {self.config.event_id}"
