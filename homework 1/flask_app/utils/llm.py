"""
llm.py — handles communication with OpenRouter.

This module provides:

1. A reusable Jinja2 prompt template for AI experts.
2. fill_template() for building expert prompts.
3. send_message() for sending requests to OpenRouter.
4. Orchestrator and expert routing functions for multi-expert agents.

The API key is loaded from the OPENROUTER_API_KEY environment variable.
"""

from jinja2 import Template
import os
import requests
import re


# ------------------------------------------------------------------
# OPENROUTER CONFIGURATION
# ------------------------------------------------------------------

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

DEFAULT_MODEL = "openai/gpt-4o-mini"


# ------------------------------------------------------------------
# MASTER PROMPT TEMPLATE
# ------------------------------------------------------------------

MASTER_TEMPLATE = Template(
    """
You are a {{ role }}, an expert in {{ domain }}.

{{ specific_instructions }}

{% if background_context %}
Context:
{{ background_context }}
{% endif %}

{% if few_shot_examples %}
Examples:
{{ few_shot_examples }}
{% endif %}

Request:
{{ request }}
""",
    trim_blocks=True,
    lstrip_blocks=True,
)


# ------------------------------------------------------------------
# PROMPT BUILDER
# ------------------------------------------------------------------

def fill_template(
    role,
    domain,
    specific_instructions,
    request,
    background_context="",
    few_shot_examples="",
):
    """
    Render MASTER_TEMPLATE into a complete expert prompt.
    """

    return MASTER_TEMPLATE.render(
        role=role,
        domain=domain,
        specific_instructions=specific_instructions,
        background_context=background_context,
        few_shot_examples=few_shot_examples,
        request=request,
    ).strip()


# ------------------------------------------------------------------
# API KEY
# ------------------------------------------------------------------

def get_api_key():
    """
    Return the OpenRouter API key from the environment.
    """

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        return None

    api_key = api_key.strip()

    if not api_key:
        return None

    # Ignore placeholders used in .env examples.
    if api_key.lower() in {
        "paste-your-key-here",
        "your-api-key-here",
        "your_openrouter_api_key",
    }:
        return None

    return api_key


# ------------------------------------------------------------------
# OPENROUTER REQUEST
# ------------------------------------------------------------------

def send_message(
    user_message,
    system_prompt="You are a helpful assistant.",
):
    """
    Send a message to OpenRouter and return the AI response.
    """

    # --------------------------------------------------------------
    # Validate user message
    # --------------------------------------------------------------

    if user_message is None:
        return "⚠️ Empty message."

    user_message = str(user_message).strip()

    if not user_message:
        return "⚠️ Empty message."

    # --------------------------------------------------------------
    # Get API key
    # --------------------------------------------------------------

    api_key = get_api_key()

    if not api_key:
        return (
            "⚠️ No API key found. "
            "Add your OpenRouter key to the .env file "
            "and restart the app."
        )

    # --------------------------------------------------------------
    # Headers
    # --------------------------------------------------------------

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8080",
        "X-Title": "AI Resume Agent",
    }

    # --------------------------------------------------------------
    # Messages
    # --------------------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_message,
        },
    ]

    # --------------------------------------------------------------
    # Request payload
    # --------------------------------------------------------------

    payload = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "temperature": 0.2,
    }

    # --------------------------------------------------------------
    # Send request
    # --------------------------------------------------------------

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )

    except requests.exceptions.Timeout:
        return (
            "⚠️ The request to OpenRouter timed out. "
            "Please try again."
        )

    except requests.exceptions.ConnectionError:
        return (
            "⚠️ Could not connect to OpenRouter. "
            "Check your internet connection."
        )

    except requests.exceptions.RequestException as error:
        return f"⚠️ Request error: {error}"

    # --------------------------------------------------------------
    # HTTP status check
    # --------------------------------------------------------------

    if response.status_code != 200:

        try:
            result = response.json()
        except ValueError:
            result = {}

        error_data = result.get("error", {})

        if isinstance(error_data, dict):
            error_message = error_data.get(
                "message",
                "Unknown OpenRouter error.",
            )
        else:
            error_message = str(error_data)

        return (
            f"⚠️ OpenRouter error "
            f"(HTTP {response.status_code}): "
            f"{error_message}"
        )

    # --------------------------------------------------------------
    # Parse JSON response
    # --------------------------------------------------------------

    try:
        result = response.json()

    except ValueError:
        return (
            "⚠️ OpenRouter returned an invalid JSON response."
        )

    # --------------------------------------------------------------
    # OpenRouter error object
    # --------------------------------------------------------------

    if "error" in result:

        error_data = result["error"]

        if isinstance(error_data, dict):
            error_message = error_data.get(
                "message",
                "Unknown API error.",
            )
        else:
            error_message = str(error_data)

        return f"⚠️ OpenRouter error: {error_message}"

    # --------------------------------------------------------------
    # Validate choices
    # --------------------------------------------------------------

    if "choices" not in result:
        return (
            "⚠️ Unexpected response from OpenRouter: "
            f"{result}"
        )

    choices = result.get("choices")

    if not choices:
        return (
            "⚠️ OpenRouter returned no choices."
        )

    # --------------------------------------------------------------
    # Extract assistant message
    # --------------------------------------------------------------

    first_choice = choices[0]

    if not isinstance(first_choice, dict):
        return (
            "⚠️ Unexpected OpenRouter response format."
        )

    message = first_choice.get("message")

    if not isinstance(message, dict):
        return (
            "⚠️ OpenRouter response does not contain "
            "a valid message."
        )

    content = message.get("content")

    if content is None:
        return (
            "⚠️ OpenRouter returned an empty response."
        )

    # Some models may return non-string content.
    if not isinstance(content, str):
        content = str(content)

    return content.strip()


