import csv
import os
from datetime import datetime, timedelta

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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

        with open(os.path.join(BASE_DIR, 'GO-GTFS/stop_times.txt'), 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            stop_times = {}
            for row in reader:
                if row['trip_id'] in trips:
                    if row['trip_id'] not in stop_times:
                        stop_times[row['trip_id']] = {}
                    stop_times[row['trip_id']][row['stop_id']] = row['departure_time']

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
