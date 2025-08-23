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
    
    with open(os.path.join(BASE_DIR, 'GO-GTFS/stops.txt'), 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        stops = {}
        for row in reader:
            processed_name = row['stop_name'].replace(' GO', '').lower()
            # Handle duplicate processed names - prefer shorter stop_id (usually the main station)
            if processed_name not in stops or len(row['stop_id']) < len(stops[processed_name]):
                stops[processed_name] = row['stop_id']
    
    # Handle common location name variations with robust matching
    def find_location_id(location_name):
        location_lower = location_name.lower().strip()
        
        # 1. Direct exact match first
        if location_lower in stops:
            return stops[location_lower]
        
        # 2. Handle special cases
        if location_lower == 'union':
            return stops.get('union station')
        
        # For Hamilton GO Centre, prefer the bus terminal (which has more connections)
        if location_lower in ['hamilton go centre', 'hamilton centre', 'hamilton go center', 'hamilton center']:
            return stops.get('hamilton centre bus', stops.get('hamilton centre'))
        
        # 3. Try common variations
        variations = [
            location_lower.replace(' go centre', '').replace(' go center', ''),
            location_lower.replace(' go station', '').replace(' station', ''),
            location_lower.replace(' go', ''),
            location_lower + ' centre',
            location_lower + ' center', 
            location_lower + ' station',
            location_lower + ' go'
        ]
        
        for variation in variations:
            if variation in stops:
                return stops[variation]
        
        # 4. Word-based partial matching (more robust than substring)
        import re
        location_words = set(re.findall(r'\b\w+\b', location_lower))
        
        best_match = None
        best_score = 0
        
        for stop_name, stop_id in stops.items():
            stop_words = set(re.findall(r'\b\w+\b', stop_name))
            
            # Calculate match score based on word overlap
            common_words = location_words.intersection(stop_words)
            if common_words:
                # Score based on percentage of input words matched and total word overlap
                input_coverage = len(common_words) / len(location_words)
                stop_coverage = len(common_words) / len(stop_words)
                score = input_coverage * 0.7 + stop_coverage * 0.3 + len(common_words) * 0.1
                
                # Boost score for key transit words
                if any(word in common_words for word in ['university', 'college', 'centre', 'center', 'station', 'terminal']):
                    score += 0.2
                
                # Require high input coverage to avoid false matches
                if score > best_score and input_coverage >= 0.6:
                    best_match = stop_id
                    best_score = score
        
        return best_match
    
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
    with open(os.path.join(BASE_DIR, 'GO-GTFS/stops.txt'), 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        stops = {}
        for row in reader:
            processed_name = row['stop_name'].replace(' GO', '').lower()
            # Handle duplicate processed names - prefer shorter stop_id (usually the main station)
            if processed_name not in stops or len(row['stop_id']) < len(stops[processed_name]['stop_id']):
                stops[processed_name] = {'stop_id': row['stop_id'], 'zone_id': row['zone_id']}
    
    # Handle common location name variations with robust matching (same logic as findTrip)
    def find_location_info(location_name):
        location_lower = location_name.lower().strip()
        
        # 1. Direct exact match first
        if location_lower in stops:
            return stops[location_lower]
        
        # 2. Handle special cases
        if location_lower == 'union':
            return stops.get('union station')
        
        # For Hamilton GO Centre, prefer the bus terminal (which has more connections)
        if location_lower in ['hamilton go centre', 'hamilton centre', 'hamilton go center', 'hamilton center']:
            return stops.get('hamilton centre bus', stops.get('hamilton centre'))
        
        # 3. Try common variations
        variations = [
            location_lower.replace(' go centre', '').replace(' go center', ''),
            location_lower.replace(' go station', '').replace(' station', ''),
            location_lower.replace(' go', ''),
            location_lower + ' centre',
            location_lower + ' center', 
            location_lower + ' station',
            location_lower + ' go'
        ]
        
        for variation in variations:
            if variation in stops:
                return stops[variation]
        
        # 4. Word-based partial matching (more robust than substring)
        import re
        location_words = set(re.findall(r'\b\w+\b', location_lower))
        
        best_match = None
        best_score = 0
        
        for stop_name, stop_info in stops.items():
            stop_words = set(re.findall(r'\b\w+\b', stop_name))
            
            # Calculate match score based on word overlap
            common_words = location_words.intersection(stop_words)
            if common_words:
                # Score based on percentage of input words matched and total word overlap
                input_coverage = len(common_words) / len(location_words)
                stop_coverage = len(common_words) / len(stop_words)
                score = input_coverage * 0.7 + stop_coverage * 0.3 + len(common_words) * 0.1
                
                # Boost score for key transit words
                if any(word in common_words for word in ['university', 'college', 'centre', 'center', 'station', 'terminal']):
                    score += 0.2
                
                # Require high input coverage to avoid false matches
                if score > best_score and input_coverage >= 0.6:
                    best_match = stop_info
                    best_score = score
        
        return best_match
    
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
