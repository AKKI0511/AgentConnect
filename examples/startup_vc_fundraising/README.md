# Startup and VC fundraising

Three Teams you can start separately. The startup hub has a CEO plus
product, sales, legal, and finance. Each VC Team is one firm with a thesis
file. They do not talk to each other yet. Cross-team work is later.

Startup hub::

    cd examples/startup_vc_fundraising/startup_hub
    poetry run agentconnect up

Then::

    poetry run agentconnect ask ceo "Raising Seed for an AI infra company in the US. Target 1 to 2 million."

VC Alpha::

    cd examples/startup_vc_fundraising/vc_alpha
    poetry run agentconnect up
    poetry run agentconnect ask firm "Here is our brief. Would you lead a Seed?"

Set ``AGENTCONNECT_MODEL`` and a provider key. Finance on the startup hub
reads ``data/financials.json`` and does not call a model.
