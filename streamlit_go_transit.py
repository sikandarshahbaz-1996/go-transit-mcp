#!/usr/bin/env python
"""
streamlit_go_transit.py

Streamlit UI wrapper for GO Transit MCP client - Interactive MCP client that connects to a GO Transit MCP server 
and provides a chat interface with OpenAI through a web interface for transit queries.
"""

import streamlit as st
import asyncio
import json
import os
import sys
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from openai import OpenAI
from dotenv import load_dotenv

# Set the event loop policy to WindowsProactorEventLoopPolicy at the top of the file to fix subprocess support on Windows.
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

load_dotenv()  # Load environment variables from .env (e.g., OPENAI_API_KEY)

# GO Transit MCP server URL
server_url = "http://157.245.115.181:8000/mcp/"

# Instantiate OpenAI client
openai_client = OpenAI()

async def load_mcp_tools(client):
    """Load tools from GO Transit MCP client and convert to OpenAI format"""
    try:
        tools = await client.list_tools()
        openai_tools = []
        
        for tool in tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                }
            }
            openai_tools.append(openai_tool)
        
        st.success(f"Loaded {len(openai_tools)} GO Transit tools from MCP server")
        return openai_tools
    except Exception as e:
        st.error(f"Error loading GO Transit tools: {e}")
        return []

async def call_tool(client, tool_name, arguments):
    """Call a tool on the GO Transit MCP client"""
    try:
        result = await client.call_tool(tool_name, arguments)
        
        # Use structured_content which has the proper JSON format
        if hasattr(result, 'structured_content') and result.structured_content:
            import json
            return json.dumps(result.structured_content, indent=2)
        
        # Fallback: combine all content items if no structured_content
        elif hasattr(result, 'content') and result.content:
            # Combine all content items into a single JSON array
            all_trips = []
            for content_item in result.content:
                if hasattr(content_item, 'text'):
                    try:
                        import json
                        trip_data = json.loads(content_item.text)
                        all_trips.append(trip_data)
                    except:
                        # If not JSON, skip this item
                        continue
            
            # Return as properly formatted JSON
            import json
            return json.dumps({"result": all_trips}, indent=2)
        
        else:
            # Last resort fallback
            import json
            return json.dumps(result, indent=2, default=str)
            
    except Exception as e:
        st.error(f"GO Transit tool call failed: {e}")
        return f"Error: {str(e)}"

