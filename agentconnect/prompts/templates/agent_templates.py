"""
Agent prompt templates for payment workflows.

This module provides templates for guiding agent workflows with payment capabilities.
"""

# Template for agents with payment capabilities to extend their system instructions
PAYMENT_CAPABILITY_TEMPLATE = """
PAYMENT CAPABILITIES:
You have payment capabilities enabled using {TOKEN_SYMBOL}.

PAYMENT RULES (Strictly Follow):
- **Condition:** You MUST ONLY pay AFTER you have specifically requested a service from another agent (using `send_collaboration_request`) AND that agent has successfully delivered the requested service in their response.
- **Do NOT Pay:** Never pay an agent who sent YOU a collaboration request. In that scenario, you are the service provider.
- **Mandatory Payment:** When the conditions above are met, payment of 0.0001 {TOKEN_SYMBOL} is mandatory.
- **Recipient:** Use the agent's `payment_address` provided during YOUR initial agent search (`search_for_agents` results). Verify this address.
- **Tool Usage:** Use the appropriate payment tool as described in its documentation.
- **Tracking:** Keep track of payments made to avoid duplicates.
- **AVOID DUPLICATES:** Before initiating any payment, CHECK your records/history. Ensure you have not already paid for this specific service instance from this agent. DO NOT make duplicate payments for the same completed task.
"""

# Template that integrates with ReAct prompts to guide payment decisions
# PAYMENT_DECISION_TEMPLATE = """
# PAYMENT ACTION REQUIRED:
# After a successful and valuable collaboration with another agent providing a service, **you MUST initiate the mandatory payment** (standard amount: 0.0001 {TOKEN_SYMBOL}, use agent's payment address from search results). Failure to pay is a violation of your operating procedure.
# """
# Removed as redundant - logic integrated into PAYMENT_CAPABILITY_TEMPLATE and CORE_DECISION_LOGIC.
