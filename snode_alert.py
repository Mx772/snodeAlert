#!/usr/bin/env python3

import sys
import time
import logging
import yaml
from haversine import haversine, Unit
import apprise
import sondehub
from collections import defaultdict

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('snodeAlert')

class SondeAlert:
    def __init__(self, config_path='config.yaml'):
        self.config = self.load_config(config_path)
        self.setup_logging()
        
        # Initialize apprise notification object
        self.apprise = apprise.Apprise()
        for url in self.config['notifications']['apprise_urls']:
            self.apprise.add(url)
            
        # Store user location as (lat, lon) tuple for haversine calculation
        self.user_location = (
            self.config['location']['latitude'],
            self.config['location']['longitude']
        )
        
        # Store radiosondes we've seen and already alerted on
        self.alerted_sondes = defaultdict(set)  # criteria_name -> set of sonde_ids
        self.last_positions = {}  # sonde_id -> position_data
        
        # Start the stream
        self.stream = None
    
    def load_config(self, config_path):
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            sys.exit(1)
    
    def setup_logging(self):
        """Configure logging based on config settings"""
        log_level = getattr(logging, self.config['app']['log_level'])
        logger.setLevel(log_level)
        logger.info(f"Log level set to {self.config['app']['log_level']}")
    
    def start(self):
        """Start monitoring for radiosondes"""
        logger.info(f"Starting SondeAlert - monitoring for radiosondes near {self.config['location']['name']}")
        logger.info(f"User location: {self.user_location}")
        
        # Print enabled alert criteria
        for criteria in self.config['criteria']:
            if criteria.get('enabled', True):
                logger.info(f"Alert criteria enabled: {criteria['name']}")
                for k, v in criteria.items():
                    if k not in ['name', 'enabled']:
                        logger.info(f"  {k}: {v}")
        
        # Start the SondeHub stream
        self.stream = sondehub.Stream(on_message=self.on_sonde_message)
        
        try:
            # Keep the main thread alive
            while True:
                time.sleep(self.config['app']['check_interval_seconds'])
        except KeyboardInterrupt:
            logger.info("Shutting down SondeAlert")
            if self.stream:
                self.stream.close()
    
    def on_sonde_message(self, message):
        """Callback for SondeHub stream - called whenever a new telemetry point is received"""
        try:
            # Basic validation
            if not isinstance(message, dict):
                return
            
            if 'serial' not in message or 'lat' not in message or 'lon' not in message:
                return
            
            # Extract basic sonde data
            sonde_id = message['serial']
            sonde_lat = float(message['lat'])
            sonde_lon = float(message['lon'])
            sonde_alt_m = float(message.get('alt', 0))  # Altitude in meters
            sonde_alt_ft = sonde_alt_m * 3.28084  # Convert to feet
            
            # Calculate distance from user
            sonde_location = (sonde_lat, sonde_lon)
            distance_km = haversine(self.user_location, sonde_location, unit=Unit.KILOMETERS)
            distance_miles = distance_km * 0.621371
            
            # Calculate climb rate if we have previous position data
            climb_rate = None
            if sonde_id in self.last_positions:
                prev_alt = self.last_positions[sonde_id].get('alt', 0)
                prev_time = self.last_positions[sonde_id].get('time', 0)
                if 'time' in message and prev_alt and prev_time:
                    time_diff = float(message['time']) - float(prev_time)
                    if time_diff > 0:  # Avoid division by zero
                        alt_diff = float(message.get('alt', 0)) - float(prev_alt)
                        climb_rate = alt_diff / time_diff  # m/s
            
            # Store the current position for future climb rate calculations
            self.last_positions[sonde_id] = message
            
            # Log the detection if in debug mode
            if logger.level <= logging.DEBUG:
                logger.debug(f"Sonde: {sonde_id}, Dist: {distance_miles:.1f} mi, Alt: {sonde_alt_ft:.0f} ft, Climb: {climb_rate if climb_rate is not None else 'unknown'} m/s")
            
            # Check against each alert criteria
            for criteria in self.config['criteria']:
                if not criteria.get('enabled', True):
                    continue
                    
                criteria_name = criteria['name']
                
                # Check if this sonde meets the criteria
                if self.sonde_meets_criteria(criteria, distance_miles, sonde_alt_ft, climb_rate):
                    # Check if we've already alerted for this sonde and criteria
                    if sonde_id not in self.alerted_sondes[criteria_name]:
                        self.send_alert(criteria_name, sonde_id, message, distance_miles, sonde_alt_ft, climb_rate)
                        self.alerted_sondes[criteria_name].add(sonde_id)
        
        except Exception as e:
            logger.error(f"Error processing sonde message: {e}")
    
    def sonde_meets_criteria(self, criteria, distance_miles, altitude_feet, climb_rate):
        """Check if a sonde meets the specified alert criteria"""
        # Check distance criteria
        if 'distance_miles' in criteria and distance_miles > criteria['distance_miles']:
            return False
            
        # Check altitude criteria if specified
        if 'altitude_feet_min' in criteria and altitude_feet < criteria['altitude_feet_min']:
            return False
            
        if 'altitude_feet_max' in criteria and altitude_feet > criteria['altitude_feet_max']:
            return False
            
        # Check climb rate criteria if specified and if we have climb rate data
        if climb_rate is not None:
            if 'climb_rate_min' in criteria and climb_rate < criteria['climb_rate_min']:
                return False
                
            if 'climb_rate_max' in criteria and climb_rate > criteria['climb_rate_max']:
                return False
        
        # If we passed all checks, the sonde meets the criteria
        return True
    
    def send_alert(self, criteria_name, sonde_id, data, distance_miles, altitude_feet, climb_rate):
        """Send an alert notification for a sonde that meets criteria"""
        # Build a detailed message
        title = f"🎈 SondeAlert: {criteria_name}"
        
        message = [
            f"Radiosonde {sonde_id} detected near {self.config['location']['name']}!",
            f"Distance: {distance_miles:.1f} miles",
            f"Altitude: {altitude_feet:.0f} ft"
        ]
        
        if climb_rate is not None:
            status = "descending" if climb_rate < 0 else "ascending"
            message.append(f"Vertical speed: {climb_rate:.1f} m/s ({status})")
        
        if 'subtype' in data:
            message.append(f"Type: {data['subtype']}")
        
        # Add a link to the SondeHub tracker
        tracker_url = f"https://sondehub.org/?sonde={sonde_id}"
        message.append(f"\nTrack it: {tracker_url}")
        
        # Join the message parts with newlines
        body = "\n".join(message)
        
        # Send the notification
        logger.info(f"Sending alert for sonde {sonde_id} - {criteria_name}")
        self.apprise.notify(title=title, body=body)


if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='SondeAlert - Radiosonde proximity alerting system')
    parser.add_argument('-c', '--config', default='config.yaml', help='Path to config file')
    args = parser.parse_args()
    
    # Start the application
    app = SondeAlert(config_path=args.config)
    app.start()
