# Enhanced MCP ChatBot API

A powerful FastAPI-based chatbot server that integrates with the Model Context Protocol (MCP), featuring persistent conversation memory, session management, and real-time WebSocket communication.

## Features

- 🧠 **Persistent Memory**: Conversations are saved and restored across sessions
- 💬 **Session Management**: Create, switch, and manage multiple chat sessions
- 🔧 **MCP Integration**: Full support for MCP tools, prompts, and resources
- 📚 **Resource Access**: Access Gmail, project files, and company resources
- 💡 **Prompt Execution**: Execute dynamic prompts with custom arguments
- 📊 **Analytics**: Detailed session statistics and memory usage
- ⚡ **Real-time Chat**: WebSocket support for instant messaging
- 🔍 **Health Monitoring**: Comprehensive health checks and system status
- 🌐 **REST API**: Full REST API with OpenAPI documentation
- 🔄 **Auto-reload**: Development server with hot reloading

## Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd simple-oauth2
```

2. **Create virtual environment**
```bash
uv venv
```

3. **Activate virtual environment**
```bash
# On Linux/macOS
source .venv/bin/activate

# On Windows
.venv\Scripts\activate
```

4. **Install dependencies**
```bash
uv sync
```

5. **Set up configuration files**
```bash
# Copy environment variables template
cp .env.example .env

# Copy server configuration template  
cp server_config.json.example server_config.json
```

6. **Edit configuration files with your real API keys**
```bash
# Edit .env with your actual API keys and settings
# Edit server_config.json with your MCP server paths
```

> ⚠️ **SECURITY WARNING**: Never commit real API keys to git! The `.env` file is ignored by git to protect your secrets.

### Running the Server

```bash
uv run main.py
```

The server will start at `http://localhost:8000`

## API Documentation

Once the server is running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Project Structure

```
├── main.py                    # Application entry point
├── enhanced_mcp_client.py     # MCP client implementation
├── server_config.json.example # Server configuration template
├── chat_memory.pkl           # Persistent memory storage
├── src/
│   ├── api/                  # API endpoints
│   │   ├── chat.py          # Chat endpoints
│   │   ├── sessions.py      # Session management
│   │   ├── mcp.py           # MCP tools/resources/prompts
│   │   ├── system.py        # Health and memory endpoints
│   │   ├── routes.py        # Main API router
│   │   └── legacy.py        # Backward compatibility
│   ├── core/
│   │   └── config.py        # App configuration
│   ├── models/
│   │   └── schemas.py       # Pydantic models
│   ├── services/
│   │   └── chatbot_service.py # Business logic
│   └── websocket/
│       └── handler.py       # WebSocket management
└── collections/              # Postman collection
```

## API Endpoints

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | API information and status |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Interactive API documentation |

### Chat Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/chat` | Send chat message |
| `WS` | `/ws` | WebSocket connection |

### Session Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/sessions` | List all sessions |
| `POST` | `/sessions` | Create new session |
| `GET` | `/sessions/{id}` | Get session details |
| `POST` | `/sessions/{id}/switch` | Switch to session |
| `DELETE` | `/sessions/{id}` | Delete session |
| `POST` | `/sessions/{id}/clear` | Clear session messages |
| `PATCH` | `/sessions/{id}/title` | Update session title |
| `GET` | `/sessions/{id}/messages` | Get session messages |
| `GET` | `/sessions/{id}/stats` | Get session statistics |

### MCP Integration

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/tools` | List available MCP tools |
| `GET` | `/prompts` | List available MCP prompts |
| `GET` | `/resources` | List available MCP resources |
| `POST` | `/resource` | Get resource content |
| `POST` | `/prompt` | Execute MCP prompt |

### Memory & System

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/memory/stats` | Memory usage statistics |
| `POST` | `/memory/save` | Manually save memory |

## API Usage Examples

### Send a Chat Message

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Hello, how can you help me?",
    "session_id": "optional-session-id"
  }'
```

### Create a New Session

```bash
curl -X POST "http://localhost:8000/sessions" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My New Chat Session"
  }'
```

### WebSocket Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = function() {
  ws.send(JSON.stringify({
    type: 'chat',
    query: 'Hello via WebSocket!',
    session_id: 'optional-session-id'
  }));
};

ws.onmessage = function(event) {
  const response = JSON.parse(event.data);
  console.log('Bot response:', response);
};
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# MCP Server Configuration  
MCP_SERVER_COMMAND=your_mcp_server_command
MCP_SERVER_ARGS=your_server_args

# Application Settings
LOG_LEVEL=INFO
MAX_SESSIONS=50
MEMORY_FILE=chat_memory.pkl
```

### Server Configuration

1. **Copy the configuration template**:
```bash
cp server_config.json.example server_config.json
```

2. **Edit `server_config.json` for your MCP server settings**:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/your/local/path/here"
      ]
    },
    "googleWorkspaceServer": {
      "command": "uv",
      "args": [
        "run",
        "server.py"
      ],
      "cwd": "/path/to/your/google-workspace-server"
    }
  }
}
```

**Note**: `server_config.json` is not tracked in git as it contains environment-specific paths.

### Logs

View application logs:
```bash
uv run uvicorn main:app --log-level debug
```

## Performance

### Monitoring

- Monitor `/health` endpoint for system status
- Use `/memory/stats` for memory usage tracking