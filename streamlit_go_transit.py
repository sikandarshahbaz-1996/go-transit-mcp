#!/usr/bin/env python
"""
streamlit_go_transit.py

Streamlit UI wrapper for GO Transit MCP client - Interactive MCP client that connects to a GO Transit MCP server 
and provides a chat interface with Claude through a web interface for transit queries.
"""

import streamlit as st
import asyncio
import json
import os
import sys
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
import anthropic
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz

# Set the event loop policy to WindowsProactorEventLoopPolicy at the top of the file to fix subprocess support on Windows.
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Configure Streamlit page
st.set_page_config(
    page_title="GO Transit Assistant",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="expanded"
)

load_dotenv()  # Load environment variables from .env (e.g., ANTHROPIC_KEY)

# GO Transit MCP server URL
server_url = "http://157.245.115.181:8000/mcp/"

# Check if API key is loaded
api_key = os.getenv('ANTHROPIC_KEY')
if not api_key:
    st.error("ANTHROPIC_KEY not found in environment variables!")
else:
    st.success("Anthropic API key loaded successfully")

# Instantiate Anthropic client
anthropic_client = anthropic.Anthropic(api_key=api_key)

async def load_mcp_tools(client):
    """Load tools from GO Transit MCP client and convert to Anthropic format"""
    try:
        tools = await client.list_tools()
        anthropic_tools = []
        
        for tool in tools:
            anthropic_tool = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema,
            }
            anthropic_tools.append(anthropic_tool)
        
        st.success(f"Loaded {len(anthropic_tools)} GO Transit tools from MCP server")
        return anthropic_tools
    except Exception as e:
        st.error(f"Error loading GO Transit tools: {e}")
        return []

async def call_tool(client, tool_name, arguments):
    """Call a tool on the GO Transit MCP client"""
    try:
        result = await client.call_tool(tool_name, arguments)
        
        # Handle different result types from MCP server
        if hasattr(result, 'structured_content') and result.structured_content:
            import json
            return json.dumps(result.structured_content, indent=2)
        
        elif hasattr(result, 'content') and result.content:
            # Handle content array
            all_content = []
            for content_item in result.content:
                if hasattr(content_item, 'text'):
                    all_content.append(content_item.text)
            
            # If it's a single string, return it directly
            if len(all_content) == 1:
                return all_content[0]
            else:
                # Multiple content items - combine them
                return "\n".join(all_content)
        
        elif hasattr(result, 'text'):
            # Direct text attribute
            return result.text
        
        elif isinstance(result, dict):
            # Dictionary result
            import json
            return json.dumps(result, indent=2, default=str)
        
        elif isinstance(result, str):
            # String result
            return result
        
        else:
            # Last resort fallback
            import json
            return json.dumps(result, indent=2, default=str)
            
    except Exception as e:
        st.error(f"GO Transit tool call failed: {e}")
        return f"Error: {str(e)}"

