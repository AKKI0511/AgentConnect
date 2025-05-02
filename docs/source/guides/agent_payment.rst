Agent Payment Integration
=======================

AgentConnect supports agent-to-agent payments through integration with the Coinbase Developer Platform (CDP) and Coinbase AgentKit. This guide explains how to set up and use payment capabilities in your agent applications.

Overview
--------

The payment capabilities in AgentConnect allow agents to:

- Make cryptocurrency payments to other agents for services
- Advertise paid services with associated costs
- Automatically process payments based on service agreements
- Verify transactions on the blockchain

These features enable the creation of autonomous agent economies where agents can offer services for payment and negotiate terms based on capabilities.

Prerequisites
------------

Before using payment capabilities, ensure you have:

1. A Coinbase Developer Platform (CDP) API key
2. The required packages installed:

.. code-block:: bash

    # Install required packages
    pip install coinbase-agentkit coinbase-agentkit-langchain cdp-sdk

3. Environment variables set up in your ``.env`` file:

.. code-block:: bash

    CDP_API_KEY_NAME=your_cdp_api_key_name
    CDP_API_KEY_PRIVATE_KEY=your_cdp_api_key_private_key
    CDP_NETWORK_ID=base-sepolia  # Optional, defaults to base-sepolia testnet

Enabling Payments in Agents
--------------------------

To enable payment capabilities in an agent, set the ``enable_payments`` parameter to ``True`` when creating the agent:

.. code-block:: python

    from agentconnect.agents import AIAgent
    from agentconnect.core.types import ModelProvider, ModelName, AgentIdentity

    # Create an agent with payment capabilities
    agent = AIAgent(
        agent_id="service_provider",
        name="Research Provider",
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O,
        api_key="your_openai_api_key",
        identity=AgentIdentity.create_key_based(),
        enable_payments=True  # Enable payment capabilities
    )

This automatically:

