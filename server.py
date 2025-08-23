from mcp.server.fastmcp import FastMCP
from functions import findTrip, calculate_fare
from pydantic import BaseModel, Field
from typing import List

mcp = FastMCP("Go Transit", host="0.0.0.0", port=8000)

class Trip(BaseModel):
    when: str = Field(description="The day of the week to find a trip for")
    from_location: str = Field(description="The location to start the trip from (GO station, bus stop, or transit hub)")
    to_location: str = Field(description="The location to end the trip at (GO station, bus stop, or transit hub)")

@mcp.tool()
def find_trip(trip: Trip) -> list[dict] | None:
    """
    Gets the trip information for a given day between two GO Transit locations.
    Args:
        - when: The day of the week to find a trip for.
        - from_location: The location to start the trip from (GO station, bus stop, or transit hub).
        - to_location: The location to end the trip at (GO station, bus stop, or transit hub).

    Returns:
        list[dict] | None: List of all trip details for the day, sorted by departure time. None if no trips found.
    """

    return findTrip(trip.when, trip.from_location, trip.to_location)

class FareRequest(BaseModel):
    from_location: str = Field(description="The origin location name (GO station, bus stop, or transit hub)")
    to_location: str = Field(description="The destination location name (GO station, bus stop, or transit hub)")

@mcp.tool()
def get_fare(fare_request: FareRequest) -> dict | None:
    """
    Calculate the fare between two GO Transit locations.
    Args:
        - from_location: The origin location name (GO station, bus stop, or transit hub)
        - to_location: The destination location name (GO station, bus stop, or transit hub)

    Returns:
        dict | None: Fare details including price, currency, and zones. None if locations not found.
    """

    return calculate_fare(fare_request.from_location, fare_request.to_location)

if __name__ == "__main__":
    mcp.run(transport="streamable-http")