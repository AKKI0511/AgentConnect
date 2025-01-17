import asyncio
import os
from dotenv import load_dotenv
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from src.agents.human_agent import HumanAgent
from src.agents.ai_agent import AIAgent
from src.communication.hub import CommunicationHub
from src.core.registry import AgentRegistry
from src.core.types import (
    ModelProvider,
    ModelName,
    InteractionMode,
    AgentIdentity,
    VerificationStatus,
)
from src.providers.provider_factory import ProviderFactory
from src.utils.logging_config import LogLevel, setup_logging

# Configure logging before anything else
setup_logging(
    level=LogLevel.INFO,  # Default level
    module_levels={
        'AgentRegistry': LogLevel.WARNING,  # Less verbose
        'CommunicationHub': LogLevel.INFO,  # Normal verbosity
        'SimpleAgentProtocol': LogLevel.DEBUG,  # More verbose
    }
)

async def main():
    load_dotenv()  # Load environment variables from .env file

    # Initialize registry and hub
    registry = AgentRegistry()
    hub = CommunicationHub(registry)

    # Generate key pairs for agents
    def generate_key_pair():
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        return public_pem, private_pem

    # Create identities with proper keys
    human_public, human_private = generate_key_pair()
    ai_public, ai_private = generate_key_pair()

    human_identity = AgentIdentity(
        did="did:key:human1",
        verification_status=VerificationStatus.VERIFIED,
        public_key=human_public,
        private_key=human_private
    )

    ai_identity = AgentIdentity(
        did="did:key:ai1",
        verification_status=VerificationStatus.PENDING,
        public_key=ai_public,
        private_key=ai_private
    )

    # Get provider type and model from user input
    print("Available providers:")
    for provider in ModelProvider:
        print(f"- {provider.value}")

    provider_name = input("Select provider: ").lower()
    provider_type = ModelProvider(provider_name)

    # Get API key from environment
    api_key = os.getenv(f"{provider_name.upper()}_API_KEY")
    if not api_key:
        raise ValueError(f"Missing API key for {provider_name}")

    # Create provider instance to get available models
    provider = ProviderFactory.create_provider(provider_type, api_key)

    print("\nAvailable models:")
    available_models = provider.get_available_models()
    for model in available_models:
        print(f"- {model.value}")

    model_name = ModelName(input("Select model: "))

    # Initialize agents with proper identities and interaction modes
    human = HumanAgent(
        agent_id="human1", name="User", identity=human_identity, organization_id="org1"
    )

    ai_assistant = AIAgent(
        agent_id="ai1",
        name="Assistant",
        provider_type=provider_type,
        model_name=model_name,
        api_key=api_key,
        identity=ai_identity,
        capabilities=["conversation"],
        interaction_modes=[InteractionMode.HUMAN_TO_AGENT],
        personality="helpful and professional",
        organization_id="org1",
    )

    # Register agents with the hub
    if not await hub.register_agent(human):
        raise RuntimeError("Failed to register human agent")
    if not await hub.register_agent(ai_assistant):
        raise RuntimeError("Failed to register AI agent")

    # Verify AI agent's identity
    if not await ai_assistant.verify_identity():
        raise RuntimeError("AI agent identity verification failed")

    # Start AI agent's message processing loop
    ai_task = asyncio.create_task(ai_assistant.run())

    try:
        # Start interaction using HumanAgent's built-in method
        await human.start_interaction(ai_assistant)
    except KeyboardInterrupt:
        print("\nChat session ended by user.")
    finally:
        # Clean up
        print("\nClosing session...")
        ai_assistant.is_running = False
        await ai_task

        # Unregister agents
        await hub.unregister_agent(human.agent_id)
        await hub.unregister_agent(ai_assistant.agent_id)


if __name__ == "__main__":
    asyncio.run(main())
