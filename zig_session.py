"""Configuração e sessão autenticada com o retaguarda Zig."""
from __future__ import annotations

import os

import streamlit as st

from zig_client import ZigClient, ZigConfig


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


CLIENT_CACHE_VERSION = "notas-v3-terminal-select"


@st.cache_resource(show_spinner=False)
def get_zig_client(
    username: str,
    password: str,
    event_id: int,
    partner_code: str,
    _version: str = CLIENT_CACHE_VERSION,
) -> ZigClient:
    client = ZigClient(
        ZigConfig(
            username=username,
            password=password,
            event_id=event_id,
            partner_code=partner_code,
        )
    )
    client.login()
    return client


def clear_zig_client_cache() -> None:
    get_zig_client.clear()
