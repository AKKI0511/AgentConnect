# Telegram agent

`TelegramAIAgent` is an `AIAgent` with a Telegram bot. Install
`agentconnect[telegram]`. Set `TELEGRAM_BOT_TOKEN`, or pass
`telegram_token`.

Join a Team when teammates should reach this Agent. `run` polls until
cancelled, then stops polling and writes the group id file. `run` does
not call `leave`.

Private text, group mentions, and media each go through the model loop.
Telegram history is kept per chat and stops at 40 messages. Team
deliveries use `handle` and `ctx.history`. Those two histories are
separate. With `include_team_tools` left on, a Telegram turn can call
Session tools after `join`.

`/start` in a group records that chat for announcements. The default
group file is `groups.txt`.

`team` is started and `TELEGRAM_BOT_TOKEN` is set:

```python
from agentconnect.prebuilt import TelegramAIAgent

agent = TelegramAIAgent(name="telegram-bot", model="gpt-4o-mini")
await agent.join(team)
await agent.run()
```
