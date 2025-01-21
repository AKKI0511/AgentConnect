from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages
from typing import Annotated, Sequence, TypedDict

from src.core.types import ModelProvider, ModelName
from src.providers.provider_factory import ProviderFactory
from .templates.system_prompts import SystemPrompts, SystemPromptConfig


class State(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


class ChainFactory:
    @staticmethod
    def create_conversation_chain(
        provider_type: ModelProvider,
        model_name: ModelName,
        api_key: str,
        system_config: SystemPromptConfig,
    ):
        # ? In the future initialize memory (redis/postgresql)
        # memory_manager = MemoryManager(
        #     memory_type=memory_type,
        #     session_id=session_id,
        #     redis_url=redis_url,
        #     \**kwargs
        # )

        # Get components
        system_prompt = SystemPrompts.get_assistant_prompt(system_config)

        # Create prompt template with examples and instructions
        prompt_messages = [system_prompt, MessagesPlaceholder(variable_name="messages")]

        # ? Future examples and instructions integration
        # Add examples if provided
        # examples = ExampleTemplates.get_conversation_examples(conv_type)
        # instructions = Instructions.get_instruction_set(instruction_type)
        # for example in examples:
        # prompt_messages.extend([
        #     HumanMessagePromptTemplate.from_template(example["user"]),
        #     AIMessagePromptTemplate.from_template(example["assistant"])
        # ])

        prompt = ChatPromptTemplate.from_messages(prompt_messages)

        # Get the provider
        provider = ProviderFactory.create_provider(provider_type, api_key)
        llm = provider.get_langchain_llm(
            model_name=model_name,
            temperature=system_config.temperature,
            max_tokens=system_config.max_tokens,
        )

        runnable = prompt | llm

        # Create the state graph for managing conversation flow
        workflow = StateGraph(state_schema=State)

        # Define the message processing node
        def call_model(state: State):
            response = runnable.invoke(state)
            return {"messages": [response]}

        # Add nodes to the graph
        workflow.set_entry_point("model")
        workflow.add_node("model", call_model)

        # TODO: In the future replace with PostgresSaver / AsyncPostgresSaver for production
        memory = MemorySaver()

        # Attach the workflow to the chain for state management
        # When we run the application, we pass in a configuration dict that specifies a thread_id.
        # This ID is used to distinguish conversational threads (e.g., between different users).
        # config = {"configurable": {"thread_id": "abc123"}}
        app = workflow.compile(checkpointer=memory)
        return app