async def chat_with_openai(messages, tools):
    """Send messages to OpenAI and get response"""
    try:
        # Ensure system message is always present and first
        system_prompt = """
            You are a professional GO Transit assistant helping customers with train schedules, fares, and route planning in the Greater Toronto Area (GTA) and surrounding regions. You have access to the GO Transit MCP server.

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
             
             FOR "LATEST" OR "LAST" QUERIES: You MUST select the final item in the array with the highest departure time.
             NEVER select the first item when asked for "latest" or "last" - this is wrong!

            ## Response Formatting:
            When presenting trip information:
            1. Highlight the specific train requested (earliest/latest/specific time)
            2. Include departure time, arrival time, and journey duration
            3. Show trip ID for reference
            4. Optionally show 2-3 alternative times for context

            Example response format:
            "The **latest train** from Union Station to Milton on Monday departs at **7:10 PM** and arrives at **8:10 PM** (1 hour journey, Trip ID: 20250825-MI-2749)."

            ## Available Tools:
            - find_trip: Get train schedules between locations for specific days
            - get_fare: Calculate fare costs between two locations

            ## Location Handling:
            - Accept common variations (e.g., "Union", "Union Station", "Milton GO", "Milton")
            - The system handles fuzzy location matching automatically
            - Popular stations include: Union Station, Milton GO, Mississauga GO, Brampton GO, Oshawa GO, Oakville GO

            ## Days of Week:
            - Accept: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday
            - Also accept: weekday, weekend, today, tomorrow

            ## Error Handling:
            - If no trips found, suggest checking station names or trying different days
            - If connection fails, apologize and suggest trying again
            - For unclear requests, ask for clarification on origin, destination, and timing
        """
        
        if not messages or messages[0]["role"] != "system":
            system_message = {"role": "system", "content": system_prompt}
            messages.insert(0, system_message)
        
        response = openai_client.chat.completions.create(
            model='gpt-4o',
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        return response.choices[0].message
    except Exception as e:
        st.error(f"OpenAI API error: {e}")
        return {"role": "assistant", "content": f"Sorry, I encountered an error: {str(e)}"}

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
                            "type": "function",
                            "function": {
                                "name": "find_trip",
                                "description": "Find GO Transit trips between locations",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "from_location": {
                                            "type": "string",
                                            "description": "The origin location"
                                        },
                                        "to_location": {
                                            "type": "string",
                                            "description": "The destination location"
                                        },
                                        "when": {
                                            "type": "string",
                                            "description": "Day of the week"
                                        }
                                    },
                                    "required": ["from_location", "to_location", "when"]
                                }
                            }
                        }
                    ]
                
                # Add user message
                messages.append({"role": "user", "content": user_input})
                
                # Get response from OpenAI
                response = await chat_with_openai(messages, tools)
                messages.append(response)
                
                # Handle tool calls
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    for tool_call in response.tool_calls:
                        # Call the tool on the GO Transit MCP server
                        arguments = json.loads(tool_call.function.arguments)
                        st.info(f"Calling {tool_call.function.name} with arguments: {arguments}")
                        
                        tool_result = await call_tool(client, tool_call.function.name, arguments)
                        
                        # Add tool response to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result
                        })
                    
                    # Get final response from OpenAI
                    final_response = await chat_with_openai(messages, tools)
                    messages.append(final_response)
                    return final_response.content
                else:
                    return response.content
        
        except Exception as e:
            st.error(f"Failed to connect to GO Transit MCP server: {e}")
            st.warning("Using fallback mode...")
            
            # Fallback mode - basic transit info
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "basic_transit_info",
                        "description": "Provide basic GO Transit information",
                        "parameters": {
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
                }
            ]
            
            messages.append({"role": "user", "content": user_input})
            response = await chat_with_openai(messages, tools)
            messages.append(response)
            
            if hasattr(response, 'tool_calls') and response.tool_calls:
                for tool_call in response.tool_calls:
                    arguments = json.loads(tool_call.function.arguments)
                    tool_result = f"I'm unable to connect to the GO Transit server right now. Please try asking about train schedules, fares, or routes and I'll do my best to help! (Query: {arguments['query']})"
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result
                    })
                
                final_response = await chat_with_openai(messages, tools)
                messages.append(final_response)
                return final_response.content
            else:
                return response.content
    
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
    
    # Reset button
    reset = st.button("Reset Chat")
    if reset:
        st.session_state["messages"] = []
        st.session_state["history"] = []
        st.session_state["reset_counter"] += 1  # Change the key to force input reset
        st.rerun()
    
    # Connection status and quick actions
    with st.sidebar:
        st.header("🚆 GO Transit Info")
        st.info(f"Server: {server_url}")
        st.success("GO Transit MCP Client Ready!")
        
        st.markdown("---")
        st.header("Quick Examples")
        st.markdown("""
        Try asking:
        - "Find trains from Milton to Union Station"
        - "What's the fare from Mississauga to Toronto?"
        - "Show me the earliest train from Oshawa to Union"
        - "What are the weekend schedules?"
        """)
        
        st.markdown("---")
        st.header("Available Stations")
        st.markdown("""
        Popular stations:
        - Union Station
        - Milton GO
        - Mississauga GO
        - Brampton GO
        - Oshawa GO
        - Oakville GO
        - And many more...
        """)
    
    # Chat interface - use reset_counter in key to force reset
    user_input = st.text_input("Ask about GO Transit:", 
                              key=f"user_input_{st.session_state['reset_counter']}", 
                              placeholder="e.g., 'Find trains from Milton to Union Station tomorrow morning'")
    
    if st.button("Send") and user_input:
        with st.spinner("Connecting to GO Transit server and searching..."):
            try:
                response = sync_chat_response(st.session_state["messages"], user_input)
                st.session_state["history"].append((user_input, response))
                st.rerun()
            except Exception as e:
                st.error("An error occurred:")
                st.error(str(e))
    
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

def run_streamlit():
    main()

if __name__ == "__main__":
    run_streamlit()
