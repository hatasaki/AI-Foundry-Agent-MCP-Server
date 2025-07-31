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
| `AZURE_AI_ENDPOINT` | HTTPS endpoint of the target AI Foundry (e.g. `https://<your-resource>.services.ai.azure.com/api/projects/<your-project>`) |
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
python server.py  # listens on http://localhost:3000/mcp
```

## Running on Azure Container Apps
A `Dockerfile` is included, and a GitHub Actions workflow automatically builds and publishes the container image to
**GitHub Container Registry (GHCR)** as `ghcr.io/hatasaki/ai-foundry-agent-mcp-server:latest`. You can deploy this pre-built image straight to
Azure Container Apps—no local `docker build` / `docker push` required.

```bash
# 0) Sign in and select the correct subscription
az login
az account set --subscription <SUBSCRIPTION_ID>

# 1) Deploy the latest image published to GHCR
az containerapp up \
  --name foundry-mcp-server \
  --resource-group <RESOURCE_GROUP> \
  --environment <CONTAINER_APPS_ENV> \
  --image ghcr.io/hatasaki/ai-foundry-agent-mcp-server:latest \
  --target-port 3000 \
  --ingress external \
  --secrets API_KEY=$API_KEY \
  --env-vars AZURE_AI_ENDPOINT=$AZURE_AI_ENDPOINT \
             AZURE_AI_AGENT_ID=$AZURE_AI_AGENT_ID \
             API_KEY=secretref:API_KEY \
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
  --scope $(az resource show --name <AI_Foundry_Name> --resource-group <FOUNDRY_RESOURCE_GROUP> --resource-type Microsoft.CognitiveServices/accounts --query id --output tsv)

# 3) Verify and check your container app's ingress url
az containerapp show --name foundry-mcp-server --resource-group <RESOURCE_GROUP> -o table

# 4) Add MCP Clinet (Such as VSCode, MCP Client for Azure) to connect
VSCode mcp.json sample:
{
  "servers": {
    "Foundry MCP server": {
      "type": "http",
      "url": "https://foundry-mcp-server.xxx.<region>.azurecontainerapps.io/mcp",
      "headers": {
        "x-api-key": "<your api key>"
      }
    }
  }
}
```

## Disclaimer
This software is provided **as-is** for testing, evaluation and demonstration purposes **only**. It is **not** production-ready and comes with **no warranty** of any kind. Use it at your own risk. The project is **not** officially endorsed by Microsoft.

## Contributing
This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.