# ------------------------------------------------------------------
# ORCHESTRATOR & EXPERT ROUTING
# ------------------------------------------------------------------

def handle_ai_chat_request(db, role, message):
    """
    Route a chat message to the named expert.
    """

    if role is None:
        return send_message(message)

    roles = db.getLLMRoles()

    if role not in roles:
        return f"Unknown expert role: {role}"

    config = roles[role]

    background_context = config["background_context"] or ""

    if role == "Content Expert":
        # Current resume data, fetched fresh for every request.
        background_context += "\n" + db.getResumeText()

    system_prompt = fill_template(
        role=config["role"],
        domain=config["domain"],
        specific_instructions=config["specific_instructions"],
        background_context=background_context,
        few_shot_examples=config["few_shot_examples"] or "",
        request=message,
    )

    output = send_message(
        message,
        system_prompt
    ).strip()

    # The rubric checks this console output.
    print(f"[{role}] generated:\n{output}\n")

    if role == "Database Read Expert":
        return execute_read_query(db, output)

    if role == "Database Write Expert":
        return execute_write_action(db, output)

    if role == "Orchestrator":
        return run_orchestrator_plan(
            db,
            message,
            output,
        )

    # Content Expert
    return output


# ------------------------------------------------------------------
# DATABASE READ EXPERT
# ------------------------------------------------------------------

def execute_read_query(db, sql):
    """
    Run the Database Read Expert's generated SQL.

    Only SELECT statements are allowed.
    """

    sql = sql.strip()

    # Remove accidental markdown code fences.
    if sql.startswith("```"):
        sql = re.sub(
            r"^```(?:sql)?\s*",
            "",
            sql,
            flags=re.IGNORECASE,
        )

        sql = re.sub(
            r"\s*```$",
            "",
            sql,
        ).strip()

    # Read Expert must be SELECT-only.
    if not sql.upper().startswith("SELECT"):
        print(
            "Database Read Expert rejected non-SELECT SQL."
        )
        return "Sorry, I couldn't safely answer that question."

    try:
        results = db.query(sql)

        print(
            f"[Database Read Expert] Query results:\n"
            f"{results}\n"
        )

        return str(results)

    except Exception as error:

        print(
            f"Read Expert query failed: {error}"
        )

        return (
            "Sorry, that question couldn't be answered."
        )


# ------------------------------------------------------------------
# DATABASE WRITE EXPERT
# ------------------------------------------------------------------

