# AI-Foundry-Agent-MCP-Server

## Overview
This repository provides a lightweight MCP (Model Context Protocol) server that exposes an Azure AI Foundry Agent as an MCP **tool**.  
Once deployed, any MCP-compatible client can invoke the registered Foundry Agent as streamable HTTP MCP server.

## Features
* Minimal, self-contained Python implementation (single `server.py`).  
* Stateless REST API that forwards requests to an Azure AI Foundry Agent.  
* No external dependencies apart from the official Azure AI Foundry Python SDK.

## MCP tool information
The MCP **tool name** and **description** are derived directly from the corresponding **Azure AI Foundry Agent** metadata.  
Please make sure your agent’s *name* and *description* are meaningful, as clients will rely on them to discover and invoke the tool correctly.

The exposed tool looks like this:
```json
{
    "name": "<agent name>",          // Spaces are replaced with underscores
    "description": "<agent description>",
    "inputSchema": {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {
                "type": "string",
                "description": "query for the tool",
            }
        }
    }
}
```

## Prerequisites
1. **Python 3.9+** (pre-installed in the dev-container)  
2. **Access to an Azure AI Foundry Agent**  
   * Foundry **Endpoint URL**  
   * Foundry **Agent ID**  
   * **API Key** for authenticating inbound requests (any opaque string you manage)

## Configuration
The server is configured entirely through environment variables:

| Variable | Description |
|----------|-------------|
| `AZURE_AI_ENDPOINT` | HTTPS endpoint of the target AI Foundry workspace (e.g. `https://<your-resource>.services.ai.azure.com/api/projects/<your-project>`) |
| `AZURE_AI_AGENT_ID` | Identifier of the agent you wish to expose |
| `API_KEY` | Value that clients must send in the `x-api-key` HTTP header |
| `PORT` *(optional)* | TCP port to bind to (default `3000`) |

Export these variables locally or pass them via `docker run ‑e` when containerising.

## Quick Start (local)
```bash
# 0 ) Login valid Azure account to access Azure AI Foundry
az login

# 1 ) Clone & install runtime dependencies
pip install -r requirements.txt

# 2 ) Configure environment (replace with your real values)
export AZURE_AI_ENDPOINT="https://xxx.services.ai.azure.com/api/projects/yyy"
export AZURE_AI_AGENT_ID="agent-123456"
export API_KEY="replace-me"

# 3 ) Launch the service
python server.py  # listens on http://localhost:3000
```

## Running on Azure Container Apps
A `Dockerfile` is included, but you don’t need to invoke `docker build` / `docker push` yourself—`az containerapp up` can build, push, and deploy in one step.

```bash
# 0) Sign in and select the correct subscription
az login
az account set --subscription <SUBSCRIPTION_ID>

# 1) Build, push, and deploy the Container App in a single command
az containerapp up \
  --name foundry-mcp-server \
  --resource-group <RESOURCE_GROUP> \
  --environment <CONTAINER_APPS_ENV> \
  --source . \                       # Builds using the local Dockerfile and pushes to a generated or existing ACR
  --target-port 3000 \
  --ingress external \
  --env-vars AZURE_AI_ENDPOINT=$AZURE_AI_ENDPOINT \
             AZURE_AI_AGENT_ID=$AZURE_AI_AGENT_ID \
             API_KEY=$API_KEY \
             PORT=3000 \
  --system-assigned                   # Enable a system-assigned managed identity

# 2) Grant the managed identity access to Azure AI Foundry (one-time)
PRINCIPAL_ID=$(az containerapp show \
  --name foundry-mcp-server \
  --resource-group <RESOURCE_GROUP> \
  --query "identity.principalId" -o tsv)

az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Azure AI User" \
  --scope "/subscriptions/<SUBSCRIPTION_ID>/resourceGroups/<FOUNDRY_RG>/providers/Microsoft.AIFoundry/accounts/<ACCOUNT_NAME>/projects/<PROJECT_NAME>"

# 3) Verify
az containerapp show --name foundry-mcp-server --resource-group <RESOURCE_GROUP> -o table
```

## Disclaimer
This software is provided **as-is** for testing, evaluation and demonstration purposes **only**. It is **not** production-ready and comes with **no warranty** of any kind. Use it at your own risk. The project is **not** officially endorsed by Microsoft.

## Contributing
This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.