async def chat_with_claude(messages, tools):
    """Send messages to Claude and get response"""
    try:
        # Get current EST datetime for context
        eastern = pytz.timezone('America/Toronto')
        current_time = datetime.now(eastern)
        current_datetime_str = current_time.strftime("%A, %B %d, %Y at %I:%M %p %Z")
        current_day = current_time.strftime("%A")
        tomorrow_day = (current_time + timedelta(days=1)).strftime("%A")
        current_date = current_time.strftime("%Y%m%d")
        tomorrow_date = (current_time + timedelta(days=1)).strftime("%Y%m%d")
        
        # Ensure system message is always present and first
        system_prompt = f"""
            You are a professional GO Transit assistant helping customers with train schedules, fares, and route planning in the Greater Toronto Area (GTA) and surrounding regions. You have access to the GO Transit MCP server.

            ## CURRENT DATE/TIME CONTEXT:
            **Current Date/Time: {current_datetime_str}**
            **Today is: {current_day}**
            **Current Date (YYYYMMDD): {current_date}**
            **Tomorrow Date (YYYYMMDD): {tomorrow_date}**

            Use this information to interpret relative time requests:
            - "today" = {current_day} (date: {current_date})
            - "tomorrow" = {tomorrow_day} (date: {tomorrow_date})
            - "next" = find the next available departure after current time
            - "in a few hours" = consider current time is {current_time.strftime("%I:%M %p")}

            ## Core Instructions:
            - Provide accurate, helpful information about GO Transit services
            - Be friendly, professional, and transit-focused in your responses
            - Always use the available tools to get real-time schedule and fare data

            ## CRITICAL TIME INTERPRETATION RULES (MUST FOLLOW):
             **LATEST/LAST** = Last departure of the day (HIGHEST time value) - ALWAYS pick the LAST item in the list
             **EARLIEST/FIRST** = First departure of the day (LOWEST time value) - ALWAYS pick the FIRST item in the list
             **NEXT** = First available departure after current time

             IMPORTANT: When trip data is returned, it is sorted chronologically by departure time:
             - First item in array = earliest departure time (e.g., 15:40)
             - Last item in array = latest departure time (e.g., 19:10)

             **TODAY** = {current_day} (date: {current_date})
             **TOMORROW** = {tomorrow_day} (date: {tomorrow_date})
             
             IMPORTANT: If the user does not specify the day, you must choose the current day by default.
             
             FOR "LATEST" OR "LAST" QUERIES: You MUST select the final item in the array with the highest departure time.
             NEVER select the first item when asked for "latest" or "last" - this is wrong!

            ## TEMPORAL ORDERING RULES (CRITICAL FOR CONVERSATION CONTEXT):
            When users ask for "next", "after", "before", "previous", or reference previous trips:
            
            **"NEXT" or "AFTER" [time/trip]:**
            - Find the FIRST departure AFTER the specified time or previous trip's time
            - If user says "next train after 8:30", find the first train departing after 8:30
            - If user says "the one after that" (referencing a previous trip), find the next chronological departure after that trip's departure time
            
            **"BEFORE" or "PREVIOUS" [time/trip]:**
            - Find the LAST departure BEFORE the specified time or previous trip's time
            - If user says "train before 8:30", find the last train departing before 8:30
            - If user says "the one before that" (referencing a previous trip), find the previous chronological departure before that trip's departure time
            
            **CONVERSATION CONTEXT:**
            - When user references "that" or "it" (e.g., "the one after that"), look at the most recent trip mentioned in the conversation
            - Always maintain chronological order: earlier times come before later times
            - If user asks for "next train" without context, assume they mean after current time
            - NEVER return a train that departs earlier than a previously mentioned train when user asks for "next" or "after"

            ## Response Formatting:
            When presenting trip information:
            1. Highlight the specific train requested (earliest/latest/specific time)
            2. Include departure time, arrival time, and journey duration
            3. Show trip ID for reference
            4. Optionally show 2-3 alternative times for context
            5. If they ask for multiple trips, meaning they don't specify "next", "earliest", "latest", "first", "last", etc., you MUST return all trips in the array.
                - Example: "Tell me the trips from Union Station to Milton on Monday" - you MUST return all trips in the array.
            
            Example response format:
            "The **latest train** from Union Station to Milton on Monday departs at **7:10 PM** and arrives at **8:10 PM** (1 hour journey, Trip ID: 20250825-MI-2749)."

            ## Available Tools:
            - get_stations: Get the complete list of all GO Transit stations, bus stops, and transit hubs
            - find_trip: Get train schedules between locations for specific dates and times (includes real-time status)
            - get_fare: Calculate fare costs between two locations
            - get_current_datetime: Get current EST date/time for complex time calculations
            
            **IMPORTANT: For trip searches, you MUST call both get_stations() AND find_trip() in sequence. Do not stop after get_stations().**
            
            **TOOL ARGUMENT FORMATS:**
            - get_stations(): Use empty arguments {{}}
            - find_trip(): Use {{"trip": {{"date": "YYYYMMDD", "from_station": "CODE", "to_station": "CODE"}}}}
            - get_fare(): Use {{"fare_request": {{"from_station": "CODE", "to_station": "CODE"}}}}
            - get_current_datetime(): Use empty arguments {{}}

            ## WORKFLOW FOR TRIP SEARCHES:
            1. **ALWAYS call get_stations() first** to get the complete station list
            2. Parse the returned comma-separated string to find the correct station codes
            3. **IMMEDIATELY call find_trip() with those station codes** - do not wait or ask for confirmation
            4. For fare queries, also call get_stations() first to get correct station codes
            
            **CRITICAL: When a user asks for trips between locations, you MUST make BOTH tool calls in sequence:**
            - First: get_stations() 
            - Second: find_trip() with the station codes you found
            - Do not stop after get_stations() - always continue to find_trip()
            
            **EXAMPLE WORKFLOW:**
            User: "Find trips from Milton to Union"
            You MUST:
            1. Call get_stations() 
            2. Find "Milton GO - ML" and "Union Station GO - UN" in the response
            3. Call find_trip with arguments: {{"trip": {{"date": "20250902", "from_station": "ML", "to_station": "UN"}}}}
            4. Present the trip results to the user
            
            **NEVER stop after step 1 - always complete steps 2, 3, and 4!**
            
            **CRITICAL: The find_trip tool expects arguments in this exact format:**
            {{"trip": {{"date": "YYYYMMDD", "from_station": "CODE", "to_station": "CODE"}}}}

            ## CRITICAL STATION NAME RULES:
            YOU MUST ONLY USE EXACT STATION CODES FROM THE OFFICIAL LIST. When users say informal names, map them to the correct official station codes.
            
            ## STATION DATA FORMAT:
            The get_stations() function returns a simple comma-separated string in this format:
            "Station Name - StationCode, Another Station - AnotherCode"
            
            Example: "Hamilton GO Centre - 00141, Union Station GO - UN"
            
            To find a station code:
            1. Look for the station name in the comma-separated list
            2. Extract the code that comes after the dash (-)
            3. Use that exact code in your find_trip() or get_fare() calls
            
            **CRITICAL MAPPING EXAMPLES:**
            - User says "Union" or "Union Station" → Use "UN" (Union Station)
            - User says "Milton" or "Milton GO" → Use "ML" (Milton GO)
            - User says "Mississauga" or "Mississauga GO" → Use "MI" (Mississauga GO)
            - User says "Brampton" or "Brampton GO" → Use "BR" (Brampton GO)
            - User says "Oakville" or "Oakville GO" → Use "OA" (Oakville GO)
            - User says "Burlington" or "Burlington GO" → Use "BU" (Burlington GO)
            - User says "Hamilton" or "Hamilton GO" → Use "HA" (Hamilton GO Centre)
            - User says "Georgetown" or "Georgetown GO" → Use "GE" (Georgetown GO)
            - User says "Kitchener" or "Kitchener GO" → Use "KI" (Kitchener GO)
            - User says "Guelph" or "Guelph GO" → Use "GL" (Guelph Central GO)
            - User says "Oshawa" or "Oshawa GO" → Use "OS" (Durham College Oshawa GO)
            - User says "Airport" or "Pearson" → Use "PA" (Pearson Airport Terminal 1)
            - User says "McMaster" → Use "MU" (McMaster University)
            - User says "Wonderland" → Use "WW" (Major Mackenzie West Bus Terminal)
            
            **COMMON STATION CODES:**
            - UN = Union Station
            - ML = Milton GO
            - MI = Mississauga GO
            - BR = Brampton GO
            - OA = Oakville GO
            - BU = Burlington GO
            - HA = Hamilton GO Centre
            - GE = Georgetown GO
            - KI = Kitchener GO
            - GL = Guelph Central GO
            - OS = Durham College Oshawa GO
            - PA = Pearson Airport Terminal 1
            
            NEVER invent station codes - only use exact matches from the official list returned by get_stations(). When users say informal names, always map to exact official station codes.

            ## DATE FORMAT REQUIREMENTS:
            - All dates must be in YYYYMMDD format (e.g., '20250902' for September 2, 2025)
            - Use current date ({current_date}) for "today"
            - Use tomorrow date ({tomorrow_date}) for "tomorrow"
            - For specific dates, convert to YYYYMMDD format

            ## TIME FORMAT REQUIREMENTS:
            - All times must be in HHMM format (e.g., '0700' for 7:00 AM, '1430' for 2:30 PM)
            - Use 24-hour format without colons

            ## Error Handling:
            - If no trips found, suggest checking station names or trying different days
            - If connection fails, apologize and suggest trying again
            - For unclear requests, ask for clarification on origin, destination, and timing
        """
        
        # Filter out system messages and prepare for Claude API
        filtered_messages = [msg for msg in messages if msg["role"] != "system"]
        
        response = anthropic_client.messages.create(
            model='claude-3-5-haiku-20241022',
            max_tokens=4096,
            system=system_prompt,
            messages=filtered_messages,
            tools=tools,
        )
        # Return the response object directly - we'll handle content extraction in the calling code
        return response
    except Exception as e:
        st.error(f"Claude API error: {e}")
        return {"role": "assistant", "content": f"Sorry, I encountered a Claude API error: {str(e)}"}

