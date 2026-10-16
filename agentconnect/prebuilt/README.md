# Prebuilt agents

Optional helpers on `BaseAgent`. Subclass `BaseAgent` when you already
have a harness. Use these when you want a LiteLLM model string, a
terminal reply, or a Telegram bot.

## AIAgent

Install `agentconnect[aiagent]`. `model` is a LiteLLM model id. Provider
keys stay in the environment.

`handle` answers a Team delivery from `ctx.history` and can call the
Session tools. Extra tools are annotated functions or `Tool` objects.
`chat` talks to the model without a Team and does not attach those
Session tools. Pass `complete` to replace LiteLLM.

`team` is started and `researcher` has joined:

```python
from agentconnect.prebuilt import AIAgent

writer = AIAgent(
    name="writer",
    model="gpt-4o-mini",
    instructions="Draft short release notes from the request.",
)
await writer.join(team)
ticket = await researcher.ask("writer", "Draft a release note: search is faster.")
if ticket.state == "completed":
    print(ticket.response.content)
```

Call `leave` when the Session should close.

## HumanAgent

Install `agentconnect[cli]`. Incoming work is printed. The reply is a
line from stdin, or from `read_line` when you supply one. Empty input
declines a request. `exit`, `quit`, or `bye` stops `start_interaction`.

`team` is started and `assistant` has joined:

```python
from agentconnect.prebuilt import HumanAgent

human = HumanAgent(name="operator-human")
await human.join(team)
await human.start_interaction("assistant")
```

## TelegramAIAgent

Install `agentconnect[telegram]`. Set `TELEGRAM_BOT_TOKEN`, or pass
`telegram_token`. Join a Team when teammates should reach the bot, then
`run` to poll. `run` stops polling when cancelled and does not call
`leave`.

Telegram text, mentions, and media use the model loop. That history is
per chat and stops at 40 messages. Team deliveries still use `handle`
and `ctx.history`. With `include_team_tools` left on, a Telegram turn
can call Session tools after `join`. `/start` in a group records that
chat for announcements. `groups_file` is rewritten when polling stops.

```python
from agentconnect.prebuilt import TelegramAIAgent

agent = TelegramAIAgent(name="telegram-bot", model="gpt-4o-mini")
await agent.join(team)
await agent.run()
```
