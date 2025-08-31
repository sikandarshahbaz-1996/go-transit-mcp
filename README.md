# 🚆 GO Transit MCP Server

A Model Context Protocol (MCP) server that provides real-time GO Transit schedule and fare information for the Greater Toronto Area (GTA). This server exposes GO Transit GTFS data through MCP tools that can be used with AI assistants.

## 🚀 Features

- **Find Trips**: Get train schedules between any two GO Transit stations with real-time status
- **Calculate Fares**: Get fare information between stations with zone-based pricing
- **Smart Location Matching**: Handles various station name formats (e.g., "Union", "Union Station", "Milton GO")
- **Real-time Data**: Uses official GO Transit GTFS data including delays, cancellations, and service alerts
- **Multiple Transport Options**: Supports both stdio and HTTP transport for maximum compatibility

## 🛠️ Installation

### Prerequisites
- Python 3.12+
- uv (recommended) or pip
- METROLINX_API_KEY (for GO Transit data access)

### Setup
```bash
# Clone the repository
git clone https://github.com/your-username/go-transit-mcp.git
cd go-transit-mcp

# Install dependencies
uv install
# OR with pip:
# pip install -r requirements.txt

# Set up environment variables
echo "METROLINX_API_KEY=your_api_key_here" > .env
```

## 🚂 Running the MCP Server

### Option 1: HTTP Transport (Recommended)
```bash
# Run the HTTP server locally
python serverHTTP.py
```
The server will start on `http://localhost:8000/mcp/`

### Option 2: stdio Transport
```bash
# Run the stdio server
python server.py
```

### Production Deployment
```bash
# For production, bind to all interfaces
python serverHTTP.py --host 0.0.0.0 --port 8000
```

## 🔧 Using with AI Assistants

### Claude Desktop

1. Clone this repository to your local machine
2. Add the following configuration to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "go-transit": {
      "command": "python3",
      "args": [
        "path-to/go-transit-mcp/server.py"
      ],
      "env": {
        "METROLINX_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

**Note**: Replace `path-to/go-transit-mcp/server.py` with the actual path to your cloned repository.

### Cursor IDE

This MCP server supports **HTTP transport** for broader compatibility and easier deployment.

#### Add to Cursor MCP Configuration

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

#### For Remote Server
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

### `get_stations`
Get the complete list of all GO Transit stations, bus stops, and transit hubs.

**Parameters:** None

**Returns:** Comma-separated string of stations in format "Station Name - StationCode"

### `find_trip`
Find train schedules between stations for a specific day with real-time status information.

**Parameters:**
- `date`: Date in YYYYMMDD format (e.g., '20250902')
- `from_station`: Origin station code (e.g., 'ML' for Milton)
- `to_station`: Destination station code (e.g., 'UN' for Union Station)
- `time`: Time in HHMM format (e.g., '0700' for 7:00 AM)
- `max_results`: Maximum number of results to return

**Real-time Features:**
- Automatic delay detection and reporting
- Cancellation notifications
- Service alert integration
- Real-time departure/arrival updates

### `get_fare`
Calculate fare between two stations.

**Parameters:**
- `from_station`: Origin station code
- `to_station`: Destination station code

### `get_current_datetime`
Get current date and time in Eastern Time.

**Parameters:** None

## 🌐 Example Usage

Once configured, you can ask your AI assistant questions like:

- "Find the last train from Milton to Union Station on Monday"
- "What's the fare from Mississauga to Toronto?"
- "Show me all trains from Oshawa to Union tomorrow morning"
- "When is the earliest train from Union to Milton?"
- "Is my train delayed?"

## 📊 Data Source

This server uses official GO Transit GTFS (General Transit Feed Specification) data, which includes:
- Train schedules and routes
- Station information and locations
- Fare zones and pricing
- Service dates and calendars
- Real-time trip updates and service alerts

## 🌐 Web Interface

A Streamlit web interface is also available for easy access:

```bash
# Start the web interface
streamlit run streamlit_go_transit.py --server.port 8501 --server.address 0.0.0.0
```

Access the web interface at `http://localhost:8501`

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 Related Projects

- [Model Context Protocol](https://modelcontextprotocol.io/) - Learn more about MCP