def sync_chat_response(messages, user_input):
    """Synchronous wrapper for the async chat logic for GO Transit queries"""
    async def _chat():
        try:
            # Create transport and client
            transport = StreamableHttpTransport(server_url)
            
            async with Client(transport=transport) as client:
                # Ping the server to test connection
                await client.ping()
                
                # Load tools from server
                tools = await load_mcp_tools(client)
                
                if not tools:
                    st.warning("No GO Transit tools found. Using fallback mode.")
                    tools = [
                        {
                            "name": "get_stations",
                            "description": "Get the complete list of all GO Transit stations",
                            "input_schema": {
                                "type": "object",
                                "properties": {},
                                "required": []
                            }
                        },
                        {
                            "name": "find_trip",
                            "description": "Find GO Transit trips between locations with real-time status",
                            "input_schema": {
                                "type": "object",
                                "properties": {
                                    "trip": {
                                        "type": "object",
                                        "properties": {
                                            "date": {
                                                "type": "string",
                                                "description": "Date in YYYYMMDD format"
                                            },
                                            "from_station": {
                                                "type": "string",
                                                "description": "Origin station code"
                                            },
                                            "to_station": {
                                                "type": "string",
                                                "description": "Destination station code"
                                            },
                                            "time": {
                                                "type": "string",
                                                "description": "Time in HHMM format"
                                            },
                                            "max_results": {
                                                "type": "string",
                                                "description": "Maximum number of results"
                                            }
                                        },
                                        "required": ["date", "from_station", "to_station"]
                                    }
                                },
                                "required": ["trip"]
                            }
                        },
                        {
                            "name": "get_fare",
                            "description": "Get fare information between two GO Transit locations",
                            "input_schema": {
                                "type": "object",
                                "properties": {
                                    "fare_request": {
                                        "type": "object",
                                        "properties": {
                                            "from_station": {
                                                "type": "string",
                                                "description": "Origin station code"
                                            },
                                            "to_station": {
                                                "type": "string",
                                                "description": "Destination station code"
                                            }
                                        },
                                        "required": ["from_station", "to_station"]
                                    }
                                },
                                "required": ["fare_request"]
                            }
                        },
                        {
                            "name": "get_current_datetime",
                            "description": "Get current date and time in Eastern Time",
                            "input_schema": {
                                "type": "object",
                                "properties": {},
                                "required": []
                            }
                        }
                    ]
                
                # Add user message
                messages.append({"role": "user", "content": user_input})
                
                # Get response from Claude
                response = await chat_with_claude(messages, tools)
                
                # Extract text content from response and add to messages
                text_content = ""
                for content_item in response.content:
                    if hasattr(content_item, 'type') and content_item.type == 'text':
                        text_content += content_item.text
                
                # Add assistant response to messages
                messages.append({"role": "assistant", "content": text_content})
                
                # Handle tool calls with support for multiple sequential calls
                tool_uses = []
                for content_item in response.content:
                    if hasattr(content_item, 'type') and content_item.type == 'tool_use':
                        tool_uses.append(content_item)
                
                if tool_uses:
                    # Process all tool calls in sequence
                    for tool_use in tool_uses:
                        # Call the tool on the GO Transit MCP server
                        arguments = tool_use.input
                        st.info(f"Calling {tool_use.name} with arguments: {arguments}")
                        
                        tool_result = await call_tool(client, tool_use.name, arguments)
                        
                        # Add tool response to messages
                        messages.append({
                            "role": "user",
                            "content": f"Tool result for {tool_use.name}: {tool_result}"
                        })
                    
                    # After all tool calls are complete, get the final response from Claude
                    # This allows Claude to process all tool results and make additional tool calls if needed
                    final_response = await chat_with_claude(messages, tools)
                    
                    # Extract text content and add to messages
                    final_text_content = ""
                    for content_item in final_response.content:
                        if hasattr(content_item, 'type') and content_item.type == 'text':
                            final_text_content += content_item.text
                    
                    messages.append({"role": "assistant", "content": final_text_content})
                    
                    # Check if the final response also has tool calls (for multi-step workflows)
                    final_tool_uses = []
                    for content_item in final_response.content:
                        if hasattr(content_item, 'type') and content_item.type == 'tool_use':
                            final_tool_uses.append(content_item)
                    
                    while final_tool_uses:
                        st.info("Processing additional tool calls...")
                        
                        # Process the additional tool calls
                        for tool_use in final_tool_uses:
                            arguments = tool_use.input
                            st.info(f"Calling {tool_use.name} with arguments: {arguments}")
                            
                            tool_result = await call_tool(client, tool_use.name, arguments)
                            
                            # Add tool response to messages
                            messages.append({
                                "role": "user",
                                "content": f"Tool result for {tool_use.name}: {tool_result}"
                            })
                        
                        # Get the next response from Claude
                        final_response = await chat_with_claude(messages, tools)
                        
                        # Extract text content and add to messages
                        final_text_content = ""
                        for content_item in final_response.content:
                            if hasattr(content_item, 'type') and content_item.type == 'text':
                                final_text_content += content_item.text
                        
                        messages.append({"role": "assistant", "content": final_text_content})
                        
                        # Check for more tool uses
                        final_tool_uses = []
                        for content_item in final_response.content:
                            if hasattr(content_item, 'type') and content_item.type == 'tool_use':
                                final_tool_uses.append(content_item)
                    
                    # Extract text content from final response
                    text_content = ""
                    for content_item in final_response.content:
                        if hasattr(content_item, 'type') and content_item.type == 'text':
                            text_content += content_item.text
                    
                    return text_content, messages
                else:
                    # Extract text content from response
                    text_content = ""
                    for content_item in response.content:
                        if hasattr(content_item, 'type') and content_item.type == 'text':
                            text_content += content_item.text
                    
                    return text_content, messages
        
        except Exception as e:
            st.error(f"Failed to connect to GO Transit MCP server: {e}")
            st.warning("Using fallback mode...")
            
            # Fallback mode - basic transit info
            tools = [
                {
                    "name": "basic_transit_info",
                    "description": "Provide basic GO Transit information",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Transit query"
                            }
                        },
                        "required": ["query"]
                    }
                }
            ]
            
            messages.append({"role": "user", "content": user_input})
            response = await chat_with_claude(messages, tools)
            
            # Extract text content and add to messages
            text_content = ""
            for content_item in response.content:
                if hasattr(content_item, 'type') and content_item.type == 'text':
                    text_content += content_item.text
            
            messages.append({"role": "assistant", "content": text_content})
            
            # Check for tool uses in fallback mode
            fallback_tool_uses = []
            for content_item in response.content:
                if hasattr(content_item, 'type') and content_item.type == 'tool_use':
                    fallback_tool_uses.append(content_item)
            
            if fallback_tool_uses:
                # Process all tool calls in sequence (fallback mode)
                for tool_use in fallback_tool_uses:
                    arguments = tool_use.input
                    tool_result = f"I'm unable to connect to the GO Transit server right now. Please try asking about train schedules, fares, or routes and I'll do my best to help! (Query: {arguments['query']})"
                    
                    messages.append({
                        "role": "user",
                        "content": f"Tool result for {tool_use.name}: {tool_result}"
                    })
                
                # Get final response and check for additional tool calls
                final_response = await chat_with_claude(messages, tools)
                
                # Extract text content and add to messages
                final_text_content = ""
                for content_item in final_response.content:
                    if hasattr(content_item, 'type') and content_item.type == 'text':
                        final_text_content += content_item.text
                
                messages.append({"role": "assistant", "content": final_text_content})
                
                # Handle additional tool calls in fallback mode
                final_fallback_tool_uses = []
                for content_item in final_response.content:
                    if hasattr(content_item, 'type') and content_item.type == 'tool_use':
                        final_fallback_tool_uses.append(content_item)
                
                while final_fallback_tool_uses:
                    st.info("Processing additional tool calls in fallback mode...")
                    
                    for tool_use in final_fallback_tool_uses:
                        arguments = tool_use.input
                        tool_result = f"I'm unable to connect to the GO Transit server right now. Please try asking about train schedules, fares, or routes and I'll do my best to help! (Query: {arguments['query']})"
                        
                        messages.append({
                            "role": "user",
                            "content": f"Tool result for {tool_use.name}: {tool_result}"
                        })
                    
                    final_response = await chat_with_claude(messages, tools)
                    
                    # Extract text content and add to messages
                    final_text_content = ""
                    for content_item in final_response.content:
                        if hasattr(content_item, 'type') and content_item.type == 'text':
                            final_text_content += content_item.text
                    
                    messages.append({"role": "assistant", "content": final_text_content})
                    
                    # Check for more tool uses
                    final_fallback_tool_uses = []
                    for content_item in final_response.content:
                        if hasattr(content_item, 'type') and content_item.type == 'tool_use':
                            final_fallback_tool_uses.append(content_item)
                
                # Extract text content from final response in fallback mode
                text_content = ""
                for content_item in final_response.content:
                    if hasattr(content_item, 'type') and content_item.type == 'text':
                        text_content += content_item.text
                
                return text_content, messages
            else:
                # Extract text content from response in fallback mode
                text_content = ""
                for content_item in response.content:
                    if hasattr(content_item, 'type') and content_item.type == 'text':
                        text_content += content_item.text
                
                return text_content, messages
    
    return asyncio.run(_chat())

