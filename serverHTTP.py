from mcp.server.fastmcp import FastMCP
from functions import findTrip, getStations, getFare, findTripWithRealTime
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime
import pytz

mcp = FastMCP("Go Transit", host="0.0.0.0", port=8000)

class Trip(BaseModel):
    date: str = Field(description="Date in YYYYMMDD format (e.g., '20250902' for September 2, 2025)")
    from_station: str = Field(description="Origin station code (e.g., 'ML' for Milton, 'UN' for Union Station)")
    to_station: str = Field(description="Destination station code (e.g., 'ML' for Milton, 'UN' for Union Station)")
    time: str = Field(description="Time in HHMM format (e.g., '0700' for 7:00 AM, '1430' for 2:30 PM)", default="0700")
    max_results: str = Field(description="Maximum number of results to return", default="20")

class FareRequest(BaseModel):
    from_station: str = Field(description="Origin station code (e.g., 'ML' for Milton, 'UN' for Union Station)")
    to_station: str = Field(description="Destination station code (e.g., 'ML' for Milton, 'UN' for Union Station)")

@mcp.tool()
def get_stations() -> dict | None:
    """
    Retrieves the complete list of all GO Transit stations, bus stops, and transit hubs.
    
    This tool should be called first before using find_trip() or get_fare() to get the correct station codes.
    The response includes LocationCode (station code), LocationName (full name), and LocationType.
    
    Returns:
        dict | None: Complete list of all stations with their codes and names. 
        Returns None if error occurs.
    """
    try:
        return getStations()
    except Exception as e:
        return None

@mcp.tool()
def find_trip(trip: Trip) -> dict | None:
    """
    Gets the trip information for a given date and time between two GO Transit locations.
    This enhanced version includes real-time status information such as delays, cancellations, and service alerts.
    
    WORKFLOW:
    1. First call get_stations() to get the complete station list
    2. Use the returned station codes in this find_trip() call
    
    Example workflow:
    - User asks: "Find trips from Toronto to Hamilton"
    - You call: get_stations() 
    - You find: Union Station (UN), Hamilton GO Centre (HA)
    - You call: find_trip(date="20250902", from_station="UN", to_station="HA", time="0700")
    
    Common station examples:
    - Union Station (UN)
    - Milton GO (ML) 
    - Oakville GO (OA)
    - Burlington GO (BU)
    - Hamilton GO Centre (HA)
    - Brampton GO (BR)
    - Mississauga GO (MI)
    - Georgetown GO (GE)
    - Kitchener GO (KI)
    - Guelph Central GO (GL)
    
    REAL-TIME FEATURES:
    - Automatic delay detection and reporting
    - Cancellation notifications
    - Service alert integration
    - Real-time departure/arrival updates
    
    Args:
        - date: Date in YYYYMMDD format (e.g., '20250902' for September 2, 2025)
        - from_station: Origin station code (e.g., 'ML' for Milton, 'UN' for Union Station)
        - to_station: Destination station code (e.g., 'ML' for Milton, 'UN' for Union Station)
        - time: Time in HHMM format (e.g., '0700' for 7:00 AM, '1430' for 2:30 PM)
        - max_results: Maximum number of results to return

    Returns:
        dict | None: Complete API response with trip details including metadata, scheduled journeys, 
        and real-time status information (delays, cancellations, alerts). 
        Returns None if no trips found or error occurs.
    """
    try:
        return findTripWithRealTime(
            date=trip.date,
            from_station=trip.from_station,
            to_station=trip.to_station,
            time=trip.time,
            max_results=trip.max_results
        )
    except Exception as e:
        return None

@mcp.tool()
def get_fare(fare_request: FareRequest) -> dict | None:
    """
    Gets the fare information between two GO Transit locations.
    
    WORKFLOW:
    1. First call get_stations() to get the complete station list
    2. Use the returned station codes in this get_fare() call
    
    Example workflow:
    - User asks: "What's the fare from Toronto to Hamilton?"
    - You call: get_stations() 
    - You find: Union Station (UN), Hamilton GO Centre (HA)
    - You call: get_fare(from_station="UN", to_station="HA")
    
    Common station examples:
    - Union Station (UN)
    - Milton GO (ML) 
    - Oakville GO (OA)
    - Burlington GO (BU)
    - Hamilton GO Centre (HA)
    - Brampton GO (BR)
    - Mississauga GO (MI)
    - Georgetown GO (GE)
    - Kitchener GO (KI)
    - Guelph Central GO (GL)
    
    Args:
        - from_station: Origin station code (e.g., 'ML' for Milton, 'UN' for Union Station)
        - to_station: Destination station code (e.g., 'ML' for Milton, 'UN' for Union Station)

    Returns:
        dict | None: Complete API response with fare information including metadata and all fare categories. 
        Returns None if no fares found or error occurs.
    """
    try:
        return getFare(
            from_station=fare_request.from_station,
            to_station=fare_request.to_station
        )
    except Exception as e:
        return None


@mcp.tool()
def get_current_datetime() -> dict:
    """
    Get the current date and time in Eastern Time (EST/EDT).
    
    Returns:
        dict: Current datetime information including day of week, date, time, and timezone
    """
    # Eastern timezone (handles EST/EDT automatically)
    eastern = pytz.timezone('America/Toronto')
    now = datetime.now(eastern)
    
    return {
        "current_datetime": now.strftime("%A, %B %d, %Y at %I:%M %p %Z"),
        "day_of_week": now.strftime("%A"),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%I:%M %p"),
        "timezone": str(now.tzinfo),
        "iso_format": now.isoformat()
    }

if __name__ == "__main__":
    mcp.run(transport="streamable-http")