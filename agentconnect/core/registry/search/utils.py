"""
Registry Search Utilities - Shared formatting and population functions

These utilities handle the conversion from registry domain objects (AgentRegistration)
to search interface objects (AgentSearchResultItem) with appropriate detail levels.
"""

from typing import Dict, List
from agentconnect.core.registry.search.schemas import AgentSearchResultItem
from agentconnect.core.registry.registration import AgentRegistration, Capability, Skill


def format_capabilities_for_output(cap_list: List[Capability]) -> List[Dict[str, str]]:
    """
    Format capabilities list for search output.

    Args:
        cap_list: List of ``Capability`` objects from registry

    Returns:
        List of dictionaries with 'name' and 'description' keys
    """
    return [
        {"name": cap.name, "description": cap.description or ""} for cap in cap_list
    ]


def format_skills_for_output(skill_list: List[Skill]) -> List[Dict[str, str]]:
    """
    Format skills list for search output.

    Args:
        skill_list: List of ``Skill`` objects from registry

    Returns:
        List of dictionaries with 'name' and 'description' keys
    """
    return [
        {"name": skill.name, "description": skill.description or ""}
        for skill in skill_list
    ]


def populate_search_result_item(
    registration: AgentRegistration, similarity_score: float, output_detail_level: str
) -> AgentSearchResultItem:
    """
    Populate ``AgentSearchResultItem`` from ``AgentRegistration`` based on detail level.

    This is the core utility that transforms registry domain objects into search
    interface objects, respecting the requested level of detail.

    Args:
        registration: The agent registration from the registry
        similarity_score: Similarity score from search operation
        output_detail_level: Level of detail ('minimal', 'summary', 'capabilities', 'full')

    Returns:
        Populated ``AgentSearchResultItem`` with appropriate level of detail
    """
    item_data = {
        "agent_id": registration.agent_id,
        "similarity_score": round(similarity_score, 4),
    }

    # Minimal level fields (always try to populate if available)
    if registration.name:
        item_data["name"] = registration.name
    if registration.url:
        item_data["url"] = registration.url
    if registration.payment_address:
        item_data["payment_address"] = registration.payment_address

    if output_detail_level == "minimal":
        return AgentSearchResultItem(**item_data)

    # Summary level fields
    if registration.summary:
        item_data["summary"] = registration.summary
    if registration.tags:
        item_data["tags"] = registration.tags

    if output_detail_level == "summary":
        return AgentSearchResultItem(**item_data)

    # Capabilities level fields
    if registration.capabilities:
        item_data["capabilities"] = format_capabilities_for_output(
            registration.capabilities
        )
    if registration.skills:
        item_data["skills"] = format_skills_for_output(registration.skills)

    if output_detail_level == "capabilities":
        return AgentSearchResultItem(**item_data)

    # Full level fields (all remaining defined in AgentSearchResultItem)
    if registration.description:
        item_data["description"] = registration.description
    if registration.examples:
        item_data["examples"] = registration.examples
    if registration.version:
        item_data["version"] = registration.version
    if registration.organization:
        item_data["organization"] = registration.organization
    if registration.developer:
        item_data["developer"] = registration.developer
    if registration.auth_schemes:
        item_data["auth_schemes"] = registration.auth_schemes
    if registration.default_input_modes:
        item_data["default_input_modes"] = registration.default_input_modes
    if registration.default_output_modes:
        item_data["default_output_modes"] = registration.default_output_modes

    return AgentSearchResultItem(**item_data)
