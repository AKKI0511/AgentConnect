"""
Tests for React prompts with payment capabilities.
"""
import sys
import os

# Add the parent directory to the system path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agentconnect.prompts.templates.prompt_templates import (
    ReactConfig,
    PromptTemplates
)

def test_react_prompt_with_payments():
    """Test that React prompt works with payment capabilities enabled."""
    # Set up a ReactConfig with payment capabilities
    react_config = ReactConfig(
        name="Payment Agent",
        capabilities=[
            {"name": "Conversation", "description": "general assistance"},
            {"name": "Payments", "description": "can pay for services"}
        ],
        personality="helpful and professional",
        mode="system_prompt",
        additional_context={"custom_field": "custom value"},
        enable_payments=True,
        payment_token_symbol="ETH",
        role="payment assistant"
    )
    
    # Create prompt
    prompt_templates = PromptTemplates()
    prompt = prompt_templates.get_react_prompt(react_config)
    
    # Get the template string
    template_string = prompt.prompt.template
        
    return template_string

if __name__ == "__main__":
    # Run the test and print the template
    template = test_react_prompt_with_payments()
    print("\nGenerated template:")
    print("=" * 80)
    print(template)
    print("=" * 80)
    print("...") 