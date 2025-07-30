import contextlib
import logging
import os
import re
from collections.abc import AsyncIterator
from typing import Dict, List

from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
import mcp.types as types

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount
from starlette.types import Receive, Scope, Send

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import ListSortOrder

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Suppress verbose Azure SDK HTTP logs
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Cached Azure AI client instances (simple singleton pattern)
# ---------------------------------------------------------------------------

_project: AIProjectClient | None = None
_agent = None  # type: ignore[assignment]

test=os.environ.get("AZURE_AI_ENDPOINT")

def _get_project() -> AIProjectClient:
    """Return a singleton AIProjectClient instance."""
    global _project
    if _project is None:
        _project = AIProjectClient(
            credential=DefaultAzureCredential(),
            endpoint=os.environ.get("AZURE_AI_ENDPOINT"),
        )
    return _project


def _get_agent():
    """Return a singleton Azure AI Foundry Agent instance."""
    global _agent
    if _agent is None:
        project = _get_project()
        agent_id = os.environ.get("AZURE_AI_AGENT_ID")
        if not agent_id:
            raise EnvironmentError("AZURE_AI_AGENT_ID environment variable is not set.")
        _agent = project.agents.get_agent(agent_id)
    return _agent


# ---------------------------------------------------------------------------
# External helper functions
# ---------------------------------------------------------------------------

async def call_agent(query: str) -> str:
    """Call Azure AI Agent to search the Web."""

    project = _get_project()

    agent = project.agents.get_agent(os.environ.get("AZURE_AI_AGENT_ID"))

    thread = project.agents.threads.create()
    project.agents.messages.create(thread_id=thread.id, role="user", content=query)

    run = project.agents.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)

    if run.status == "failed":
        return f"Run failed: {run.last_error}"

    messages = project.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)

    response_text = ""
    for message in messages:
        if message.text_messages:
            logger.info("%s: %s", message.role, message.text_messages[-1].text.value)
            response_text += f"{message.role}: {message.text_messages[-1].text.value}\n"
    if not response_text:
        response_text = "No text messages found in the response."
    return response_text


def get_agent_name() -> str:
    """Return the Azure AI Foundry Agent name via SDK."""
    return _get_agent().name  # type: ignore[attr-defined]


def get_agent_description() -> str:
    """Return the Azure AI Foundry Agent description via SDK."""
    # Some agent objects may not have a description attribute; fall back gracefully
    return getattr(_get_agent(), "description", "Azure AI Foundry Agent")

def sanitize_name(name: str) -> str:
    """Return a sanitized version of the name suitable for tool identifiers.

    Spaces are converted to underscores and any non-word characters (anything
    other than letters, digits or an underscore) are stripped out.
    """
    # Replace one or more whitespace characters with a single underscore
    name = re.sub(r"\s+", "_", name)
    # Remove any character that is not a letter, digit or underscore
    name = re.sub(r"[^\w_]", "", name)
    return name

# ---------------------------------------------------------------------------
# Build MCP server definition
# ---------------------------------------------------------------------------

mcp_app = Server(f"{sanitize_name(get_agent_name())}_Agent_MCP_server")

@mcp_app.list_tools()
async def list_tools() -> List[types.Tool]:
    """Return the tool manifest."""
    tool_name = sanitize_name(get_agent_name())
    tool_description = get_agent_description()
    logger.info("Listing tool: %s - %s", tool_name, tool_description)
    return [
        types.Tool(
            name=tool_name,
            description=tool_description,
            inputSchema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "query for the tool",
                    }
                },
            },
        ),
    ]


@mcp_app.call_tool()
async def call_tool(name: str, arguments: Dict) -> List[types.Content]:
    """Route tool calls to implementations."""

    if name == f"{sanitize_name(get_agent_name())}":
        query = arguments.get("query")
        logger.info("Tool called: %s with query: %s", name, query)
        if not query:
            raise ValueError("Missing required argument 'query'")
        return [types.TextContent(type="text", text=await call_agent(query))]

    logger.warning("Unknown tool called: %s", name)
    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# StreamableHTTP session manager (stateless)
# ---------------------------------------------------------------------------

# Create the session manager with stateless mode
session_manager = StreamableHTTPSessionManager(
    app=mcp_app,
    event_store=None,
    json_response=False,  # SSE streaming
    stateless=True,
)


async def handle_streamable_http(scope: Scope, receive: Receive, send: Send) -> None:
    """ASGI handler that verifies API key then delegates to session manager."""

    # Verify API key from headers
    if scope["type"] == "http":
        headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}
        api_key = headers.get("x-api-key")
        if api_key != os.environ.get("API_KEY", "ai-foundry-agent-mcp-server-strong-key"):
            response = JSONResponse(
                {"detail": "Unauthorized: invalid or missing key header"},
                status_code=401,
            )
            await response(scope, receive, send)
            return

    # Delegate request handling to session manager
    await session_manager.handle_request(scope, receive, send)


@contextlib.asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    """Start and shut down the session manager."""

    async with session_manager.run():
        logger.info("Application started with StreamableHTTP session manager!")
        try:
            yield
        finally:
            logger.info("Application shutting down...")


# Build the final Starlette ASGI app
starlette_app = Starlette(
    debug=True,
    routes=[Mount("/mcp", handle_streamable_http)],
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware to accept '/mcp' (no trailing slash) without redirect
# ---------------------------------------------------------------------------

class _MCPRootMiddleware:
    # Rewrite a request to '/mcp' so that it behaves as '/mcp/'

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope.get("type") == "http" and scope.get("path") == "/mcp":
            scope = dict(scope)
            scope["path"] = "/mcp/"
        await self.app(scope, receive, send)


# Wrap the Starlette app with the middleware
asgi_app = _MCPRootMiddleware(starlette_app)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    # Allow overriding the listening port via the PORT environment variable
    port = int(os.environ.get("PORT", "3000"))
    uvicorn.run(asgi_app, host="0.0.0.0", port=port)