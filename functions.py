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

