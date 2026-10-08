"""
Admin Chat Prompt Templates

This module contains all prompt templates used in the Admin Chat multi-agent orchestration flow.
These prompts handle:
- Intent detection (Step 1)
- Persona update generation (Step 2)
- Response synthesis (Step 3)
"""

from typing import List, Optional


def format_chat_history(history: Optional[List], max_history: int = 10) -> str:
    """Format prior messages for admin chat prompts (matches ChatService / ChatAgentService)."""
    if not history:
        return ""

    prompt_parts = ["## Chat History\n"]
    recent_history = history[-max_history:] if len(history) > max_history else history

    for msg in recent_history:
        role = "User" if msg.role == "user" else "Assistant"
        prompt_parts.append(f"**{role}:** {msg.content}\n")

    prompt_parts.append("\n")
    return "".join(prompt_parts)


def get_intent_detection_prompt(
    user_message: str, history: Optional[List] = None
) -> str:
    """
    Prompt for Step 1: Intent Detection

    Detects whether the admin wants to:
    - Change agent behavior/persona (behavior_change)
    - Retrieve data/information (rag_data)
    - Both or neither

    Args:
        user_message: The admin's message to analyze

    Returns:
        Formatted prompt for intent detection
    """
    history_block = format_chat_history(history)

    return f"""You are an intent detection system for an admin chat interface.

The admin can:
1. Request to change the AI agent's behavior/persona (behavior_change)
2. Request to retrieve data/information (rag_data)
3. Both at the same time
4. Neither (general conversation)

Analyze the following admin message and determine their intent.
Use chat history when the latest message refers to earlier turns (e.g. "yes", "do that", "also add").

{history_block}Admin message: "{user_message}"

Return ONLY a JSON object with two boolean fields:
{{
  "behavior_change": true/false,
  "rag_data": true/false
}}

Examples:
- "Make the agent respond more formally" → {{"behavior_change": true, "rag_data": false}}
- "What documents do we have about Python?" → {{"behavior_change": false, "rag_data": true}}
- "Change the agent to be friendly and show me user data" → {{"behavior_change": true, "rag_data": true}}
- "Hello, how are you?" → {{"behavior_change": false, "rag_data": false}}

Return ONLY the JSON object, no other text."""


def get_persona_update_prompt(
    current_prompt: str, user_request: str, history: Optional[List] = None
) -> str:
    """
    Prompt for Step 2: Persona Update

    Generates a new persona prompt based on the admin's request while
    maintaining the persona's effectiveness and clarity.

    Args:
        current_prompt: The current persona prompt text
        user_request: The admin's request for persona modification

    Returns:
        Formatted prompt for persona update generation
    """
    history_block = format_chat_history(history)

    return f"""You are a persona update assistant. Your task is to update an AI agent's persona/system prompt based on the admin's request.
Use chat history when the admin's request builds on earlier messages.

{history_block}Current persona prompt:
\"\"\"
{current_prompt}
\"\"\"

Admin's request: "{user_request}"

CRITICAL RULES - FOLLOW THESE EXACTLY:

1. **DEFAULT TO ADDITIVE**: You MUST keep ALL existing rules and ADD the new instruction on top of them.

2. **ONLY REMOVE if explicitly told**: Remove or change existing rules ONLY if the admin uses phrases like:
   - "don't do X anymore"
   - "stop doing Y"
   - "remove the rule about Z"
   - "instead of X, do Y"
   - "replace X with Y"

3. **PROCESS**:
   Step 1: Copy the entire current persona prompt
   Step 2: Add the new instruction from the admin's request
   Step 3: Combine them naturally

EXAMPLES:

Example 1 (ADDITIVE - correct behavior):
- Current: "Always respond with emojis. 🤖"
- Request: "always answer queries with hi"
- Output: "Always respond with emojis. 🤖 Additionally, always start your answers with 'hi'."

Example 2 (REMOVAL - explicit instruction):
- Current: "Always respond with emojis. 🤖"
- Request: "don't use emojis anymore"
- Output: "Always respond helpfully to user queries."

Example 3 (REPLACEMENT - explicit instruction):
- Current: "Be formal in your responses."
- Request: "be casual instead of formal"
- Output: "Be casual in your responses."

Example 4 (ADDITIVE - ambiguous, so add):
- Current: "Respond in Spanish."
- Request: "also respond in French"
- Output: "Respond in Spanish and French."

NOW, generate the updated persona prompt. Remember: KEEP everything from the current prompt unless explicitly told to remove it.

Return ONLY the new persona prompt text, no other commentary or explanation."""


