import csv
import os
import subprocess
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BASE_URL = "https://api.openmetrolinx.com/OpenDataAPI/api/V1/"

def findTrip(date="20250902", from_station="ML", to_station="UN", time="0700", max_results="20"):
    api_key = os.getenv('METROLINX_API_KEY')
    
    if not api_key:
        raise ValueError("METROLINX_API_KEY not found in environment variables")
    
    endpoint = f"Schedule/Journey/{date}/{from_station}/{to_station}/{time}/{max_results}"
    url = f"{BASE_URL}{endpoint}?key={api_key}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('Metadata', {}).get('ErrorCode') == '200':
            return data
        else:
            error_msg = data.get('Metadata', {}).get('ErrorMessage', 'Unknown error')
            raise Exception(f"API Error: {error_msg}")
            
    except requests.exceptions.RequestException as e:
        raise Exception(f"Request failed: {str(e)}")
    except ValueError as e:
        raise Exception(f"Invalid JSON response: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error: {str(e)}")


def getStations():
    api_key = os.getenv('METROLINX_API_KEY')
    
    if not api_key:
        raise ValueError("METROLINX_API_KEY not found in environment variables")
    
    endpoint = "Stop/All"
    url = f"{BASE_URL}{endpoint}?key={api_key}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('Metadata', {}).get('ErrorCode') == '200':
            return data
        else:
            error_msg = data.get('Metadata', {}).get('ErrorMessage', 'Unknown error')
            raise Exception(f"API Error: {error_msg}")
            
    except requests.exceptions.RequestException as e:
        raise Exception(f"Request failed: {str(e)}")
    except ValueError as e:
        raise Exception(f"Invalid JSON response: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error: {str(e)}")


def getFare(from_station, to_station):
    api_key = os.getenv('METROLINX_API_KEY')
    
    if not api_key:
        raise ValueError("METROLINX_API_KEY not found in environment variables")
    
    endpoint = f"Fares/{from_station}/{to_station}"
    url = f"{BASE_URL}{endpoint}?key={api_key}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('Metadata', {}).get('ErrorCode') == '200':
            return data
        else:
            error_msg = data.get('Metadata', {}).get('ErrorMessage', 'Unknown error')
            raise Exception(f"API Error: {error_msg}")
            
    except requests.exceptions.RequestException as e:
        raise Exception(f"Request failed: {str(e)}")
    except ValueError as e:
        raise Exception(f"Invalid JSON response: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error: {str(e)}")


def getTripUpdates():
    api_key = os.getenv('METROLINX_API_KEY')
    
    if not api_key:
        raise ValueError("METROLINX_API_KEY not found in environment variables")
    
    endpoint = "Gtfs/Feed/TripUpdates"
    url = f"{BASE_URL}{endpoint}?key={api_key}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        
        # GTFS feeds have a different structure - check for header and entity
        if 'header' in data and 'entity' in data:
            return data
        else:
            raise Exception("Invalid GTFS response format")
            
    except requests.exceptions.RequestException as e:
        raise Exception(f"Request failed: {str(e)}")
    except ValueError as e:
        raise Exception(f"Invalid JSON response: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error: {str(e)}")

def getServiceExceptions():
    api_key = os.getenv('METROLINX_API_KEY')
    
    if not api_key:
        raise ValueError("METROLINX_API_KEY not found in environment variables")
    
    endpoint = "ServiceUpdate/Exceptions/All"
    url = f"{BASE_URL}{endpoint}?key={api_key}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('Metadata', {}).get('ErrorCode') == '200':
            return data
        else:
            error_msg = data.get('Metadata', {}).get('ErrorMessage', 'Unknown error')
            raise Exception(f"API Error: {error_msg}")
            
    except requests.exceptions.RequestException as e:
        raise Exception(f"Request failed: {str(e)}")
    except ValueError as e:
        raise Exception(f"Invalid JSON response: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error: {str(e)}")

def getServiceAlerts():
    api_key = os.getenv('METROLINX_API_KEY')
    
    if not api_key:
        raise ValueError("METROLINX_API_KEY not found in environment variables")
    
    endpoint = "Gtfs/Feed/Alerts"
    url = f"{BASE_URL}{endpoint}?key={api_key}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        
        # GTFS feeds have a different structure - check for header and entity
        if 'header' in data and 'entity' in data:
            return data
        else:
            raise Exception("Invalid GTFS response format")
            
    except requests.exceptions.RequestException as e:
        raise Exception(f"Request failed: {str(e)}")
    except ValueError as e:
        raise Exception(f"Invalid JSON response: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error: {str(e)}")

