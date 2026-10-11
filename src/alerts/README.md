# Alerts

Formatação e envio de alertas via Telegram.

## Módulos

- `telegram.py` — Templates + envio (`send_telegram()`, formatadores diversos)

## Funções principais

- `send_telegram(bot_token, chat_id, text, dry_run=True)` — envia texto (dry_run só loga)
- `format_alert(...)` — SIGNAL (entrada, stop, TP, R/R, tamanho)
- `format_paper_open(...)` — posição paper aberta
- `format_paper_close(...)` — posição paper fechada (com PnL)
- `format_portfolio_alert(...)` — meta BUY/SELL atingida
- `format_trade_confirmation(...)`, `format_troca_confirmation(...)`, `format_sell_confirmation(...)` — confirmações de comandos
- `format_extrato(...)`, `format_historico(...)`, `format_help()` — consultas
- `format_edit_confirmation(...)`, `format_delete_confirmation(...)` — edição/remoção
- `get_updates(bot_token, offset=0, timeout=30)` — long-poll `getUpdates` (usado pelo listener)

## Notas

- Dry-run (`cfg["system"]["dry_run"]=true`): imprime em log, não envia
- Credenciais: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` via `.env`
- Emojis para melhor legibilidade
