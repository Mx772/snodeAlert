# SondeAlert

A Python application that monitors radiosondes (weather balloons) and sends notifications when they meet specific criteria relative to your location.

## Features

- Real-time monitoring of radiosondes worldwide using SondeHub data
- Customizable alert criteria based on:
  - Distance from your location
  - Altitude
  - Vertical speed (climb/descent rate)
- Notifications via Discord using Apprise (expandable to other platforms)
- Configurable via YAML file

## Example

![image](https://github.com/user-attachments/assets/29ef526d-986a-428d-82ea-f60021018e29)


## Requirements

- Python 3.7+
- Required packages (see requirements.txt):
  - sondehub
  - apprise
  - pyyaml
  - haversine

## Setup

1. Clone the repository:
   ```
   git clone https://your-repository-url/snodeAlert.git
   cd snodeAlert
   ```

2. Create a Python virtual environment and install dependencies:
   ```
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Configure your Discord webhook:
   - Create a webhook in your Discord server settings
   - Update the `config.yaml` file with your webhook URL

4. Update the `config.yaml` file with your location and alert criteria

## Configuration

Edit the `config.yaml` file to customize your settings:

```yaml
# User location settings
location:
  latitude: 40.7128  # Replace with your latitude
  longitude: -74.0060  # Replace with your longitude
  name: "New York City"  # Location name for notifications

# Notification settings
notifications:
  apprise_urls:
    - "discord://webhook_id/webhook_token"  # Replace with your Discord webhook URL

# Alert criteria
criteria:
  - name: "Nearby Low Altitude"  # Name for this alert condition
    distance_miles: 50  # Maximum distance in miles
    altitude_feet_max: 1000  # Maximum altitude in feet
    climb_rate_max: 0  # Maximum climb rate in m/s (negative means descending)
    enabled: true
  
  - name: "Nearby Any Altitude" 
    distance_miles: 30  # Maximum distance in miles
    enabled: true

# Application settings
app:
  check_interval_seconds: 10  # How often to check for radiosondes meeting criteria
  log_level: "INFO"  # Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
```

## Usage

Activate the virtual environment and run the application:

```bash
source .venv/bin/activate
python snode_alert.py
```

Optionally, specify a different config file:

```bash
python snode_alert.py --config my_config.yaml
```

## How It Works

The application connects to the SondeHub data stream to receive real-time updates about radiosondes around the world. When a radiosonde meeting your specified criteria is detected, the application sends a notification through Discord (or other configured Apprise services).

## Extending

### Additional Notification Methods

You can use any notification method supported by [Apprise](https://github.com/caronc/apprise), including:

- Telegram
- Slack
- Email
- SMS
- And many more

Simply add the appropriate URL to the `apprise_urls` list in your config file.

## License

MIT License
