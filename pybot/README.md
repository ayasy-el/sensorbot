# Sensor Telegram Bot

## Overview
This Telegram bot retrieves and displays environmental sensor data from InfluxDB.

## Prerequisites
- Python 3.8+
- InfluxDB
- Telegram Bot Token

## Setup

1. Clone the repository
2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Configure Environment Variables
- Copy `.env.example` to `.env`
- Edit `.env` with your actual configuration
```bash
# Copy example file
cp .env.example .env

# Edit .env with your favorite text editor
nano .env  # or use any text editor
```

Key configurations:
- `TELEGRAM_BOT_TOKEN`: Your Telegram Bot Token from BotFather
- `INFLUXDB_URL`: InfluxDB server URL
- `INFLUXDB_TOKEN`: InfluxDB authentication token
- `INFLUXDB_ORG`: Your InfluxDB organization name
- `INFLUXDB_BUCKET`: InfluxDB bucket name
- `SENSOR_LOCATION`: Description of sensor location

5. Run the Bot
```bash
python sensor_bot.py
```

## Configuration
- Modify `INFLUXDB_URL`, `INFLUXDB_ORG`, and `INFLUXDB_BUCKET` in the script as needed
- Adjust sensor data processing logic in `get_sensor_data()` function

## Features
- Retrieve real-time sensor data
- UV index categorization
- Formatted sensor information message

## Supported Sensors
- Temperature (BMP)
- Pressure (BMP)
- Humidity (DHT)
- UV Voltage
