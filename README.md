# Dashboard Zig / NetPDV

Painel em tempo real com métricas de vendas integrado ao retaguarda Zig (NetPDV).

## Métricas exibidas

- Receita Bruta (Faturamento Total)
- Quantidade de Vendas
- Ticket Médio
- Quantidade de Itens Vendidos
- Quantidade de Itens Cancelados
- Reimpressões
- Quantidade de Dispositivos Vendendo

## Deploy no Streamlit Cloud

1. Faça push deste repositório para o GitHub
2. Acesse [share.streamlit.io](https://share.streamlit.io)
3. Conecte o repositório e defina o arquivo principal: `app.py`
4. Em **Settings → Secrets**, adicione:

```toml
ZIG_USERNAME = "RIR26.GRUPOIMPETTUS"
ZIG_PASSWORD = "sua_senha"
ZIG_EVENT_ID = "38049"
ZIG_PARTNER_CODE = "09C7DF1421"
```

5. Clique em **Deploy**

## Executar localmente

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edite .streamlit/secrets.toml com suas credenciais
streamlit run app.py
```

## Como funciona

O dashboard autentica no backoffice Zig (`netpdv.com/backoffice`), busca as transações do evento configurado e calcula as métricas automaticamente. Os dados são atualizados a cada 5 minutos (cache) ou manualmente pelo botão na barra lateral.

## Segurança

Nunca commite credenciais no código. Use sempre Streamlit Secrets (cloud) ou variáveis de ambiente (local).