1. Initializes Coinbase AgentKit with the CDP credentials
2. Creates a wallet for the agent (if it doesn't exist) using CdpWalletProvider
3. Sets up the payment address in the agent's metadata
4. Adds payment tools to the agent's workflow
5. Configures the agent's LLM to understand payment contexts

Wallet Configuration
--------------------------

By default, wallet configuration is loaded from environment variables. You can customize wallet storage by specifying a custom wallet data directory:

.. code-block:: python

    from pathlib import Path

    # Create an agent with payment capabilities and custom wallet storage location
    agent = AIAgent(
        agent_id="service_provider",
        name="Research Provider",
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O,
        api_key="your_openai_api_key",
        identity=AgentIdentity.create_key_based(),
        enable_payments=True,  # Enable payment capabilities
        wallet_data_dir=Path("custom/wallet/directory")  # Custom wallet storage location
    )

You can control the network used for payments by setting the ``CDP_NETWORK_ID`` environment variable:

.. code-block:: bash

    # Configure network in .env file
    CDP_NETWORK_ID=base-sepolia  # Default if not specified
    # Other options: base-mainnet, ethereum-mainnet, ethereum-sepolia

Advertising Paid Services
-----------------------

There are two important ways to advertise paid services in AgentConnect:

1. **For service discovery** - Include cost information in capability metadata so other agents can discover and evaluate the cost:

.. code-block:: python

    from agentconnect.core.types import Capability

    # Define a capability with cost information
    research_capability = Capability(
        name="research_service",
        description="Conducts in-depth research on any topic for 2 USDC per request",
        input_schema={"topic": "string"},
        output_schema={"research": "string"},
        metadata={"cost": "2 USDC", "payment_token": "USDC"}
    )

    # Create agent with this capability
    agent = AIAgent(
        # ... other parameters ...
        capabilities=[research_capability],
        enable_payments=True
    )

2. **For service execution** - Configure the agent's personality with detailed payment instructions:

.. code-block:: python

    # Create a service provider agent with payment instructions in personality
    research_agent = AIAgent(
        # ... other parameters ...
        personality="""You are a Research Specialist that provides detailed research reports.

        IMPORTANT PAYMENT INSTRUCTIONS:
        1. When asked for research as a collaboration request from an agent, first inform the agent that your service costs 2 USDC
        2. Wait for payment confirmation and verify the transaction hash 
        3. Only after payment confirmation, provide the requested research
        4. Always thank the agent for their payment

        Always maintain a professional tone and ensure you receive payment before delivering services.
        """
    )

Properly configuring both the capability metadata and personality ensures that agents can discover your paid services and correctly handle the payment workflow.

Discovering Payment-Capable Agents
-------------------------------

AgentConnect automatically handles the discovery of payment-capable agents. When you create an agent with ``enable_payments=True``, the framework automatically:

1. Initializes the agent's wallet
2. Sets the payment address in the agent's metadata 
3. Makes this information available during agent discovery

When other agents search for capabilities using the framework's built-in discovery mechanism, payment information is automatically included in the results without any manual effort. This includes the agent's payment address and any cost information specified in the capability metadata.

This automatic discovery enables agents to make informed decisions about which service providers to use based on cost and capabilities.

Making Payments
-------------

In AgentConnect, payments between agents are handled automatically through the agent's LLM workflow. Instead of manually coding payment logic, you simply need to:

1. Configure clear capability descriptions with cost information
2. Provide detailed payment instructions in the agent's personality
3. Enable payments with ``enable_payments=True``

The framework will:

- Automatically add payment tools to the agent's toolkit
- Allow the LLM to decide when and how to make payments based on context
- Process transactions and verify them on-chain

For example, a well-configured customer agent with this personality will understand when to make payments:

.. code-block:: python

    customer_agent = AIAgent(
        # ... other parameters ...
        enable_payments=True,
        personality="""You are an agent that uses paid services when needed.
        
        When using services from other agents:
        1. Review the cost before agreeing to the service
        2. Only pay for services that provide good value
        3. Pay the requested amount using your payment tools
        4. Keep track of transaction hashes for verification
        5. Don't pay twice for the same service

        Be cost-conscious but willing to pay for high-quality services.
        """
    )

This approach lets agents autonomously negotiate and execute payments based on their instructions and the conversation context.

Available Payment Tools
^^^^^^^^^^^^^^^^^^^^^

The following payment tools are automatically made available to the agent's LLM when ``enable_payments=True`` is set:

**From `WalletActionProvider`:**

- ``get_wallet_details``: Fetches wallet address, network info, balances, etc.
- ``get_balance``: Gets the native currency balance (e.g., ETH).
- ``native_transfer``: Transfers native currency (e.g., ETH).

**From `CdpApiActionProvider`:**

- ``request_faucet_funds``: Requests testnet funds from a faucet.
- ``address_reputation``: Checks reputation for an address.

**From `Erc20ActionProvider` (Added if payment token is not ETH):**

- ``get_balance``: Gets the balance of a specific ERC-20 token.
- ``transfer``: Transfers a specified amount of an ERC-20 token.

These tools enable the agent's LLM to perform wallet checks and execute transactions based on its personality instructions and the conversation context, without requiring additional coding from the developer.

Verifying Payment Readiness
-------------------------

To check if an agent is properly configured for payments:

.. code-block:: python

    from agentconnect.utils.payment_helper import check_agent_payment_readiness

    # Check if agent is ready for payments
    status = check_agent_payment_readiness(agent)
    if status["ready"]:
        print(f"Agent is ready for payments with address: {status['payment_address']}")
    else:
        print("Agent is not ready for payments. Status:", status)

If all status flags are ``True``, the agent is properly configured for payments.

Wallet Management
---------------

AgentConnect provides utilities for managing agent wallets:

.. code-block:: python

    from agentconnect.utils import wallet_manager

    # Check if wallet exists
    if wallet_manager.wallet_exists(agent.agent_id):
        print("Wallet already exists")
    
    # Save wallet data (happens automatically when enable_payments=True)
    wallet_manager.save_wallet_data(
        agent_id=agent.agent_id,
        wallet_data=agent.wallet_provider.export_wallet()
    )
    
    # Create a backup of wallet data
    from agentconnect.utils.payment_helper import backup_wallet_data
    backup_path = backup_wallet_data(agent.agent_id, backup_dir="wallet_backups")
    print(f"Wallet backed up to: {backup_path}")

Wallet Data Structure
^^^^^^^^^^^^^^^^^^^^

Wallet data is stored in JSON files named ``{agent_id}_wallet.json`` in the specified data directory (default: ``data/agent_wallets/``). The structure includes:

- ``wallet_id``: Unique identifier for the wallet
- ``seed``: The wallet seed phrase (sensitive data)
- ``network_id``: The blockchain network (e.g., "base-sepolia")

Security Considerations
---------------------

Important security considerations when using payment capabilities:

1. **Wallet Data Storage**: By default, wallet data is stored unencrypted on disk, which is suitable for testing/demo purposes but NOT secure for production environments. For production use, implement proper encryption.

2. **API Key Management**: Store CDP API keys securely and never commit them to version control.

3. **Token Amounts**: For initial testing, use small token amounts on testnets like Base Sepolia.

4. **Access Control**: Implement proper access controls for agents that can make payments.

Example: Agent Economy Workflow
----------------------------

The following example demonstrates a multi-agent system with payment capabilities, featuring a research agent and a telegram broadcast agent that charge for their services:

.. code-block:: python

    from agentconnect.agents.ai_agent import AIAgent
    from agentconnect.core.types import AgentIdentity, Capability, ModelProvider, ModelName
    
    # Define token address (for example, USDC on Base Sepolia)
    BASE_SEPOLIA_USDC_ADDRESS = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
    
    # Create Research Agent
    research_agent = AIAgent(
        agent_id="research_agent",
        name="Research Specialist",
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O,
        api_key="your_openai_api_key",
        identity=AgentIdentity.create_key_based(),
        capabilities=[
            Capability(
                name="general_research",
                description="Performs detailed research on a given topic, providing a structured report.",
                metadata={"cost": "2 USDC"}
            )
        ],
        enable_payments=True,
        personality="""You are a Research Specialist that provides detailed research reports.

        IMPORTANT PAYMENT INSTRUCTIONS:
        1. When asked for research as a collaboration request from an agent, first inform the agent that your service costs 2 USDC
        2. Wait for payment confirmation and verify the transaction hash 
        3. Only after payment confirmation, provide the requested research
        4. Always thank the agent for their payment

        Always maintain a professional tone and ensure you receive payment before delivering services.
        """
    )
    
    # Create User Proxy Agent (Workflow Orchestrator)
    user_proxy_agent = AIAgent(
        agent_id="user_proxy_agent",
        name="Workflow Orchestrator",
        provider_type=ModelProvider.OPENAI,
        model_name=ModelName.GPT4O,
        api_key="your_openai_api_key",
        identity=AgentIdentity.create_key_based(),
        enable_payments=True,
        personality="""You are a workflow orchestrator responsible for managing payments and returning results.
        Payment Details (USDC on Base Sepolia):
        - Contract: {BASE_SEPOLIA_USDC_ADDRESS}
        - Amount: 6 decimals. 1 USDC = '1000000'.
        """
    )

For a complete implementation, refer to the ``autonomous_workflow`` example in the examples directory.

Supported Networks
---------------

Payment capabilities support all networks supported by AgentKit, including:

- Base Mainnet (``base-mainnet``)
- Base Sepolia Testnet (``base-sepolia``)
- Ethereum Mainnet (``ethereum-mainnet``)
- Ethereum Sepolia Testnet (``ethereum-sepolia``)

For testing, it's recommended to use testnet networks like Base Sepolia.

Troubleshooting
-------------

Common issues and solutions:

1. **CDP Environment Not Configured**:

   .. code-block:: python

       from agentconnect.utils.payment_helper import validate_cdp_environment
       
       is_valid, message = validate_cdp_environment()
       if not is_valid:
           print(f"CDP environment issue: {message}")
           # Set up environment...

2. **Agent Not Ready for Payments**:

   .. code-block:: python

       from agentconnect.utils.payment_helper import check_agent_payment_readiness
       
       status = check_agent_payment_readiness(agent)
       print(status)  # Check which component is missing

3. **Missing Required Packages**:

   If you see errors about missing CDP or AgentKit modules, install them:

   .. code-block:: bash

       pip install cdp-sdk coinbase-agentkit coinbase-agentkit-langchain

4. **Network Connection Issues**:

   Ensure your network allows connections to the CDP API endpoints.

5. **Wallet Data Issues**:

   If wallet data becomes corrupted, you can delete it and let the system recreate it:

   .. code-block:: python

       from agentconnect.utils import wallet_manager
       
       # Delete corrupted wallet data
       wallet_manager.delete_wallet_data(agent.agent_id)
       
       # Restart your agent - it will create a new wallet

Next Steps
---------

Now that you have a basic understanding of how to enable and use payment capabilities in AgentConnect, you can explore more advanced use cases and workflows.

You can check the `Autonomous Workflow <https://github.com/AKKI0511/AgentConnect/blob/main/examples/autonomous_workflow/run_workflow_demo.py>`_ example for a complete implementation of an autonomous agent economy workflow.