def mergeRealTimeData(scheduled_trips, trip_updates=None, exceptions=None, alerts=None):
    """
    Merge real-time data with scheduled trips to provide enhanced status information.
    """
    if not scheduled_trips or 'SchJourneys' not in scheduled_trips:
        return scheduled_trips
    
    # Create lookup dictionaries for real-time data
    trip_updates_lookup = {}
    exceptions_lookup = {}
    alerts_lookup = {}
    
    # Process trip updates if available
    if trip_updates and 'entity' in trip_updates:
        for entity in trip_updates['entity']:
            if 'tripUpdate' in entity and 'trip' in entity['tripUpdate']:
                trip_id = entity['tripUpdate']['trip'].get('tripId', '')
                trip_updates_lookup[trip_id] = entity['tripUpdate']
    
    # Process exceptions if available
    if exceptions and 'Exceptions' in exceptions:
        for exception in exceptions['Exceptions']:
            trip_number = exception.get('TripNumber', '')
            exceptions_lookup[trip_number] = exception
    
    # Process alerts if available
    if alerts and 'entity' in alerts:
        for entity in alerts['entity']:
            if 'alert' in entity:
                alert = entity['alert']
                # Alerts might affect multiple trips
                if 'informedEntity' in alert:
                    for informed_entity in alert['informedEntity']:
                        if 'trip' in informed_entity:
                            trip_id = informed_entity['trip'].get('tripId', '')
                            if trip_id not in alerts_lookup:
                                alerts_lookup[trip_id] = []
                            alerts_lookup[trip_id].append(alert)
    
    # Enhance each journey with real-time data
    for journey in scheduled_trips['SchJourneys']:
        for service in journey['Services']:
            for trip in service['Trips']['Trip']:
                trip_number = trip.get('Number', '')
                trip_id = f"{trip.get('Line', '')}_{trip_number}"
                
                # Initialize status
                trip['Status'] = {
                    'isDelayed': False,
                    'isCancelled': False,
                    'delayMinutes': 0,
                    'realTimeDeparture': None,
                    'realTimeArrival': None,
                    'statusMessage': None,
                    'alerts': []
                }
                
                # Check for exceptions (cancellations)
                if trip_number in exceptions_lookup:
                    exception = exceptions_lookup[trip_number]
                    trip['Status']['isCancelled'] = True
                    trip['Status']['statusMessage'] = exception.get('Message', 'Trip cancelled')
                
                # Check for trip updates (delays)
                elif trip_id in trip_updates_lookup:
                    update = trip_updates_lookup[trip_id]
                    if 'stopTimeUpdate' in update:
                        for stop_update in update['stopTimeUpdate']:
                            if 'departure' in stop_update and 'delay' in stop_update['departure']:
                                delay_seconds = stop_update['departure']['delay']
                                if delay_seconds > 0:
                                    trip['Status']['isDelayed'] = True
                                    trip['Status']['delayMinutes'] = delay_seconds // 60
                                    trip['Status']['statusMessage'] = f"Delayed by {trip['Status']['delayMinutes']} minutes"
                
                # Check for alerts
                if trip_id in alerts_lookup:
                    trip['Status']['alerts'] = alerts_lookup[trip_id]
                    if not trip['Status']['statusMessage']:
                        trip['Status']['statusMessage'] = "Service alerts available"
    
    return scheduled_trips

def findTripWithRealTime(date="20250902", from_station="ML", to_station="UN", time="0700", max_results="20"):
    """
    Enhanced findTrip function that includes real-time status information.
    """
    # Get scheduled trips
    scheduled_trips = findTrip(date, from_station, to_station, time, max_results)
    
    if not scheduled_trips:
        return None
    
    # Get real-time data (with error handling)
    trip_updates = None
    exceptions = None
    alerts = None
    
    try:
        trip_updates = getTripUpdates()
    except Exception as e:
        # Log error but continue with scheduled trips
        pass
    
    try:
        exceptions = getServiceExceptions()
    except Exception as e:
        # Log error but continue with scheduled trips
        pass
    
    try:
        alerts = getServiceAlerts()
    except Exception as e:
        # Log error but continue with scheduled trips
        pass
    
    # Merge real-time data with scheduled trips
    enhanced_trips = mergeRealTimeData(scheduled_trips, trip_updates, exceptions, alerts)
    
    return enhanced_trips