def execute_write_action(db, generated_sql):
    """
    Execute the Database Write Expert's generated SQL.

    The Database Write Expert is configured in llm_roles.csv
    to generate exactly one SQLite INSERT statement.
    """

    sql = generated_sql.strip()

    # --------------------------------------------------------------
    # Remove markdown code fences if the model adds them.
    # --------------------------------------------------------------

    if sql.startswith("```"):

        sql = re.sub(
            r"^```(?:sql)?\s*",
            "",
            sql,
            flags=re.IGNORECASE,
        )

        sql = re.sub(
            r"\s*```$",
            "",
            sql,
        ).strip()

    # --------------------------------------------------------------
    # Safety check: only INSERT is allowed.
    # --------------------------------------------------------------

    if not sql.upper().startswith("INSERT INTO"):

        print(
            "Write Expert rejected unsafe SQL:"
        )

        print(sql)

        return "Operation was unsuccessful."

    # --------------------------------------------------------------
    # Prevent multiple SQL statements.
    #
    # A single trailing semicolon is allowed.
    # --------------------------------------------------------------

    sql_without_trailing_semicolon = sql.rstrip()

    if sql_without_trailing_semicolon.endswith(";"):
        sql_without_trailing_semicolon = (
            sql_without_trailing_semicolon[:-1]
        )

    if ";" in sql_without_trailing_semicolon:

        print(
            "Write Expert rejected multiple SQL statements:"
        )

        print(sql)

        return "Operation was unsuccessful."

    # --------------------------------------------------------------
    # Execute INSERT.
    # --------------------------------------------------------------

    try:

        db.query(sql)

        print(
            "[Database Write Expert] "
            "Database write successful.\n"
        )

        return "The database was updated successfully."

    except Exception as error:

        print(
            f"Write Expert SQL execution failed: {error}"
        )

        print(
            f"SQL was:\n{sql}"
        )

        return "Operation was unsuccessful."


# ------------------------------------------------------------------
# ORCHESTRATOR
# ------------------------------------------------------------------

def run_orchestrator_plan(
    db,
    original_request,
    plan_text,
):
    """
    Parse the Orchestrator's plan, run each expert call in order,
    collect results, then synthesize one final answer.
    """

    # --------------------------------------------------------------
    # Parse plan
    # --------------------------------------------------------------

    try:

        call_strings = eval(
            plan_text,
            {"__builtins__": {}},
            {},
        )

    except Exception:

        print(
            "Orchestrator returned an "
            f"unparseable plan: {plan_text}"
        )

        return (
            "Sorry, I couldn't plan a response "
            "to that."
        )

    # Make sure the plan is a list.
    if not isinstance(call_strings, list):

        print(
            "Orchestrator plan is not a list:"
        )

        print(call_strings)

        return (
            "Sorry, I couldn't plan a response "
            "to that."
        )

    # --------------------------------------------------------------
    # Execute expert calls in order
    # --------------------------------------------------------------

    results = []

    for call_string in call_strings:

        print(
            f"[Orchestrator] executing: "
            f"{call_string}"
        )

        # Parse:
        # handle_ai_chat_request(
        #     role="Expert",
        #     message="..."
        # )
        match = re.search(
            r'role="([^"]*)",\s*message="([^"]*)"',
            call_string,
        )

        if not match:

            print(
                f"Could not parse call string: "
                f"{call_string}"
            )

            continue

        role = match.group(1)
        message = match.group(2)

        response = handle_ai_chat_request(
            db,
            role,
            message,
        )

        results.append(
            (
                role,
                message,
                response,
            )
        )

    # --------------------------------------------------------------
    # Build summary
    # --------------------------------------------------------------

    steps_summary = "\n".join(
        f"{role}: {resp}"
        for role, message, resp in results
    )

    # --------------------------------------------------------------
    # Final synthesis
    # --------------------------------------------------------------

    synthesis_prompt = (
        f'The user asked: "{original_request}"\n\n'
        f"Here is what each expert found or did:\n"
        f"{steps_summary}\n\n"
        "Write ONE short, clear reply. "
        "A Database Write Expert step's result "
        "is already the exact message to show "
        "the user. If one is present, reuse it "
        "verbatim rather than rephrasing it. "
        "Otherwise, summarize the other results "
        "in plain language. Never mention SQL, "
        "Python, code, or these internal steps."
    )

    final_answer = send_message(
        original_request,
        synthesis_prompt,
    )

    print(
        f"[Orchestrator] Final answer:\n"
        f"{final_answer}\n"
    )

    return final_answer