"""Cálculo das métricas do dashboard."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DashboardMetrics:
    receita_bruta: float
    quantidade_vendas: int
    ticket_medio: float
    quantidade_itens_vendidos: int
    quantidade_itens_cancelados: int
    reimpressoes: int
    quantidade_dispositivos_vendendo: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "receita_bruta": self.receita_bruta,
            "quantidade_vendas": self.quantidade_vendas,
            "ticket_medio": self.ticket_medio,
            "quantidade_itens_vendidos": self.quantidade_itens_vendidos,
            "quantidade_itens_cancelados": self.quantidade_itens_cancelados,
            "reimpressoes": self.reimpressoes,
            "quantidade_dispositivos_vendendo": self.quantidade_dispositivos_vendendo,
        }


SALE_KEYWORDS = ("compra", "venda", "consumo", "ficha")
CANCEL_KEYWORDS = ("cancel", "estorn", "devol")


def _is_sale(transaction: dict[str, Any]) -> bool:
    status = str(transaction.get("status", "")).lower()
    operacao = str(transaction.get("operacao", "")).lower()
    if any(word in status for word in CANCEL_KEYWORDS):
        return False
    if "efetiv" in status or status == "":
        return any(word in operacao for word in SALE_KEYWORDS)
    return False


def _is_cancelled(transaction: dict[str, Any]) -> bool:
    status = str(transaction.get("status", "")).lower()
    operacao = str(transaction.get("operacao", "")).lower()
    return any(word in status for word in CANCEL_KEYWORDS) or any(
        word in operacao for word in CANCEL_KEYWORDS
    )


def _cancelled_quantity(transaction: dict[str, Any]) -> int:
    quantity = abs(transaction.get("quantidade", 0))
    return quantity if quantity else 1


def compute_metrics(
    transactions: list[dict[str, Any]],
    pending_prints: list[dict[str, Any]] | None = None,
    indicators: dict[str, Any] | None = None,
) -> DashboardMetrics:
    sales = [tx for tx in transactions if _is_sale(tx)]
    cancelled = [tx for tx in transactions if _is_cancelled(tx)]

    receita_bruta = sum(tx.get("valor", 0.0) for tx in sales)
    quantidade_vendas = len(sales)
    quantidade_itens_vendidos = sum(tx.get("quantidade", 0) for tx in sales)
    quantidade_itens_cancelados = sum(_cancelled_quantity(tx) for tx in cancelled)
    ticket_medio = receita_bruta / quantidade_vendas if quantidade_vendas else 0.0

    terminals = {
        str(tx.get("terminal", "")).strip()
        for tx in sales
        if str(tx.get("terminal", "")).strip()
    }
    quantidade_dispositivos_vendendo = len(terminals)

    reimpressoes = 0
    if pending_prints:
        reimpressoes = sum(
            int(item.get("qtdPedidos", 0) or 0) for item in pending_prints
        )

    if indicators and indicators.get("indicadores"):
        indic = indicators["indicadores"]
        consumo = float(indic.get("Consumo") or 0)
        if consumo > 0:
            receita_bruta = consumo
            ticket_medio = receita_bruta / quantidade_vendas if quantidade_vendas else 0.0

        term_caixa = int(indic.get("QtdTerminaisCaixa") or 0)
        term_bar = int(indic.get("QtdTerminaisBar") or 0)
        if term_caixa or term_bar:
            quantidade_dispositivos_vendendo = term_caixa + term_bar

    return DashboardMetrics(
        receita_bruta=receita_bruta,
        quantidade_vendas=quantidade_vendas,
        ticket_medio=ticket_medio,
        quantidade_itens_vendidos=quantidade_itens_vendidos,
        quantidade_itens_cancelados=quantidade_itens_cancelados,
        reimpressoes=reimpressoes,
        quantidade_dispositivos_vendendo=quantidade_dispositivos_vendendo,
    )
