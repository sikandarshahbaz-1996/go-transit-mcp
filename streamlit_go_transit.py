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
        # Get current EST datetime for context
        eastern = pytz.timezone('America/Toronto')
        current_time = datetime.now(eastern)
        current_datetime_str = current_time.strftime("%A, %B %d, %Y at %I:%M %p %Z")
        current_day = current_time.strftime("%A")
        tomorrow_day = (current_time + timedelta(days=1)).strftime("%A")
        
        # Ensure system message is always present and first
        system_prompt = f"""
            You are a professional GO Transit assistant helping customers with train schedules, fares, and route planning in the Greater Toronto Area (GTA) and surrounding regions. You have access to the GO Transit MCP server.

            ## CURRENT DATE/TIME CONTEXT:
            **Current Date/Time: {current_datetime_str}**
            **Today is: {current_day}**

            Use this information to interpret relative time requests:
            - "today" = {current_day}
            - "tomorrow" = {tomorrow_day}
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

             **TODAY** = {current_day}
             **TOMORROW** = {tomorrow_day}
             
             IMPORTANT: If they user does not specify the day, you must choose the current day by default.
             
             FOR "LATEST" OR "LAST" QUERIES: You MUST select the final item in the array with the highest departure time.
             NEVER select the first item when asked for "latest" or "last" - this is wrong!

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
            - find_trip: Get train schedules between locations for specific days
            - get_fare: Calculate fare costs between two locations
            - get_current_datetime: Get current EST date/time for complex time calculations

            ## CRITICAL STATION NAME RULES:
            YOU MUST ONLY USE EXACT STATION NAMES FROM THE OFFICIAL LIST. When users say informal names, map them to the correct official name.
            
            **CRITICAL MAPPING EXAMPLES:**
            - User says "Oshawa" or "Oshawa GO" → Use "Durham College Oshawa GO"
            - User says "Union" → Use "Union Station"  
            - User says "Airport" or "Pearson" → Use "Pearson Airport Terminal 1"
            - User says "McMaster" → Use "McMaster University"
            - User says "Wonderland" → Use "Major Mackenzie West Bus Terminal (Canada's Wonderland)"
            - User says "Square One" → Use "Square One" (exact match)
            - User says "Toronto Zoo" → Use "Toronto Zoo" (exact match)
            - User says "Milton" → Use "Milton GO"
            
            **COMPLETE OFFICIAL STATION LIST:**
            These are the ONLY valid station names you can use. When users say informal names, map them to exact matches from this list:
            
            10953 Hwy. 48 @ Elgin Mills Rd. E.
            279 Guelph St. @ Sinclair Ave.
            324 Guelph St. @ Sinclair Ave.
            4th Line @ Chiefswood Rd.
            50 Generations Dr. (Oneida Business Park)
            6715 Millcreek Dr. @ Aquitaine Ave. (Millcreek Business Centre)
            785 York Rd. @ Cityview Dr.
            Acton GO
            Agincourt GO
            Ajax GO
            Ajax GO Bus
            Albion Rd. @ Steeles Ave. W.
            Aldershot GO
            Aldershot GO Bus
            Allandale Waterfront GO
            Allandale Waterfront GO Bus
            Alma St. @ Fall St. (Rockwood Conservation Area)
            Alma St. @ Inkerman St.
            Appleby GO
            Appleby GO Bus
            Aquitaine Ave. @ Formentera Ave. (Meadowvale Town Centre)
            Aquitaine Ave. @ Glen Erin Dr.
            Aquitaine Ave. @ Meadowvale Town Centre Circle
            Aquitaine Ave. @ Millcreek Dr.
            Aquitaine Ave. @ Montevideo Rd.
            Aurora GO
            Aurora GO Bus
            Baldwin St. @ Hwy. 407 Park & Ride
            Barrie South GO
            Barrie South GO Bus
            Barrie St. @ 8th Line
            Barrie St. @ Britannia Ave.
            Barrie St. @ Doctors Lane
            Barrie St. @ Fletcher St.
            Barrie St. @ Holland St. W.
            Barrie Transit Terminal
            Bayview Ave. @ Langstaff Rd. E.
            Bayview Ave. @ Mulock Dr.
            Bayview Ave. @ River Ridge Blvd.
            Bayview Ave. @ St. John's Sideroad
            Blind Line @ Banting Dr.
            Blind Line @ College Ave.
            Blind Line @ Hansen Blvd.
            Blind Line @ St. Andrews Dr.
            Bloomington GO
            Bloor GO
            Bond St. W. @ Centre St. N.
            Bond St. W. @ Park Rd. N.
            Bond St. W. @ Stevenson Rd. N.
            Bovaird Dr. W. @ Chinguacousy Rd.
            Bovaird Dr. W. @ Hurontario St.
            Bovaird Dr. W. @ Lake Louise Dr.
            Bovaird Dr. W. @ McLaughlin Rd. N.
            Bovaird Dr. W. @ Mississauga Rd.
            Bovaird Dr. W. @ Worthington Ave.
            Bowmanville Ave. @ Baseline Rd.
            Bradford GO
            Bradford GO Bus
            Bradford St. @ Olive St.
            Bradford St. @ Yonge St.
            Bramalea Bus Terminal
            Bramalea GO
            Bramalea GO Bus
            Bramalea Rd. @ Avondale Blvd.
            Bramalea Rd. @ Balmoral Dr.
            Bramalea Rd. @ Dearbourne Blvd.
            Brampton Bus Terminal
            Brampton Innovation District GO
            Brant St. @ Churchill Ave.
            Brant St. @ Leighland Rd.
            Brantford Bus Terminal
            Broadway @ 4th St.
            Broadway @ Banting Dr.
            Broadway @ Blind Line
            Broadway @ Centre St.
            Broadway @ Dawson Rd.
            Broadway @ John St.
            Broadway @ Townline
            Broadway @ Wellington St.
            Brock Rd. @ Hwy. 407 Park & Ride
            Brock Rd. @ McLean Rd. (Aberfoyle) Park & Ride
            Brock Rd. S. @ Gilmour Rd.
            Brock Rd. S. @ Maple Leaf Ln.
            Brock Rd. S. @ Old Brock Rd.
            Brock University
            Bronte GO
            Bronte GO Bus
            Bronte Rd. @ Hwy. 407 Park & Ride
            Bullock Dr. @ Austin Dr.
            Bullock Dr. @ Hwy. 7
            Bullock Dr. @ Laidlaw Blvd.
            Bullock Dr. @ McCowan Rd.
            Bullock Dr. @ McCowan Rd. (Centennial GO)
            Burlington GO
            Burlington GO Bus
            Burton Ave. @ Bayview Dr.
            Burton Ave. @ Granville St.
            Cambridge Smart Centre
            Casablanca Blvd. @ QEW Park & Ride
            Centennial College
            Centennial GO
            Centennial Pkwy N. @ QEW (Confederation) Park & Ride
            Centre St. S. @ Athol St. W.
            Chiefswood Rd. @ 4th Line
            Chiefswood Rd. @ Sour Springs Rd.
            Clarington Blvd. @ Durham Hwy. 2
            Clarington Blvd. @ Durham Hwy. 2 (Bowmanville) Park & Ride
            Clark Blvd. @ Kings Cross Rd.
            Clarkson GO
            Clarkson GO Bus
            Colborne St E. @ Kiwanis Way
            Colborne St. E. @ Park Ave.
            Colborne St. E. @ Puleston St.
            Consumers Rd. @ William Sylvester Dr.
            Cooksville GO
            Cooksville GO Bus
            Cornell Bus Terminal
            Courtice Rd. @ Baseline Rd. Park & Ride
            Crawford Dr. @ Harper Rd. Park & Ride
            Creditview Rd. @ Eglinton Ave.
            Creditview Rd. @ Rathkeale Rd.
            Dalhousie St. @ Park Ave.
            Danforth GO
            Davis Dr. @ Hwy. 404 Park & Ride
            Davis Dr. @ Prospect St.
            Davis Dr. @ Superior St. (Newmarket GO)
            Davis Dr. W. @ Eagle St. W.
            Derry Rd. @ Armstrong Blvd.
            Derry Rd. @ Fourth Line
            Derry Rd. @ James Snow Pkwy.
            Derry Rd. @ Miller Way
            Derry Rd. @ Sauve St.
            Derry Rd. @ Thompson Rd. S.
            Derry Rd. @ Trudeau Dr.
            Derry Rd. W. @ Danton Promenade
            Derry Rd. W. @ Forest Park Dr.
            Derry Rd. W. @ Lisgar Dr.
            Derry Rd. W. @ Ninth Line
            Derry Rd. W. @ Rosehurst Dr.
            Derry Rd. W. @ Tenth Line W.
            Derry Rd. W. @ Terragar Blvd.
            Derry Rd. W. @ Winston Churchill Blvd.
            Dixie GO
            Dixie Transitway Station
            Downsview Park GO
            Drew Centre @ Thompson Rd. S.
            Dundas St. @ Anderson St.
            Dundas St. @ Brock St.
            Dundas St. @ Garden St.
            Dundas St. @ Halls Rd.
            Dundas St. @ Hopkins St.
            Dundas St. @ Hwy. 407 Park & Ride
            Dundas St. @ Hwy. 412 Park & Ride
            Dundas St. @ Thickson Rd.
            Dundas St. @ White Oaks Crt.
            Dupont Meadow Pl. @ Mississauga Rd.
            Durham College Campus/Ontario Tech University
            Durham College Oshawa GO
            Durham Hwy. 2 @ Bennett Rd.
            Durham Hwy. 2 @ Bowmanville Ave.
            Durham Hwy. 2 @ Bragg Rd.
            Durham Hwy. 2 @ Browview Rd.
            Durham Hwy. 2 @ Durham Regional Rd. 42
            Durham Hwy. 2 @ Kurve Inn Rd.
            Durham Hwy. 2 @ Lambs Rd.
            Durham Hwy. 2 @ Rickard Rd.
            Durham Hwy. 47 @ Goodwood Rd.
            Durham Rd. 57 @ Bowmanville Ave.
            Durham Rd. 57 @ Waverley Rd.
            East Gwillimbury GO
            East Gwillimbury GO Bus
            Eglinton Ave. W. @ Credit Valley Rd.
            Eglinton Ave. W. @ Mississauga Rd.
            Eglinton Ave. W. @ Summersky Crt.
            Eglinton GO
            Elizabeth St. @ Beaumont Cr.
            Elizabeth St. @ Stevenson St. S.
            Elizabeth St. @ Victoria Rd.
            Elizabeth St. @ Victoria Rd. S.
            Erie Ave. @ Ninth Ave.
            Erin Mills Pkwy. @ Banfield Rd.
            Erin Mills Pkwy. @ Battleford Rd.
            Erin Mills Pkwy. @ Britannia Rd. W.
            Erin Mills Pkwy. @ Erin Centre Blvd.
            Erin Mills Pkwy. @ McFarren Blvd.
            Erin Mills Pkwy. @ Millcreek Dr.
            Erin Mills Pkwy. @ Turner Valley Rd.
            Erin Mills Pkwy. @ Vista Blvd.
            Erin Mills Pkwy. @ Wickham Rd.
            Erin Mills Pkwy. @ Windwood Dr.
            Erin Mills Transitway Station
            Erindale GO
            Erindale GO Bus
            Etobicoke North GO
            Exhibition GO
            Fairview St. @ Maple Ave.
            Financial Dr. @ Syntex Crt.
            Finch Ave. @ Kenview Blvd.
            Finch Ave. @ Kenview Blvd. (Wild Water Kingdom)
            Finch Ave. W. @ Darcel Ave.
            Finch Ave. W. @ Longo Circle
            Finch Bus Terminal
            First Ave. @ Front St. Park & Ride
            Georgetown GO
            Georgetown GO Bus
            Georgetown Market
            Gordon St. @ Arkell Rd.
            Gordon St. @ Clair Rd. E.
            Gordon St. @ Clair Rd. W.
            Gordon St. @ Clairfields Dr. E.
            Gordon St. @ Clairfields Dr. W.
            Gordon St. @ Edinburgh Rd. S.
            Gordon St. @ Kortright Rd.
            Gordon St. @ Kortright Rd. E.
            Gordon St. @ Stone Rd.
            Gormley GO
            Green Lane E. @ Yonge St.
            Guelph Central GO
            Guelph Central GO Bus
            Guelph St. @ Alcott Dr.
            Guelph St. @ Armstrong Ave.
            Guelph St. @ Delrex Blvd.
            Guelph St. @ Hall Rd.
            Guelph St. @ King St.
            Guelph St. @ Lakeview Ave.
            Guelph St. @ Maple Ave.
            Guelph St. @ McFarlane Dr.
            Guelph St. @ Mill St.
            Guelph St. @ Mountainview Rd. N.
            Guelph St. @ Mountainview Rd. S.
            Guelph St. @ Noble St.
            Guelph St. @ Sinclair Ave.
            Guelph St. W. @ Lakeview Ave.
            Guildwood GO
            Hamilton GO Centre
            Hamilton GO Centre Bus
            Hansen Blvd. @ First St. (Orangeville Mall)
            Hansen Blvd. @ Michael Dr.
            Hansen Blvd. @ Scott Dr.
            Hespeler Rd. @ Pinebush Rd.
            Holland St. E. @ Colborne St.
            Hurontario St. @ Boston Mills Rd.
            Hurontario St. @ Bovaird Dr. W.
            Hurontario St. @ Charleston Side Rd.
            Hurontario St. @ Chester Dr.
            Hurontario St. @ Conservation Dr.
            Hurontario St. @ County Court Blvd.
            Hurontario St. @ Elm Dr.
            Hurontario St. @ Fairview Rd.
            Hurontario St. @ Forks of The Credit Rd.
            Hurontario St. @ Hwy. 407 Park & Ride
            Hurontario St. @ King St.
            Hurontario St. @ Mayfield Rd.
            Hurontario St. @ McCannell Ave.
            Hurontario St. @ Mistywood Dr.
            Hurontario St. @ Old School Rd.
            Hurontario St. @ Olde Baseline Rd.
            Hurontario St. @ Ray Lawson Blvd.
            Hurontario St. @ Sandalwood Pkwy. E.
            Hurontario St. @ Sandalwood Pkwy. W.
            Hurontario St. @ Sir Lou Dr.
            Hurontario St. @ Terry St.
            Hurontario St. @ Travelled Rd.
            Hurontario St. @ Wanless Dr.
            Hwy 407 Bus Terminal
            Hwy. 10 @ 4th Ave.
            Hwy. 10 @ Buena Vista Dr.
            Hwy. 10 @ Dufferin Rd.
            Hwy. 10 @ Travelled Rd.
            Hwy. 11 @ Meadowland St.
            Hwy. 2 @ Hwy. 35/115 Park & Ride
            Hwy. 35 @ Hwy. 115 Park & Ride
            Hwy. 401 @ Keele St.
            Hwy. 47 @ Front St.
            Hwy. 47 @ Paisley Ln.
            Hwy. 48 @ 16th Ave.
            Hwy. 48 @ 19th Ave.
            Hwy. 48 @ Hoover Park Dr.
            Hwy. 50 @ Bellchase Trail
            Hwy. 50 @ Castlemore Rd.
            Hwy. 50 @ Columbia Way
            Hwy. 50 @ Cottrelle Blvd.
            Hwy. 50 @ Ebenezer Rd.
            Hwy. 50 @ Langstaff Rd.
            Hwy. 50 @ McEwan Dr.
            Hwy. 50 @ Queen St. E.
            Hwy. 50 @ Trade Valley Dr.
            Hwy. 7 @ Banting Rd.
            Hwy. 7 @ Bethel Rd.
            Hwy. 7 @ Hyland Ave.
            Hwy. 7 @ Swansea Rd.
            Hwy. 9 @ Hwy. 400 Park & Ride
            Keele St. @ Barhill Rd.
            Keele St. @ Barrhill Rd.
            Keele St. @ Burton Grove (King City GO)
            Keele St. @ Drummond Dr.
            Keele St. @ Hwy. 401
            Keele St. @ Kirby Rd.
            Keele St. @ Peak Point Blvd.
            Keele St. @ Station Rd. (King City GO)
            Keele St. @ Teston Rd.
            Kennedy GO
            King City GO
            King St. E. @ Division St.
            King St. E. @ Galbraith Cr.
            King St. E. @ George St.
            King St. E. @ Hughson St. N.
            King St. E. @ Liberty St.
            King St. E. @ Mearns Ave.
            King St. E. @ Ontario St.
            King St. E. @ Simpson Ave.
            King St. W. @ Dundurn St. N.
            King St. W. @ Park Rd.
            King St. W. @ Pearl St. N.
            King St. W. @ Queen St. N.
            King St. W. @ Roenigk Dr.
            King St. W. @ Scugog St.
            King St. W. @ Stevenson Rd.
            King St. W. @ Strathcona Ave. N.
            King St. W. @ Summers Ln. (Hamilton Place)
            King St. W. @ Temperance St.
            Kingston Rd. @ Brock Rd.
            Kingston Rd. @ Church St.
            Kingston Rd. @ Fairport Rd.
            Kingston Rd. @ Glenanna Rd.
            Kingston Rd. @ Harwood Ave.
            Kingston Rd. @ Port Union Rd.
            Kingston Rd. @ Rougemount Dr.
            Kingston Rd. @ Salem Rd.
            Kingston Rd. @ Sheppard Ave. E.
            Kingston Rd. @ Walnut Ln.
            Kingston Rd. @ Westney Rd.
            Kingston Rd. @ Whites Rd.
            Kipling Bus Terminal
            Kipling GO
            Kitchener GO
            Kitchener GO Bus
            Langstaff GO
            Langstaff Rd. E. @ Bayview Ave.
            Langstaff Rd. E. @ Cedar Ave. (Langstaff GO)
            Langstaff Rd. E. @ Yonge St.
            Lisgar GO
            Lisgar GO Bus
            Liverpool Rd. @ Pickering Pkwy.
            Long Branch GO
            MacDonell St. @ Carden St. (Guelph Central GO)
            Main St. @ Baker Hill Blvd.
            Main St. @ Church St. N.
            Main St. @ Edward St. (Stouffville GO)
            Main St. @ Market St.
            Main St. @ Mill St. E.
            Main St. @ Ringwood Dr.
            Main St. @ Sandale Rd.
            Main St. @ Sandiford Dr.
            Main St. @ Stouffer St.
            Main St. @ Tenth Line
            Main St. @ Weldon Rd.
            Main St. @ Westlawn Cres.
            Main St. N. @ 16th Ave.
            Main St. N. @ Bovaird Dr. W.
            Main St. N. @ Elizabeth Dr.
            Main St. N. @ George St.
            Main St. N. @ Henry St.
            Main St. N. @ Mill St. E.
            Main St. N. @ Moore Park Cres.
            Main St. N. @ Ramona Blvd. (Markham GO)
            Main St. N. @ School Ln.
            Main St. N. @ Station St. (Markham GO)
            Main St. N. @ Vodden St. E.
            Main St. N. @ Vodden St. W.
            Main St. N. @ Williams Pkwy.
            Main St. S. @ Bridge St.
            Main St. S. @ Clarence St.
            Main St. S. @ Dunbar St.
            Main St. S. @ Elgin Dr.
            Main St. S. @ Frederick St.
            Main St. S. @ MacLennan St.
            Main St. S. @ Nanwood Dr.
            Main St. S. @ Ridge Rd.
            Main St. S. @ Valley Rd.
            Main St. S. @ Wellington St. E.
            Main St. W. @ Caroline St. S.
            Main St. W. @ Dundurn St. S.
            Main St. W. @ Haddon Ave. S.
            Main St. W. @ Longwood Rd. S.
            Main St. W. @ Macklin St. S.
            Main St. W. @ Paisley Ave. S.
            Main St. W. @ Pearl St. S.
            Main St. W. @ Ray St. S.
            Main St. W. @ Summers Ln. (Hamilton City Hall)
            Major Mackenzie Dr. E. @ Cedar Ave.
            Major Mackenzie Dr. E. @ Hwy. 404
            Major Mackenzie Dr. W. @ Keele St.
            Major Mackenzie West Bus Terminal (Canada's Wonderland)
            Malton GO
            Malton GO Bus
            Maple Ave. @ Mountainview Rd. N.
            Maple GO
            Maple GO Bus
            Markham GO
            Markham Rd. @ Castlemore Ave.
            Markham Rd. @ Edward Jeffreys Ave.
            Martin Rd. @ Aspen Springs Dr.
            Mayfield Rd. @ Hwy. 50 Park & Ride
            McCowan Rd. @ Triton Rd.
            McMaster Innovation Park
            McMaster University
            Meadowvale GO
            Meadowvale GO Bus
            Military Trail. @ Pan Am Dr.
            Mill St. E. @ Elgin St. N.
            Mill St. E. @ Elgin St. S.
            Mill St. E. @ Fellows St. (Acton GO)
            Millcreek Dr. @ Aquitaine Ave.
            Millcreek Dr. @ Erin Mills Pkwy.
            Millcreek Dr. @ Millrace Crt.
            Milliken GO
            Milton GO
            Milton GO Bus
            Mimico GO
            Mississauga Rd. @ Argentia Rd.
            Mississauga Rd. @ Dupont Meadow Place
            Mississauga Rd. @ Mississauga Rd.
            Mississauga Rd. @ Royal Bank Dr.
            Morningside Ave. @ Tams Rd.
            Mount Joy GO
            Mount Joy GO Bus
            Mount Pleasant GO
            Mount Pleasant GO Bus
            Mountainview Rd. N. @ Maple Ave.
            Moutainview Rd. N. @ Maple Ave.
            New Credit Variety & Gas Bar
            Newmarket GO
            Niagara College
            Niagara Falls Bus Terminal
            Niagara Falls GO
            Oakville GO
            Oakville GO Bus
            Old Cummer GO
            Old Elm GO
            Old Elm GO Bus
            Ontario St. @ QEW (Beamsville) Park & Ride
            Oriole GO
            Pearson Airport Terminal 1
            Peterborough Bus Terminal
            Peterborough Rd. 10 @ Hwy. 115 Park & Ride
            Pickering GO
            Pickering GO Bus
            Plains Rd. E. @ Cedarwood Place
            Plains Rd. E. @ Falcon Blvd.
            Plains Rd. E. @ Francis Rd.
            Plains Rd. E. @ Gallagher Rd.
            Plains Rd. E. @ King Rd.
            Plains Rd. E. @ Lasalle Park Rd.
            Plains Rd. E. @ Waterdown Rd.
            Plains Rd. E. @ Willowbrook Rd.
            Port Credit GO
            Prospect St. @ Davis Dr.
            Prospect St. @ Pearson St.
            Queen St. @ Acton Blvd.
            Queen St. @ Churchill Rd. N.
            Queen St. @ Churchill Rd. S.
            Queen St. @ Hickman St.
            Queen St. @ Longfield Rd.
            Queen St. @ Mill St.
            Queen St. @ Tanners Dr.
            Queen St. N. @ Columbia Way
            Queen St. S. @ Allan Dr.
            Queen St. S. @ Downey Dr.
            Queen St. S. @ Shore St.
            Queen St. S. @ Wilton Dr.
            Queensville Sdrd. @ Hwy. 404 Park & Ride
            Railway St. @ Albert St.
            Rathburn Rd. W. @ Creditview Rd.
            Rathburn Rd. W. @ Elora Dr.
            Rathburn Rd. W. @ Mavis Rd.
            Rathburn Rd. W. @ Perivale Rd.
            Regional Rd. 25 @ Hwy. 401 Park & Ride
            Regional Rd. 50 @ Bolton Heights Dr.
            Regional Rd. 50 @ Countryside Dr.
            Regional Rd. 50 @ Cross Country Blvd.
            Regional Rd. 50 @ George Bolton Pkwy.
            Regional Rd. 50 @ Nashville Rd.
            Regional Rd. 50 @ Queensgate Blvd.
            Regional Rd. 50 @ Rutherford Rd.
            Renforth Dr. @ Convair Dr.
            Renforth Transitway Station
            Richmond Hill Centre
            Richmond Hill GO
            Richmond Hill GO Bus
            Rouge Hill GO
            Rutherford GO
            Rutherford GO Bus
            Scarborough Centre Bus Terminal
            Scarborough GO
            Sheppard Ave. E. @ Herons Hill Way
            Sheridan College
            Shopper's World
            Simcoe St. @ Britannia Ave.
            Simcoe St. N. @ Britannia Ave.
            Simcoe St. N. @ Parkwood Crt.
            Simcoe St. N. @ Richmond St. E.
            Simcoe St. N. @ Windfields Farm Dr.
            Simcoe St. S. @ Athol St. E.
            Sour Springs Rd. @ Chiefswood Rd.
            Sour Springs Rd. @ Mohawk Rd.
            Sportsworld Dr. @ Hwy. 8 Park & Ride
            Square One
            St. Catharines Downtown Terminal
            St. Catharines Fairview Mall
            St. Catharines GO
            Stanley Ave. @ Hwy. 420 Park & Ride
            Steeles Ave. @ Trafalgar Rd. (Toronto Premium Outlets)
            Steeles Ave. E. @ First Gulf Blvd.
            Steeles Ave. E. @ Kennedy Rd. S.
            Steeles Ave. E. @ Rutherford St. S.
            Stouffville GO
            Stouffville Rd. At Goodwood Rd.
            Streetsville GO
            Streetsville GO Bus
            Streetsville GO Station Parking Lot
            Syntex Crt. @ Financial Dr.
            Tenth Line @ Aintree Dr.
            Tenth Line @ Forsyth Farm Dr.
            Tenth Line @ Hemlock Dr.
            Tenth Line @ Norm Faulkner Dr.
            Tenth Line @ Sleepy Hollow Ln.
            Tenth Ln. @ Main St.
            Thomas St. @ Erin Mills Pkwy.
            Thomas St. @ Highbank Rd.
            Thompson Rd. S. @ Childs Dr.
            Thompson Rd. S. @ Derry Rd. W.
            Thompson Rd. S. @ Laurier Ave.
            Thompson Rd. S. @ McCuaig Dr.
            Toll Rd. @ Bradford St.
            Toll Rd. @ Centennial Ave.
            Toll Rd. @ Oriole Dr.
            Toronto St. @ Brock St.
            Toronto St. @ Elgin Park Dr.
            Toronto St. @ Welwood Dr.
            Toronto St. N. @ Albert St.
            Toronto St. S. @ Banff Rd.
            Toronto St. S. @ Campbell Dr.
            Toronto St. S. @ Mill St.
            Toronto St. S. @ Peel St.
            Toronto St. S. @ Poplar St.
            Toronto Zoo
            Townline @ Mill St. (Orangeville) Park & Ride
            Trafalgar Rd. @ Briarhall Gate
            Trafalgar Rd. @ Burnhamthorpe Rd.
            Trafalgar Rd. @ Dundas St.
            Trafalgar Rd. @ Dundas St. E.
            Trafalgar Rd. @ Glenashton Dr.
            Trafalgar Rd. @ Hwy. 407 Park & Ride
            Trafalgar Rd. @ Iroquois Shore Rd.
            Trafalgar Rd. @ Leighland Ave.
            Trafalgar Rd. @ McCraney St. E.
            Trafalgar Rd. @ River Oaks Blvd. E.
            Trafalgar Rd. @ Rosegate Way
            Trafalgar Rd. @ Upper Middle Rd. E.
            Trafalgar Rd. @ White Oaks Blvd.
            Trent University
            Trinity Common Mall
            Union Station
            Union Station Bus Terminal
            Unionville GO
            Unionville GO Bus
            University of Guelph
            University of Toronto Scarborough
            University of Waterloo Terminal
            Upper Canada Mall
            Victoria St. @ Thickson Rd. (Thickson Ridge Power Centre)
            Victoria St. E. @ S. Blair St
            Victoria St. E. @ S. Blair St.
            Victoria St. N. @ Frederick St.
            Waterdown Rd. @ Masonry Crt.
            Wayne Gretzky Pkwy. @ Chatham St.
            Wayne Gretzky Pkwy. @ Elgin St.
            Wayne Gretzky Pkwy. @ Henry St.
            Wayne Gretzky Pwky. @ Henry St.
            Weber St. E. @ Montgomery Rd.
            Weber St. E. @ Queen St. N.
            Weber St. W. @ Queen St. N.
            Wellington St. E. @ Bayview Ave.
            Wellington St. E. @ First Commerce Dr.
            Wellington St. E. @ Hwy. 404 Park & Ride
            Wellington St. E. @ John West Way
            Wellington St. E. @ Mary St.
            Wellington St. E. @ Mavrinac Blvd.
            Wellington St. E. @ Stronach Blvd.
            Wellington St. W. @ George St. S.
            West Harbour GO
            West Harbour GO Bus
            Weston GO
            Whitby GO
            Whitby GO Bus
            Wilfrid Laurier University
            Williams Pkwy. @ Hwy. 410 Park & Ride
            Winston Churchill Blvd. @ Derry Rd. W.
            Winston Churchill Blvd. @ Vanderbilt Rd.
            Winston Churchill Transitway Station
            Woodbine Ave. @ Hwy. 404 Park & Ride
            Woodlawn Rd. W. @ Regal Rd.
            YMCA Blvd. @ Kennedy Rd.
            Yonge St. @ 16th Ave.
            Yonge St. @ 16th Ave. (South Hill Shopping Centre)
            Yonge St. @ 4th Line (Churchill Community Centre)
            Yonge St. @ Ashford Dr.
            Yonge St. @ Aspenwood Dr.
            Yonge St. @ Baif Blvd. (Hillcrest Mall)
            Yonge St. @ Bantry Ave.
            Yonge St. @ Bay Thorn Dr.
            Yonge St. @ Beresford Dr.
            Yonge St. @ Big Bay Point Rd.
            Yonge St. @ Bonshaw Ave.
            Yonge St. @ Bristol Rd.
            Yonge St. @ Bunker Rd.
            Yonge St. @ Carrville Rd.
            Yonge St. @ Centre St.
            Yonge St. @ Churchill Ave.
            Yonge St. @ Clarissa Dr.
            Yonge St. @ Clark Ave. E.
            Yonge St. @ Clark Ave. W.
            Yonge St. @ Country Ln.
            Yonge St. @ County Rd. 89
            Yonge St. @ Cummer Ave.
            Yonge St. @ Davis Dr. (Upper Canada Mall)
            Yonge St. @ Dawson Manor Blvd.
            Yonge St. @ Doncaster Ave.
            Yonge St. @ Drewry Ave.
            Yonge St. @ Edgar Ave.
            Yonge St. @ Elgin St.
            Yonge St. @ Ellerslie Ave.
            Yonge St. @ Elmhurst Ave.
            Yonge St. @ Elmwood Ave.
            Yonge St. @ Empress Ave.
            Yonge St. @ Esther Dr.
            Yonge St. @ Finch Ave.
            Yonge St. @ Florence Ave.
            Yonge St. @ Garden Ave.
            Yonge St. @ Glen Cameron Rd.
            Yonge St. @ Glendora Ave.
            Yonge St. @ Glenn Ave.
            Yonge St. @ Green Ln. E.
            Yonge St. @ Green Ln. E. (Silver City)
            Yonge St. @ Green Ln. W. (Green Lane Centre)
            Yonge St. @ Harding Blvd.
            Yonge St. @ Harding Blvd. W.
            Yonge St. @ High Tech Rd.
            Yonge St. @ Hopkins St.
            Yonge St. @ Hwy. 407
            Yonge St. @ Innisfil Beach Rd.
            Yonge St. @ John St.
            Yonge St. @ Kempford Blvd.
            Yonge St. @ Killarney Beach Rd.
            Yonge St. @ Kingston Rd.
            Yonge St. @ Langstaff Rd. E.
            Yonge St. @ Line 11
            Yonge St. @ Line 13
            Yonge St. @ Little Ave.
            Yonge St. @ London Rd.
            Yonge St. @ Lynn St.
            Yonge St. @ Madawaska Ave.
            Yonge St. @ Madelaine Dr.
            Yonge St. @ Major Mackenzie Dr. E.
            Yonge St. @ Mapleview Dr. E.
            Yonge St. @ May Ave.
            Yonge St. @ Meadowland St.
            Yonge St. @ Meadowview Ave.
            Yonge St. @ Mortonvale Dr.
            Yonge St. @ Mount Albert Rd.
            Yonge St. @ North St.
            Yonge St. @ North York Blvd.
            Yonge St. @ North York Blvd. (Mel Lastman Square)
            Yonge St. @ Northern Heights Dr.
            Yonge St. @ Northtown Way
            Yonge St. @ Norton Ave.
            Yonge St. @ Oak Ave.
            Yonge St. @ Observatory Ln.
            Yonge St. @ Old Yonge St.
            Yonge St. @ Park Home Ave.
            Yonge St. @ Poyntz Ave.
            Yonge St. @ Queen St.
            Yonge St. @ Royal Orchard Blvd.
            Yonge St. @ Scott Dr.
            Yonge St. @ Sheppard Ave.
            Yonge St. @ Shore Acres Dr.
            Yonge St. @ Spruce Ave.
            Yonge St. @ Steeles Ave. W.
            Yonge St. @ Thornhill Ave.
            Yonge St. @ Uplands Ave.
            Yonge St. @ Victoria St.
            Yonge St. @ Weldrick Rd. E.
            Yonge St. @ Weldrick Rd. W.
            Yonge St. @ Westwood Ln.
            Yonge St. @ William Carson Cr.
            Yonge St. @ Yongehurst Dr.
            York Mills Bus Terminal
            York St. @ 800 York St.
            Yorkdale Bus Terminal
            Young St. @ Peel St.
                        
            NEVER invent station names - only use exact matches from this official list. When users say informal names, always map to exact official names.

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
                    return final_response.content, messages
                else:
                    return response.content, messages
        
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
                return final_response.content, messages
            else:
                return response.content, messages
    
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
    input_value = "" if st.session_state["input_submitted"] else None
    user_input = st.text_input("", 
                              key=f"user_input_{st.session_state['reset_counter']}", 
                              placeholder="e.g., 'Find trains from Milton to Union Station tomorrow morning'",
                              value=input_value)
    
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
        st.session_state["input_submitted"] = False
        st.rerun()
    
    if send_button and user_input:
        with st.spinner("Connecting to GO Transit server and searching..."):
            try:
                response, updated_messages = sync_chat_response(st.session_state["messages"], user_input)
                st.session_state["messages"] = updated_messages  # Persist conversation context
                st.session_state["history"].append((user_input, response))
                st.session_state["input_submitted"] = True  # Flag to clear input
                st.rerun()
            except Exception as e:
                st.error("An error occurred:")
                st.error(str(e))
    
    # Reset input_submitted flag after rerun
    if st.session_state["input_submitted"]:
        st.session_state["input_submitted"] = False

def run_streamlit():
    main()

if __name__ == "__main__":
    run_streamlit()
