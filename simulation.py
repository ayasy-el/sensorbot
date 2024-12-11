import paho.mqtt.client as mqtt
import time
import random

# MQTT settings
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC_UV = "sensor/uv/voltage"
MQTT_TOPIC_BMP_TEMP = "sensor/bmp/temperature"
MQTT_TOPIC_AUTO_TEMP = "sensor/auto/temperature"
MQTT_TOPIC_BMP_PRESS = "sensor/bmp/pressure"
MQTT_TOPIC_BMP_ALT = "sensor/bmp/altitude"
MQTT_TOPIC_DHT_TEMP = "sensor/dht/temperature"
MQTT_TOPIC_DHT_HUMID = "sensor/dht/humidity"
MQTT_TOPIC_MQ135_PPM = "sensor/mq135/ppm"

# Define temperature, humidity, and UV voltage ranges for each condition
conditions = {
    'cold': {'temp_range': (-10, 10), 'humidity_range': (20, 40), 'uv_range': (0, 300)},
    'cool': {'temp_range': (10, 20), 'humidity_range': (40, 60), 'uv_range': (300, 600)},
    'moderate': {'temp_range': (20, 30), 'humidity_range': (50, 70), 'uv_range': (600, 900)},
    'hot': {'temp_range': (30, 40), 'humidity_range': (60, 80), 'uv_range': (900, 1200)}
}

# Prompt user for simulation condition
condition = ''
while condition not in conditions:
    condition = input("Select simulation condition (cold, cool, moderate, hot): ").lower()
    if condition not in conditions:
        print("Invalid condition. Please choose from cold, cool, moderate, hot.")

# Set ranges based on the selected condition
temp_min, temp_max = conditions[condition]['temp_range']
humidity_min, humidity_max = conditions[condition]['humidity_range']
uv_min, uv_max = conditions[condition]['uv_range']

# Initialize sensor simulation variables
bmp_temperature = random.uniform(temp_min, temp_max)
bmp_pressure = 1013.25
bmp_altitude = 0.0
dht_temperature = random.uniform(temp_min, temp_max)
dht_humidity = random.uniform(humidity_min, humidity_max)
mq135_ppm = random.randint(0, 400)
uv_voltage_mV = random.uniform(uv_min, uv_max)

# Track previous DHT temperature
previous_dht_temperature = dht_temperature

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
    else:
        print(f"Failed to connect, return code {rc}")

client = mqtt.Client()
client.on_connect = on_connect
client.connect(MQTT_BROKER, MQTT_PORT, 60)

# Start the loop
client.loop_start()

def bmp_pressure_to_altitude(pressure):
    """Calculate altitude based on pressure."""
    return 44330.0 * (1.0 - (pressure / 1013.25) ** (1.0 / 5.255))

try:
    while True:
        # Simulate BMP280 temperature based on condition
        bmp_temperature += random.uniform(-0.2, 0.2)
        bmp_temperature = max(temp_min, min(temp_max, bmp_temperature))
        
        # Simulate BMP280 pressure
        bmp_pressure += random.uniform(-1.0, 1.0)
        bmp_pressure = max(950.0, min(1050.0, bmp_pressure))
        bmp_altitude = bmp_pressure_to_altitude(bmp_pressure)
        
        # Simulate DHT11 temperature based on condition
        dht_temperature += random.uniform(-0.5, 0.5)
        dht_temperature = max(temp_min, min(temp_max, dht_temperature))
        
        # Calculate temperature change
        temp_change = dht_temperature - previous_dht_temperature
        
        # Adjust humidity based on temperature change and random fluctuation
        humidity_change = 0.1 * temp_change + random.uniform(-1.0, 1.0)
        dht_humidity += humidity_change
        dht_humidity = max(humidity_min, min(humidity_max, dht_humidity))
        
        # Limit humidity change per iteration
        dht_humidity += min(max(humidity_change, -1.0), 1.0)
        
        # Simulate MQ135 readings
        mq135_ppm = random.randint(0, 400)
        
        # Simulate UV voltage with small fluctuations
        uv_voltage_mV += random.uniform(-5.0, 5.0)
        uv_voltage_mV = max(uv_min, min(uv_max, uv_voltage_mV))
        
        # Update previous DHT temperature
        previous_dht_temperature = dht_temperature
        
        # Publish data
        client.publish(MQTT_TOPIC_UV, "{:.2f}".format(uv_voltage_mV))
        client.publish(MQTT_TOPIC_BMP_TEMP, "{:.2f}".format(bmp_temperature))
        client.publish(MQTT_TOPIC_AUTO_TEMP, "{:.2f}".format(bmp_temperature))
        client.publish(MQTT_TOPIC_BMP_PRESS, "{:.2f}".format(bmp_pressure))
        client.publish(MQTT_TOPIC_BMP_ALT, "{:.2f}".format(bmp_altitude))
        client.publish(MQTT_TOPIC_DHT_TEMP, "{:.2f}".format(dht_temperature))
        client.publish(MQTT_TOPIC_DHT_HUMID, "{:.2f}".format(dht_humidity))
        client.publish(MQTT_TOPIC_MQ135_PPM, "{:.2f}".format(mq135_ppm))
        
        # Print to console
        print(f"UV Voltage: {uv_voltage_mV:.2f} mV")
        print(f"BMP280 - Temp: {bmp_temperature:.2f}°C, Pressure: {bmp_pressure:.2f} hPa, Altitude: {bmp_altitude:.2f} m")
        print(f"DHT11 - Temp: {dht_temperature:.2f}°C, Humidity: {dht_humidity:.2f}%")
        print(f"MQ135 - PPM: {mq135_ppm:.2f} PPM")
        
        time.sleep(2)
except KeyboardInterrupt:
    print("Simulation stopped.")
finally:
    client.loop_stop()
    client.disconnect()