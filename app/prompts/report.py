"""Prompt templates for the report tool."""

REPORT_SYSTEM_PROMPT = "You are a helpful assistant."

REPORT_PROMPT_TEMPLATE = """INSTRUCTION TO MODEL:

— If the user's message is a greeting ONLY (e.g., "hello", "hi", "hey", "salaam", "greetings") and contains NOTHING ELSE, then respond with a short, warm greeting like "Hello!" and STOP. Do not continue or process any further logic.

— If the user's message contains ANYTHING other than just a greeting (e.g., requests, questions, instructions), IGNORE the greeting and DO NOT respond to it. Proceed ONLY with the instructions below to generate the report.

--- BEGIN REPORT GENERATION LOGIC ---

Please generate a detailed report based on the following information.
Try to fill this structure if the information needed is provided in user's narrative. Otherwise, just write a professional and structured report without this template.
Skip any part the narrative does not cover. Do not force this template.
Here is the main information:
{info}

**Information**
* Put information given above as bullet points here.
* Each bullet point should have a field name and value.
* Do not make up any information. Use only what is provided.

**Overview:**
* Provide a concise summary of the testing activity, including key timestamps and any notable preliminary events or issues encountered before the main testing.
* Format this as a professional paragraph that flows naturally.

**Results:**
* Record all quantitative measurements.
* Note qualitative observations.
* Document any deviations from expected behavior.

**Conclusion:**
Summarize the overall testing outcome, system performance, and whether all objectives were met. Include any notable observations about the system's reliability and functionality.

**Signatures:**
Technician: ________________________
Supervisor: ________________________
Date: ________________________

Write the report using user's narrative below:
User Narrative: {narrative}
Report:
"""


def get_generate_report_prompt(info: dict, narrative: str) -> str:
    """Build the report user prompt from legacy template."""
    return REPORT_PROMPT_TEMPLATE.format(info=str(info), narrative=narrative)
