# Telegram Agent

`TelegramAIAgent` is an `AIAgent` with a Telegram bot. Join a Team, then
`run()` to poll Telegram. Incoming Telegram text uses the same LiteLLM loop
as Team work. Telegram send and announcement operations are extra tools.

Requires `pip install 'agentconnect[telegram]'`.

## Usage

```python
from agentconnect.prebuilt import TelegramAIAgent
from agentconnect.team import Team

agent = TelegramAIAgent(
    name="telegram-bot",
    model="gpt-4o-mini",
    telegram_token="your_telegram_token",
)
team = await Team("content-squad").start()
await agent.join(team)
await agent.run()
```

`TELEGRAM_BOT_TOKEN` is used when `telegram_token` is omitted.

`groups_file` stores registered group chat ids (default `groups.txt`).

## Layout

- `TelegramAIAgent`: model loop plus Telegram polling
- `TelegramBotManager`: bot lifecycle
- `TelegramMessageProcessor`: Telegram update to a payload for the loop
- `HandlerRegistry`: `/start`, `/help`, mentions, media, private text
- `telegram_tools.py`: `Tool` values the model can call

Team deliveries still go through `process_message`. `run()` polls Telegram
only. The Session already pulls Team work after `join`.
