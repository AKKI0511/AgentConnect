import asyncio
import os
from dotenv import load_dotenv
import json

from src.agents.ai_agent import AIAgent
from src.communication.hub import CommunicationHub
from src.core.registry import AgentRegistry
from src.core.types import (
    AgentType, InteractionMode, ModelProvider, ModelName, 
    MessageType, AgentIdentity, VerificationStatus
)
from src.utils.logging_config import LogLevel, setup_logging

# Sample e-commerce dataset for analysis
ECOMMERCE_DATA = {
    "daily_metrics": {
        "sales": [
            {"date": "2024-03-01", "revenue": 15234, "orders": 423, "avg_order_value": 36},
            {"date": "2024-03-02", "revenue": 18456, "orders": 512, "avg_order_value": 36.05},
            {"date": "2024-03-03", "revenue": 21654, "orders": 587, "avg_order_value": 36.89},
            # ... more daily data
        ],
        "user_behavior": {
            "cart_abandonment_rate": 0.68,
            "browse_to_buy_ratio": 0.12,
            "return_customer_rate": 0.45
        },
        "product_performance": [
            {"category": "Electronics", "revenue": 45678, "units_sold": 789},
            {"category": "Clothing", "revenue": 34567, "units_sold": 1234},
            {"category": "Home", "revenue": 23456, "units_sold": 567}
        ]
    },
    "customer_segments": {
        "new_customers": 1234,
        "returning_customers": 567,
        "vip_customers": 123
    },
    "marketing_campaigns": [
        {"name": "Spring Sale", "spend": 5000, "revenue": 25000, "roas": 5},
        {"name": "Email Campaign", "spend": 1000, "revenue": 15000, "roas": 15},
        {"name": "Social Media", "spend": 3000, "revenue": 12000, "roas": 4}
    ]
}

setup_logging(
    level=LogLevel.INFO,
    module_levels={
        'AgentRegistry': LogLevel.WARNING,
        'CommunicationHub': LogLevel.WARNING,
        'AgentProtocol': LogLevel.WARNING,
    }
)

async def run_ecommerce_analysis_demo():
    """Demonstrates autonomous agents analyzing real e-commerce data"""
    
    print("\n=== Starting E-commerce Data Analysis Demo ===\n")
    
    load_dotenv()
    registry = AgentRegistry()
    hub = CommunicationHub(registry)
    
    # Create identities for agents
    data_processor_identity = AgentIdentity(
        did="did:key:processor1",
        verification_status=VerificationStatus.VERIFIED,
        public_key="processor_public_key",
        private_key="processor_private_key"
    )
    
    analyst_identity = AgentIdentity(
        did="did:key:analyst1",
        verification_status=VerificationStatus.VERIFIED,
        public_key="analyst_public_key",
        private_key="analyst_private_key"
    )
    
    print("🤖 Initializing AI Agents...")
    # Create two AI agents with different capabilities
    data_processor = AIAgent(
        agent_id="processor1",
        name="DataProcessor",
        provider_type=ModelProvider.GROQ,
        model_name=ModelName.LLAMA33_70B_VTL,
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        identity=data_processor_identity,
        capabilities=["data_processing", "statistical_analysis", "trend_detection"],
        interaction_modes=[InteractionMode.AGENT_TO_AGENT],
        personality="detail-oriented data analyst focused on identifying key metrics and trends"
    )
    
    business_analyst = AIAgent(
        agent_id="analyst1",
        name="BusinessAnalyst",
        provider_type=ModelProvider.GROQ,
        model_name=ModelName.LLAMA3_70B,
        api_key=os.getenv("OPENAI_API_KEY"),
        identity=analyst_identity,
        capabilities=["business_analysis", "strategy_recommendation", "performance_optimization"],
        interaction_modes=[InteractionMode.AGENT_TO_AGENT],
        personality="strategic business analyst focused on actionable insights and recommendations"
    )
    
    print("📝 Registering agents with the hub...")
    await hub.register_agent(data_processor)
    await hub.register_agent(business_analyst)
    print("✅ Agents registered successfully\n")
    
    processor_task = asyncio.create_task(data_processor.run())
    analyst_task = asyncio.create_task(business_analyst.run())
    
    try:
        print("=== Starting E-commerce Analysis ===\n")
        
        # Initialize analysis with real data
        await data_processor.send_message(
            receiver_id=business_analyst.agent_id,
            content=f"""I have processed our e-commerce platform's recent performance data. 
            Here's the detailed dataset for analysis:
            {json.dumps(ECOMMERCE_DATA, indent=2)}
            
            Could you analyze this data and provide strategic insights on:
            1. Revenue trends and opportunities
            2. Customer segment performance
            3. Marketing campaign effectiveness
            4. Recommendations for optimization""",
            metadata={
                "task": "ecommerce_analysis",
                "data_type": "performance_metrics",
                "time_period": "current_month",
                "analysis_required": [
                    "trend_analysis",
                    "segment_performance",
                    "campaign_effectiveness",
                    "optimization_recommendations"
                ]
            }
        )
        
        print("🔄 Agents are analyzing the e-commerce data...")
        print("\n=== Live Analysis Discussion ===\n")
        
        # Monitor and display the autonomous analysis discussion
        previous_message_count = 0
        for _ in range(10):  # Allow for more exchanges due to complex analysis
            await asyncio.sleep(2)
            messages = hub.get_message_history()
            
            # Display only new messages
            if len(messages) > previous_message_count:
                for msg in messages[previous_message_count:]:
                    print(f"🤖 {msg.sender_id}:\n{msg.content}\n")
                previous_message_count = len(messages)
        
        print("\n=== Analysis Summary ===")
        print(f"Total messages exchanged: {len(hub.get_message_history())}")
        
    finally:
        print("\n🛑 Concluding analysis session...")
        data_processor.is_running = False
        business_analyst.is_running = False
        await processor_task
        await analyst_task
        await hub.unregister_agent(data_processor.agent_id)
        await hub.unregister_agent(business_analyst.agent_id)
        print("✅ Analysis session completed")

if __name__ == "__main__":
    asyncio.run(run_ecommerce_analysis_demo())
