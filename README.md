# 🚆 GO Transit MCP Server

A Model Context Protocol (MCP) server that provides real-time GO Transit schedule and fare information for the Greater Toronto Area (GTA). This server exposes GO Transit GTFS data through MCP tools that can be used with AI assistants.

## 🚀 Features

- **Find Trips**: Get train schedules between any two GO Transit stations
- **Calculate Fares**: Get fare information between stations with zone-based pricing
- **Smart Location Matching**: Handles various station name formats (e.g., "Union", "Union Station", "Milton GO")
- **Real-time Data**: Uses official GO Transit GTFS data

## 🛠️ Installation

### Prerequisites
- Python 3.12+
- uv (recommended) or pip

### Setup
```bash
# Clone the repository
git clone https://github.com/your-username/go-transit-mcp.git
cd go-transit-mcp

# Install dependencies
uv install
# OR with pip:
# pip install -r requirements.txt
```

## 🚂 Running the MCP Server

### Local Development
```bash
# Run the server locally
python server.py
```
The server will start on `http://localhost:8000/mcp/`

### Production Deployment
```bash
# For production, bind to all interfaces
python server.py --host 0.0.0.0 --port 8000
```

## 🔧 Using with Cursor IDE

This MCP server uses **HTTP transport** (not stdio) for broader compatibility and easier deployment.

### Add to Cursor MCP Configuration

1. Open Cursor IDE
2. Go to Settings → MCP Servers
3. Add the following configuration:

```json
{
  "mcpServers": {
    "go-transit-mcp": {
      "url": "http://localhost:8000/mcp/"
    }
  } 
}
```

### For Remote Server
If running on a remote server (e.g., DigitalOcean):
```json
{
  "mcpServers": {
    "go-transit-mcp": {
      "url": "http://your-server-ip:8000/mcp/"
    }
  }
}
```

## 🧰 Available Tools

### `find_trip`
Find train schedules between stations for a specific day.

**Parameters:**
- `when`: Day of the week (Monday, Tuesday, etc.)
- `from_location`: Origin station name
- `to_location`: Destination station name

**Example:**
```json
{
  "when": "Monday",
  "from_location": "Milton",
  "to_location": "Union Station"
}
```

### `get_fare`
Calculate fare between two stations.

**Parameters:**
- `from_location`: Origin station name  
- `to_location`: Destination station name

**Example:**
```json
{
  "from_location": "Milton",
  "to_location": "Union Station"
}
```

## 🌐 Example Usage in Cursor

Once configured, you can ask your AI assistant questions like:

- "Find the last train from Milton to Union Station on Monday"
- "What's the fare from Mississauga to Toronto?"
- "Show me all trains from Oshawa to Union tomorrow morning"
- "When is the earliest train from Union to Milton?"

## 📊 Data Source

This server uses official GO Transit GTFS (General Transit Feed Specification) data, which includes:
- Train schedules and routes
- Station information and locations
- Fare zones and pricing
- Service dates and calendars

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 Related Projects

- [Streamlit GO Transit Assistant](./streamlit_go_transit.py) - Web interface for this MCP server
- [Model Context Protocol](https://modelcontextprotocol.io/) - Learn more about MCP
