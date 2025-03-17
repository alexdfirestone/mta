import requests
import time
import json
from google.transit import gtfs_realtime_pb2
from protobuf_to_dict import protobuf_to_dict
from datetime import datetime


# Union Square stop IDs for each line
# Format is parent_station + direction (N or S)
UNION_SQ_STOP_IDS = {
    # N, R, Q, W trains (BMT Broadway Line)
    'N': 'R14N',  # Northbound
    'R': 'R14N',  # Northbound
    'Q': 'R14N',  # Northbound
    'W': 'R14N',  # Northbound
    'N_south': 'R14S',  # Southbound
    'R_south': 'R14S',  # Southbound
    'Q_south': 'R14S',  # Southbound
    'W_south': 'R14S',  # Southbound
    
    # 4, 5, 6 trains (IRT Lexington Avenue Line)
    '4': '635N',  # Northbound
    '5': '635N',  # Northbound
    '6': '635N',  # Northbound
    '4_south': '635S',  # Southbound
    '5_south': '635S',  # Southbound
    '6_south': '635S',  # Southbound
    
    # L trains (BMT Canarsie Line)
    'L': 'L03N',  # Northbound/Westbound (8 Avenue)
    'L_south': 'L03S',  # Southbound/Eastbound (Canarsie)
}

# Feed endpoints for different lines
FEED_URLS = {
    'nqrw': 'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw',
    '456': 'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs',  # 1,2,3,4,5,6,S
    'l': 'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-l'
}

def fetch_mta_data(url):
    """Fetch data from MTA API"""
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.content
        else:
            return None
    except Exception as e:
        return None

def parse_gtfs_data(binary_data):
    """Parse GTFS binary data into readable format"""
    if not binary_data:
        return None
        
    feed = gtfs_realtime_pb2.FeedMessage()
    try:
        feed.ParseFromString(binary_data)
    except Exception as e:
        return None
    
    # Convert to dictionary for easier handling
    return protobuf_to_dict(feed)

def is_target_route(route_id):
    """Check if the route is one of our target routes"""
    target_routes = ['N', 'Q', 'R', 'W', '4', '5', '6', 'L']
    return route_id in target_routes

def format_time(timestamp):
    """Format Unix timestamp to readable time"""
    return datetime.fromtimestamp(timestamp).strftime('%I:%M:%S %p')

def get_upcoming_trains_at_union_square(feed_dict):
    """Extract upcoming trains arriving at Union Square"""
    if not feed_dict or 'entity' not in feed_dict:
        return []
    
    upcoming_trains = []
    
    for entity in feed_dict.get('entity', []):
        if 'trip_update' not in entity:
            continue
            
        trip_update = entity['trip_update']
        
        # Skip if no trip or route information
        if 'trip' not in trip_update or 'route_id' not in trip_update['trip']:
            continue
            
        route_id = trip_update['trip']['route_id']
        
        # Only process our target routes
        if not is_target_route(route_id):
            continue
            
        # Skip if no stop time updates
        if 'stop_time_update' not in trip_update:
            continue
        
        # Get direction if available through NYC extensions
        direction = None
        if 'nyct_trip_descriptor' in trip_update['trip']:
            nyct_info = trip_update['trip']['nyct_trip_descriptor']
            if 'direction' in nyct_info:
                direction = nyct_info['direction']
        
        # Look for Union Square stops in this trip
        for stop in trip_update['stop_time_update']:
            stop_id = stop.get('stop_id', '')
            
            # Check if this is a Union Square stop
            is_union_sq_stop = False
            for key, value in UNION_SQ_STOP_IDS.items():
                if stop_id == value:
                    is_union_sq_stop = True
                    direction_text = "Uptown/Bronx" if 'N' in stop_id else "Downtown/Brooklyn"
                    if route_id == 'L':
                        direction_text = "To 8 Ave" if 'N' in stop_id else "To Canarsie"
                    break
            
            if not is_union_sq_stop:
                continue
            
            # Get arrival time
            arrival_time = None
            if 'arrival' in stop and 'time' in stop['arrival']:
                arrival_time = stop['arrival']['time']
            
            # Only include future arrivals (within the next hour)
            if arrival_time:
                now = time.time()
                if arrival_time > now and arrival_time < now + 3600:  # Within the next hour
                    train_info = {
                        'route_id': route_id,
                        'direction': direction_text,
                        'arrival_time': arrival_time,
                        'arrival_time_formatted': format_time(arrival_time),
                        'minutes_away': int((arrival_time - now) / 60)
                    }
                    
                    # Get additional NYC subway specific info if available
                    if 'nyct_stop_time_update' in stop:
                        nyct_stop_info = stop['nyct_stop_time_update']
                        if 'scheduled_track' in nyct_stop_info:
                            train_info['track'] = nyct_stop_info['scheduled_track']
                            
                    upcoming_trains.append(train_info)
    
    # Sort by arrival time
    return sorted(upcoming_trains, key=lambda x: x['arrival_time'])

def get_union_square_trains():
    """Fetch and return Union Square train data as JSON"""
    timestamp = datetime.now()
    
    result = {
        "station": "Union Square",
        "timestamp": timestamp.isoformat(),
        "formatted_time": timestamp.strftime('%I:%M:%S %p, %B %d, %Y'),
        "lines": {
            "456": {
                "name": "4/5/6 Trains (Lexington Avenue Line)",
                "uptown": [],
                "downtown": []
            },
            "nqrw": {
                "name": "N/Q/R/W Trains (Broadway Line)",
                "uptown": [],
                "downtown": []
            },
            "l": {
                "name": "L Trains (Canarsie Line)",
                "westbound": [],
                "eastbound": []
            }
        },
        "all_trains": []
    }
    
    all_upcoming_trains = []
    
    # Fetch data for each feed
    for line_group, url in FEED_URLS.items():
        binary_data = fetch_mta_data(url)
        if binary_data:
            feed_dict = parse_gtfs_data(binary_data)
            if feed_dict:
                upcoming_trains = get_upcoming_trains_at_union_square(feed_dict)
                all_upcoming_trains.extend(upcoming_trains)
    
    # Sort by arrival time
    all_upcoming_trains = sorted(all_upcoming_trains, key=lambda x: x['arrival_time'])
    result["all_trains"] = all_upcoming_trains
    
    # Group trains by line and direction
    for train in all_upcoming_trains:
        route_id = train['route_id']
        direction = train['direction']
        
        if route_id in ['4', '5', '6']:
            if "Uptown" in direction:
                result["lines"]["456"]["uptown"].append(train)
            else:
                result["lines"]["456"]["downtown"].append(train)
        
        elif route_id in ['N', 'Q', 'R', 'W']:
            if "Uptown" in direction:
                result["lines"]["nqrw"]["uptown"].append(train)
            else:
                result["lines"]["nqrw"]["downtown"].append(train)
        
        elif route_id == 'L':
            if "8 Ave" in direction:
                result["lines"]["l"]["westbound"].append(train)
            else:
                result["lines"]["l"]["eastbound"].append(train)
    
    return result

# Example of how to use with FastAPI
# 
# from fastapi import FastAPI
# 
# app = FastAPI()
# 
# @app.get("/api/union-square-trains")
# async def union_square_trains():
#     result = get_union_square_trains()
#     return result