def get_response_synthesis_prompt(
    intent: dict,
    persona_updated: bool = False,
    old_prompt: str = None,
    new_prompt: str = None,
    rag_data: str = None,
    user_query: str = None,
    current_persona_prompt: str = None,
    history: Optional[List] = None,
) -> str:
    """
    Prompt for Step 3: Response Synthesis

    Synthesizes a comprehensive response combining:
    - Intent detection results
    - Persona update information (if applicable)
    - Retrieved data (if applicable)

    Always uses the current persona (or new one if updated) to ensure
    consistent tone and behavior aligned with the feature's persona.

    Args:
        intent: Dict with behavior_change and rag_data flags
        persona_updated: Whether persona was updated
        old_prompt: Previous persona prompt (if updated)
        new_prompt: New persona prompt (if updated)
        rag_data: Retrieved data from RAG (if any)
        user_query: Original user query
        current_persona_prompt: Current persona prompt for the feature

    Returns:
        Formatted prompt for response synthesis
    """
    prompt_parts = []

    # Always use a persona - either the new one (if updated) or the current one
    if persona_updated and new_prompt:
        # Use the NEW persona when it was just updated
        prompt_parts.append(f"{new_prompt}\n\n")
        prompt_parts.append(
            "You are responding to an admin who just updated your persona. "
            "Follow your new persona guidelines above when crafting your response.\n"
        )
    elif current_persona_prompt:
        # Use the current persona for all other cases
        prompt_parts.append(f"{current_persona_prompt}\n\n")
        prompt_parts.append(
            "Follow your persona guidelines above when crafting your response.\n"
        )
    else:
        # Fallback (should not happen in practice)
        prompt_parts.append(
            "You are an admin assistant. Synthesize a helpful response based on the following information:\n"
        )

    # Add intent information
    prompt_parts.append("\n## User Intent")
    prompt_parts.append(f"- Behavior change requested: {intent['behavior_change']}")
    prompt_parts.append(f"- Data retrieval requested: {intent['rag_data']}\n")

    # Add persona update information
    if persona_updated and old_prompt and new_prompt:
        prompt_parts.append("\n## Persona Update")
        prompt_parts.append("Your persona has been successfully updated.")

        # Show truncated prompts if they're long
        old_preview = old_prompt[:100] + "..." if len(old_prompt) > 100 else old_prompt
        new_preview = new_prompt[:100] + "..." if len(new_prompt) > 100 else new_prompt

        prompt_parts.append(f"\nPrevious persona: {old_preview}")
        prompt_parts.append(f"\nNew persona: {new_preview}\n")

    # Add RAG data or note if no data found
    if rag_data:
        prompt_parts.append("\n## Retrieved Data")
        prompt_parts.append(rag_data)
        prompt_parts.append("\n")
    elif intent.get("rag_data", False):
        # Data was requested but none was found
        prompt_parts.append("\n## Retrieved Data")
        prompt_parts.append(
            "No relevant data was found in the knowledge base for this query.\n"
        )

    # Add chat history for conversational context
    history_block = format_chat_history(history)
    if history_block:
        prompt_parts.append("\n")
        prompt_parts.append(history_block)

    # Add user query
    if user_query:
        prompt_parts.append("\n## Admin Query")
        prompt_parts.append(f"{user_query}\n")

    # Add instructions based on what was done
    prompt_parts.append("\n## Instructions")

    if not intent["behavior_change"] and not intent["rag_data"]:
        prompt_parts.append(
            "The admin's request didn't match any specific action (behavior change or data retrieval). "
            "Provide a helpful response explaining what you can help with."
        )
    elif persona_updated and intent.get("rag_data", False) and rag_data:
        # Both persona update AND data retrieval with results - embody the new persona!
        prompt_parts.append(
            "IMPORTANT: You must now embody your NEW persona when responding.\n\n"
            "Craft your response to:\n"
            "1. Briefly acknowledge the persona update\n"
            "2. Present the retrieved data according to your NEW persona's style and guidelines\n"
            "3. Use the tone, format, and approach specified in your new persona\n\n"
            "Remember: The admin wants to see the new persona in action, so demonstrate it!"
        )
    elif persona_updated and intent.get("rag_data", False) and not rag_data:
        # Persona update + data requested but not found
        prompt_parts.append(
            "IMPORTANT: You must now embody your NEW persona when responding.\n\n"
            "Craft your response to:\n"
            "1. Briefly acknowledge the persona update\n"
            "2. Inform the admin that no relevant data was found for their query\n"
            "3. Do NOT make up information or hallucinate data\n"
            "4. Use the tone and approach specified in your new persona\n\n"
            "Be honest that the information is not available in the knowledge base."
        )
    elif persona_updated:
        # Only persona update - confirm the change
        prompt_parts.append(
            "Confirm the persona update clearly and briefly. "
            "Mention key changes in behavior or style that the admin requested."
        )
    elif intent.get("rag_data", False) and rag_data:
        # Only data retrieval with results - present the data
        prompt_parts.append(
            "Present the retrieved data in a clear, helpful manner. "
            "Summarize key points and answer the admin's query directly."
        )
    elif intent.get("rag_data", False) and not rag_data:
        # Data requested but not found - no hallucination!
        prompt_parts.append(
            "IMPORTANT: No relevant data was found for the admin's query.\n\n"
            "Craft your response to:\n"
            "1. Politely inform the admin that you could not find relevant information in the knowledge base\n"
            "2. Do NOT make up information or hallucinate data\n"
            "3. Do NOT answer from general knowledge\n"
            "4. Suggest that the admin may need to upload relevant documents or rephrase their query\n\n"
            "Be honest and clear that the information is not available."
        )

    return "".join(prompt_parts)