def main():
    st.title("🚆 GO Transit Assistant")
    st.markdown("Interactive chat interface for GO Transit schedules, fares, and route information")
    
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "history" not in st.session_state:
        st.session_state["history"] = []
    if "reset_counter" not in st.session_state:
        st.session_state["reset_counter"] = 0
    if "input_submitted" not in st.session_state:
        st.session_state["input_submitted"] = False
    
    # Connection status and quick actions
    with st.sidebar:
        st.header("🚆 GO Transit Info")
        st.info(f"Server: {server_url}")
        st.success("GO Transit MCP Client Ready! (Claude 3.5 Haiku)")
        
        st.markdown("---")
        st.header("Quick Examples")
        st.markdown("""
        Try asking:
        - "Find trains from Milton to Union Station"
        - "What's the fare from Mississauga to Toronto?"
        - "Show me the earliest train from Oshawa to Union"
        - "What are the weekend schedules?"
        - "Get me the latest train from Brampton to Union"
        """)
        
        st.markdown("---")
        st.header("Available Stations")
        st.markdown("""
        Popular station codes:
        - UN = Union Station
        - ML = Milton GO
        - MI = Mississauga GO
        - BR = Brampton GO
        - OA = Oakville GO
        - BU = Burlington GO
        - HA = Hamilton GO Centre
        - GE = Georgetown GO
        - KI = Kitchener GO
        - GL = Guelph Central GO
        - OS = Durham College Oshawa GO
        - PA = Pearson Airport Terminal 1
        """)
        
        st.markdown("---")
        st.header("New Features")
        st.markdown("""
        ✨ **Real-time Status**: Get live updates on delays and cancellations
        🚆 **Enhanced Trip Info**: More detailed journey information
        💰 **Fare Calculator**: Get accurate fare information
        📍 **Station Lookup**: Complete station directory
        ⏰ **Current Time**: Always up-to-date time context
        """)
    
    # Display chat history
    st.header("Chat History")
    if not st.session_state["history"]:
        st.info("No messages yet. Ask me about GO Transit schedules, fares, or routes!")
    else:
        for i, (user, bot) in enumerate(st.session_state["history"]):
            with st.container():
                col1, col2 = st.columns([1, 4])
                with col1:
                    st.markdown("**You:**")
                with col2:
                    st.markdown(user)
                
                col1, col2 = st.columns([1, 4])
                with col1:
                    st.markdown("**🚆 Assistant:**")
                with col2:
                    st.markdown(bot)
                
                if i < len(st.session_state["history"]) - 1:
                    st.divider()
    
    # Chat interface - moved below chat history
    st.markdown("---")
    st.header("Ask about your GO Transit trip")
    
    # Input field and buttons on same line
    user_input = st.text_input("", 
                              key=f"user_input_{st.session_state['reset_counter']}", 
                              placeholder="e.g., 'Find trains from Milton to Union Station tomorrow morning'")
    
    # Buttons on same line
    col1, col2 = st.columns([1, 1])
    with col1:
        send_button = st.button("Send")
    with col2:
        reset = st.button("Reset Chat")
    
    if reset:
        st.session_state["messages"] = []
        st.session_state["history"] = []
        st.session_state["reset_counter"] += 1  # Change the key to force input reset
        st.rerun()
    
    if send_button and user_input:
        with st.spinner("Connecting to GO Transit server and searching..."):
            try:
                response, updated_messages = sync_chat_response(st.session_state["messages"], user_input)
                st.session_state["messages"] = updated_messages  # Persist conversation context
                st.session_state["history"].append((user_input, response))
                st.session_state["reset_counter"] += 1  # Force input field to reset
                st.rerun()
            except Exception as e:
                st.error("An error occurred:")
                st.error(str(e))

def run_streamlit():
    main()

if __name__ == "__main__":
    run_streamlit()
