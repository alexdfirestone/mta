import requests
import time
import json
from google.transit import gtfs_realtime_pb2
#from protobuf_to_dict import protobuf_to_dict
from google.protobuf.json_format import MessageToDict
from datetime import datetime
import os
import logging


# Custom protobuf to dict converter that works with Python 3.11
def protobuf_to_dict(message):
    result_dict = {}
    for field, value in message.ListFields():
        if field.label == field.LABEL_REPEATED:
            result_dict[field.name] = [_convert_value(v) for v in value]
        else:
            result_dict[field.name] = _convert_value(value)
    return result_dict

def _convert_value(value):
    if hasattr(value, 'ListFields'):
        return protobuf_to_dict(value)
    elif isinstance(value, list) and value and hasattr(value[0], 'ListFields'):
        return [protobuf_to_dict(v) for v in value]
    else:
        return value

# Configure logging
logger = logging.getLogger(__name__)

class MTAService:
    def __init__(self, config_path):
        """Initialize the MTA service with a configuration file."""
        # Load configuration
        self.load_config(config_path)
        logger.info(f"MTA service initialized with config from {config_path}")
        
    def load_config(self, config_path):
        """Load station configuration from a JSON file."""
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
                
            # Extract needed configuration
            self.stations = self.config.get('STATIONS', {})
            self.feed_urls = self.config.get('FEED_URLS', {})
            self.target_routes = self.config.get('TARGET_ROUTES', [])
            self.api_key = self.config.get('API_KEY', os.environ.get('MTA_API_KEY'))
            self.feed_to_routes = self.config.get('FEED_TO_ROUTES', {})
            
            if not self.api_key:
                logger.warning("No MTA API key found in config or environment variables")
                
        except Exception as e:
            logger.error(f"Error loading configuration from {config_path}: {str(e)}")
            raise
            
    def fetch_mta_data(self, url):
        """Fetch data from MTA API with proper authentication."""
        headers = {}
        if self.api_key:
            headers['x-api-key'] = self.api_key
            
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"Error fetching MTA data: HTTP {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Exception fetching MTA data: {str(e)}")
            return None

    def parse_gtfs_data(self, binary_data):
        """Parse GTFS binary data into readable format."""
        if not binary_data:
            return None
            
        feed = gtfs_realtime_pb2.FeedMessage()
        try:
            feed.ParseFromString(binary_data)
        except Exception as e:
            logger.error(f"Error parsing GTFS data: {str(e)}")
            return None
        
        # Convert to dictionary for easier handling
        return protobuf_to_dict(feed)

    def format_time(self, timestamp):
        """Format Unix timestamp to readable time."""
        return datetime.fromtimestamp(timestamp).strftime('%I:%M:%S %p')

    def get_upcoming_trains_at_station(self, feed_dict, station_id):
        """Extract upcoming trains arriving at a specific station."""
        if not feed_dict or 'entity' not in feed_dict:
            return []
        
        if station_id not in self.stations:
            logger.warning(f"Station {station_id} not found in configuration")
            return []
            
        station_config = self.stations[station_id]
        stop_ids = station_config.get('STOP_IDS', {})
        
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
            if route_id not in self.target_routes:
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
            
            # Look for station stops in this trip
            for stop in trip_update['stop_time_update']:
                stop_id = stop.get('stop_id', '')
                
                # Check if this is a station stop
                is_station_stop = False
                direction_text = None
                
                for key, value in stop_ids.items():
                    if stop_id == value:
                        is_station_stop = True
                        # Determine direction based on the configuration
                        directions = station_config.get('DIRECTIONS', {})
                        for direction_key, direction_config in directions.items():
                            if key in direction_config.get('stop_id_keys', []):
                                direction_text = direction_config.get('display_name', direction_key)
                                break
                        break
                
                if not is_station_stop:
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
                            'arrival_time_formatted': self.format_time(arrival_time),
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

    def get_station_trains(self, station_id):
        """Fetch and return train data for a specific station."""
        if station_id not in self.stations:
            logger.warning(f"Station {station_id} not found in configuration")
            return {"error": f"Station {station_id} not found in configuration"}
            
        station_config = self.stations[station_id]
        timestamp = datetime.now()
        
        result = {
            "station": station_config.get('DISPLAY_NAME', station_id),
            "timestamp": timestamp.isoformat(),
            "formatted_time": timestamp.strftime('%I:%M:%S %p, %B %d, %Y'),
            "lines": {},
            "all_trains": []
        }
        
        # Initialize lines structure based on configuration
        line_groups = station_config.get('LINE_GROUPS', {})
        for line_group, line_config in line_groups.items():
            result["lines"][line_group] = {
                "name": line_config.get('display_name', line_group)
            }
            # Initialize directions for this line group
            for direction_key in station_config.get('DIRECTIONS', {}).keys():
                result["lines"][line_group][direction_key] = []
        
        all_upcoming_trains = []
        
        # Determine which feeds to fetch based on the station configuration
        station_routes = station_config.get('ROUTES', [])
        feeds_to_fetch = set()
        
        # Map routes to feeds
        for route in station_routes:
            for feed_id, routes in self.feed_to_routes.items():
                if route in routes:
                    feeds_to_fetch.add(feed_id)
        
        # Fetch data for required feeds
        for feed_id in feeds_to_fetch:
            if feed_id in self.feed_urls:
                url = self.feed_urls[feed_id]
                binary_data = self.fetch_mta_data(url)
                if binary_data:
                    feed_dict = self.parse_gtfs_data(binary_data)
                    if feed_dict:
                        upcoming_trains = self.get_upcoming_trains_at_station(feed_dict, station_id)
                        all_upcoming_trains.extend(upcoming_trains)
                        logger.info(f"Fetched {len(upcoming_trains)} trains for {station_id} from feed {feed_id}")
        
        # Sort by arrival time
        all_upcoming_trains = sorted(all_upcoming_trains, key=lambda x: x['arrival_time'])
        result["all_trains"] = all_upcoming_trains
        
        # Group trains by line and direction
        for train in all_upcoming_trains:
            route_id = train['route_id']
            direction = train['direction']
            
            # Find which line group this route belongs to
            for line_group, line_config in line_groups.items():
                if route_id in line_config.get('routes', []):
                    # Find which direction this train is going
                    for direction_key, direction_config in station_config.get('DIRECTIONS', {}).items():
                        if direction == direction_config.get('display_name'):
                            if direction_key in result["lines"][line_group]:
                                result["lines"][line_group][direction_key].append(train)
                                break
        
        return result


# Initialize service with config path (can be overridden with environment variable)
config_path = os.environ.get("MTA_CONFIG_PATH", "mta_data/mta_config.json")
_service = None

def get_service():
    """Get or initialize the MTA service singleton."""
    global _service
    if _service is None:
        try:
            _service = MTAService(config_path)
        except Exception as e:
            logger.error(f"Failed to initialize MTA service: {e}")
            raise
    return _service

# Function to get Union Square trains (for compatibility with existing code)
def get_union_square_trains():
    """Get train data for Union Square station."""
    service = get_service()
    return service.get_station_trains("union_square")

# Functions for other stations can be added as needed
def get_times_square_trains():
    """Get train data for Times Square station."""
    service = get_service()
    return service.get_station_trains("times_square")

def get_station_trains(station_id):
    """Generic function to get train data for any station."""
    service = get_service()
    return service.get_station_trains(station_id)