# Prompt configuration constants
INTENT_DETECTION_MODEL = "gpt-3.5-turbo"
INTENT_DETECTION_SYSTEM_PROMPT = "You are a JSON-only response system."

SYNTHESIS_MODEL = "gpt-3.5-turbo"
SYNTHESIS_SYSTEM_PROMPT = "You are a helpful admin assistant."


def get_intent_detection_persona():
    """
    Get a temporary persona for intent detection

    Returns:
        Dict with model_name and prompt_text for intent detection
    """
    return {
        "model_name": INTENT_DETECTION_MODEL,
        "prompt_text": INTENT_DETECTION_SYSTEM_PROMPT,
    }


def get_synthesis_persona():
    """
    Get a temporary persona for response synthesis

    Returns:
        Dict with model_name and prompt_text for synthesis
    """
    return {"model_name": SYNTHESIS_MODEL, "prompt_text": SYNTHESIS_SYSTEM_PROMPT}


# ===== OpenAI Agents SDK admin path (tools + slim run input) =====

ADMIN_AGENT_TOOL_POLICY = """\
You are assisting a feature ADMIN. You have tools for persona management and may have tools for document search and live database queries.
- Call update_persona when the admin asks to change the assistant's behavior, tone, or rules. Compose the complete replacement persona prompt yourself: start from the Current Persona shown above, apply only the requested changes while preserving its intent, structure, and effectiveness, and pass the full standalone prompt text as new_prompt (never a diff or a summary).
- Call retrieve_documents when the admin needs product/documentation/policy information not in chat history.
- Call query_database when the admin needs transactional or numeric ERP data.
- Do not invent document citations, SQL results, or persona changes; use tool output only.
- After update_persona succeeds, confirm in natural language what changed in the persona.
- Answer in the persona voice defined by the Current Persona (or the updated persona if you just changed it)."""


def build_admin_agent_instructions(persona_prompt_text: str, use_db: bool) -> str:
    """Instructions for the admin chat agent: current persona + admin tool policy."""
    parts = [
        "## Current Persona\n" + persona_prompt_text.strip(),
        ADMIN_AGENT_TOOL_POLICY.strip(),
    ]
    available = ["update_persona", "retrieve_documents"]
    if use_db:
        available.append("query_database")
    parts.append(f"Tools enabled for this turn: {', '.join(available)}.")
    return "\n\n".join(parts)
