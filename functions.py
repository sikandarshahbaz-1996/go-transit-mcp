import csv
import os
import subprocess
from datetime import datetime, timedelta

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def extract_relevant_stop_times(trip_ids, file_path):
    """
    Extract only stop_times rows for specific trip_ids using grep for efficiency.
    This avoids reading the entire 136MB file and only processes relevant rows.
    """
    if not trip_ids:
        return {}
    
    try:
        # Create grep pattern for the trip_ids (escape special characters)
        trip_pattern = '|'.join([trip_id.replace('-', '\\-') for trip_id in trip_ids])
        
        # Use grep to extract only relevant rows (skip header, match trip_id at start)
        result = subprocess.run(
            ['grep', '-E', f'^({trip_pattern}),', file_path],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse the filtered results using CSV format
        stop_times = {}
        for line in result.stdout.strip().split('\n'):
            if line and not line.startswith('trip_id'):  # Skip header if present
                parts = line.split(',')
                if len(parts) >= 4:  # trip_id,arrival_time,departure_time,stop_id,...
                    trip_id = parts[0]
                    departure_time = parts[2]  # departure_time is 3rd column
                    stop_id = parts[3]         # stop_id is 4th column
                    
                    if trip_id not in stop_times:
                        stop_times[trip_id] = {}
                    stop_times[trip_id][stop_id] = departure_time
        
        return stop_times
        
    except subprocess.CalledProcessError:
        # Fallback to original method if grep fails
        return extract_relevant_stop_times_fallback(trip_ids, file_path)
    except Exception as e:
        # Fallback to original method for any other error
        print(f"Grep optimization failed, using fallback: {e}")
        return extract_relevant_stop_times_fallback(trip_ids, file_path)

def extract_relevant_stop_times_fallback(trip_ids, file_path):
    """
    Fallback method that reads the entire file if grep optimization fails.
    This ensures functionality is never broken.
    """
    trip_ids_set = set(trip_ids)
    stop_times = {}
    
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['trip_id'] in trip_ids_set:
                if row['trip_id'] not in stop_times:
                    stop_times[row['trip_id']] = {}
                stop_times[row['trip_id']][row['stop_id']] = row['departure_time']
    
    return stop_times

def findTrip(when, from_location, to_location):
    today = datetime.now().date()
    
    with open(os.path.join(BASE_DIR, 'GO-GTFS/calendar_dates.txt'), 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        service_dates = {datetime.strptime(row['date'], '%Y%m%d').date(): row['service_id'] 
                        for row in reader if datetime.strptime(row['date'], '%Y%m%d').date() > today}
    
    target_dates = [date for date in service_dates.keys() if date.strftime('%A').lower() == when.lower()]
    if not target_dates:
        return None
    
    service_id = service_dates[min(target_dates)]
    
    # Load all stops with exact name matching only
    with open(os.path.join(BASE_DIR, 'GO-GTFS/stops.txt'), 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        stops = {}
        for row in reader:
            # Store exact stop names (case-insensitive)
            stop_name = row['stop_name'].strip()
            stops[stop_name.lower()] = row['stop_id']
    
    # Simple exact matching function - let OpenAI handle the intelligence
    def find_location_id(location_name):
        location_clean = location_name.strip().lower()
        return stops.get(location_clean)
    
    from_id = find_location_id(from_location)
    to_id = find_location_id(to_location)
    if not from_id or not to_id:
        return None
    
    for direction in ['0', '1']:
        with open(os.path.join(BASE_DIR, 'GO-GTFS/trips.txt'), 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            trips = [row['trip_id'] for row in reader if row['service_id'] == service_id and row['direction_id'] == direction]

        all_trips = []

        # OPTIMIZED: Use selective reading instead of reading entire 136MB file
        stop_times_file = os.path.join(BASE_DIR, 'GO-GTFS/stop_times.txt')
        stop_times = extract_relevant_stop_times(trips, stop_times_file)

        for trip_id, times in stop_times.items():
            if from_id in times and to_id in times:
                departure_time = times[from_id]
                arrival_time = times[to_id]
                if departure_time < arrival_time:
                    all_trips.append({
                        'trip_id': trip_id,
                        'departure_time': departure_time,
                        'arrival_time': arrival_time,
                        'from': from_location,
                        'to': to_location
                    })

        if all_trips:
            all_trips.sort(key=lambda x: x['departure_time'])
            return all_trips

    return None

def calculate_fare(from_location, to_location):
    """
    Calculate the fare between two GO Transit locations.
    Returns fare info dictionary or None if not found.
    """
    # Load all stops with exact name matching only
    with open(os.path.join(BASE_DIR, 'GO-GTFS/stops.txt'), 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        stops = {}
        for row in reader:
            # Store exact stop names (case-insensitive) with stop info
            stop_name = row['stop_name'].strip()
            stops[stop_name.lower()] = {'stop_id': row['stop_id'], 'zone_id': row['zone_id']}
    
    # Simple exact matching function - let OpenAI handle the intelligence
    def find_location_info(location_name):
        location_clean = location_name.strip().lower()
        return stops.get(location_clean)
    
    from_info = find_location_info(from_location)
    to_info = find_location_info(to_location)
    
    if not from_info or not to_info:
        return None
    
    from_zone = from_info['zone_id']
    to_zone = to_info['zone_id']
    
    # Look up fare using zones
    fare_id = f"{from_zone}-{to_zone}"
    
    with open(os.path.join(BASE_DIR, 'GO-GTFS/fare_attributes.txt'), 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['fare_id'] == fare_id:
                return {
                    'from_location': from_location,
                    'to_location': to_location,
                    'fare': float(row['price']),
                    'currency': row['currency_type'],
                    'from_zone': from_zone,
                    'to_zone': to_zone
                }
    
    return None
