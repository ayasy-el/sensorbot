import os
import sys
import logging
from datetime import datetime, timedelta
import pytz


from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from influxdb_client import InfluxDBClient
from influxdb_client.client.query_api import QueryApi
from influxdb_client.client.write_api import SYNCHRONOUS


# Explicitly add the script's directory to Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# Add dotenv import with Windows-specific handling
try:
    from dotenv import load_dotenv, dotenv_values
except ImportError:
    print("python-dotenv not installed. Please install it using 'pip install python-dotenv'")
    sys.exit(1)

# Add Groq import
try:
    from groq import Groq
except ImportError:
    print("Groq library not installed. Please install it using 'pip install groq'")
    sys.exit(1)

# Windows-friendly .env loading
def load_env_file():
    # Try multiple possible .env file locations
    env_paths = [
        os.path.join(script_dir, '.env'),
        os.path.join(script_dir, '.env.txt'),
        os.path.join(os.getcwd(), '.env'),
    ]
    
    env_vars = {}
    for path in env_paths:
        if os.path.exists(path):
            try:
                # Read .env file manually for Windows compatibility
                with open(path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            # Remove quotes if present
                            value = value.strip().strip('\'"')
                            os.environ[key.strip()] = value
                print(f"Loaded environment variables from {path}")
                break
            except Exception as e:
                print(f"Error reading {path}: {e}")
    
    return env_vars

# Load environment variables
load_env_file()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# InfluxDB Configuration
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "your-influxdb-token")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "your-org")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "my-bucket")
SENSOR_LOCATION = os.getenv("SENSOR_LOCATION", "Lokasi Tidak Diketahui")

# Groq AI Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

def get_aqi_category(aqi):
    """Get the AQI category based on the provided value."""
    if 0 <= aqi <= 50:
        return "Baik"
    elif 51 <= aqi <= 100:
        return "Sedang"
    elif 101 <= aqi <= 150:
        return "Tidak Sehat untuk Golongan Sensitif"
    elif 151 <= aqi <= 200:
        return "Tidak Sehat"
    elif 201 <= aqi <= 300:
        return "Sangat Tidak Sehat"
    elif aqi >= 301:
        return "Berbahaya"
    else:
        return "Nilai AQI tidak valid"

def get_uv_index(uv_value):
    """Convert UV value in mV to UV index."""
    if uv_value < 50:
        return 0
    elif uv_value < 227:
        return 1
    elif uv_value < 318:
        return 2
    elif uv_value < 408:
        return 3
    elif uv_value < 503:
        return 4
    elif uv_value < 606:
        return 5
    elif uv_value < 696:
        return 6
    elif uv_value < 795:
        return 7
    elif uv_value < 881:
        return 8
    elif uv_value < 976:
        return 9
    elif uv_value < 1079:
        return 10
    elif uv_value < 1170:
        return 11
    else:
        return 12

def get_uv_category(uv_value):
    """Categorize UV index."""
    uv_index = get_uv_index(uv_value)
    if uv_index == 0:
        return "Nihil"
    elif uv_index <= 2:
        return "Rendah"
    elif uv_index <= 5:
        return "Sedang"
    elif uv_index <= 7:
        return "Tinggi"
    else:
        return "Sangat Tinggi"

def get_sensor_data():
    """Retrieve sensor data from InfluxDB."""
    try:
        # Create InfluxDB client
        client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        query_api = client.query_api()

        # Get current time in WIB (Jakarta) timezone
        wib = pytz.timezone('Asia/Jakarta')
        now = datetime.now(wib)
        start_time = now - timedelta(minutes=10)

        # Construct query
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: {start_time.isoformat()}, stop: {now.isoformat()})
            |> filter(fn: (r) => 
                r["_measurement"] == "mqtt_consumer" and 
                (r["topic"] == "sensor/auto/temperature" or 
                 r["topic"] == "sensor/bmp/pressure" or 
                 r["topic"] == "sensor/dht/humidity" or 
                 r["topic"] == "sensor/mq135/ppm" or 
                 r["topic"] == "sensor/uv/voltage")
            )
            |> last()
        '''

        # Execute query
        result = query_api.query(query)

        # Process results
        data = {}
        for table in result:
            for record in table.records:
                topic = record.values.get('topic', '')
                value = record.get_value()
                
                if 'temperature' in topic:
                    data['temperature'] = round(value, 1)
                elif 'pressure' in topic:
                    data['pressure'] = round(value, 1)
                elif 'humidity' in topic:
                    data['humidity'] = round(value, 1)
                elif 'uv/voltage' in topic:
                    # Convert voltage to UV index (example conversion)
                    uv_index = round(value, 1)  # Adjust multiplier based on your sensor
                    data['uv'] = {
                        'value': get_uv_index(uv_index),
                        'category': get_uv_category(uv_index)
                    }
                elif 'mq135/ppm' in topic:
                    data['ppm'] = {
                        'value': round(value, 1),
                        'category': get_aqi_category(round(value, 1))
                    }

        # Close client
        client.close()

        return data
    except Exception as e:
        logger.error(f"Error retrieving sensor data: {e}")
        return None

def generate_ai_conclusion(sensor_data):
    """
    Generate a conclusion using Groq AI based on sensor data.
    
    Args:
        sensor_data (dict): Dictionary containing sensor readings
    
    Returns:
        str: AI-generated conclusion
    """
    if not GROQ_API_KEY:
        return "Kesimpulan AI tidak tersedia (API key tidak dikonfigurasi)"
    
    try:
        # Initialize Groq client
        client = Groq(api_key=GROQ_API_KEY)
        now = datetime.now(pytz.timezone('Asia/Jakarta'))
        
        # Prepare prompt with sensor data
        prompt = f"""Berikan kesimpulan singkat dan rekomendasi berdasarkan data sensor berikut:
Tanggal {now.strftime('%d/%m/%Y')} | Jam {now.strftime('%H:%M')} 
- Suhu: {sensor_data.get('temperature', 'N/A')}°C
- Kelembapan: {sensor_data.get('humidity', 'N/A')}%
- Tekanan: {sensor_data.get('pressure', 'N/A')} hPa
- UV : {sensor_data.get('uv', {}).get('value', 'N/A')} (Kategori: {sensor_data.get('uv', {}).get('category', 'N/A')})
- CO: {sensor_data.get('ppm', 'N/A').get('value', 'N/A')} ppm (Kategori: {sensor_data.get('ppm', 'N/A').get('category', 'N/A')})

Tulis dalam 1 kalimat sangat singkat padat jelas, fokus pada kondisi lingkungan dan saran praktis. MENGGUNAKAN Bahasa Indonesia!"""
        
        # Generate conclusion
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Kamu adalah asisten pakar yang membantu menganalisis kondisi lingkungan berdasarkan data sensor."},
                {"role": "user", "content": prompt}
            ],
            model="gemma2-9b-it"
        )
        
        # Extract and return conclusion
        conclusion = chat_completion.choices[0].message.content.strip()
        return conclusion
    
    except Exception as e:
        logger.error(f"Error generating AI conclusion: {e}")
        return "Kesimpulan AI tidak dapat dibuat saat ini."

def format_sensor_message(data):
    """Format sensor data into a readable Telegram message."""
    if not data:
        return "Maaf, tidak dapat mengambil data sensor saat ini."

    now = datetime.now(pytz.timezone('Asia/Jakarta'))
    
    # Generate AI conclusion
    ai_conclusion = generate_ai_conclusion(data)
    
    message = f"""📊 Kondisi Udara
📅 {now.strftime('%d/%m/%Y')} | ⏰ {now.strftime('%H:%M')} | 📍 {SENSOR_LOCATION}  
🌡 Suhu: {data.get('temperature', '---')} °C  
☀ UV: {data.get('uv', {}).get('value', '---')} (Kategori: {data.get('uv', {}).get('category', '---')})  
💧 Kelembapan: {data.get('humidity', '---')} %  
🔽 Tekanan: {data.get('pressure', '---')} hPa 
💨 CO: {data.get('ppm', 'N/A').get('value', 'N/A')} ppm (Kategori: {data.get('ppm', 'N/A').get('category', 'N/A')})

📝 Kesimpulan: {ai_conclusion}"""

    return message

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /info command to display sensor information."""
    # Send initial processing message
    processing_message = await update.message.reply_text("Mengambil informasi sensor...")
    
    try:
        # Get sensor data
        sensor_data = get_sensor_data()
        
        # Format sensor message
        message = format_sensor_message(sensor_data)
        
        # Edit the previous message with sensor information
        await processing_message.edit_text(message)
    except Exception as e:
        # Handle any errors during data retrieval or message sending
        logger.error(f"Error in info_command: {e}")
        await processing_message.edit_text("Maaf, tidak dapat mengambil data sensor saat ini. Silakan coba lagi nanti.")

def influxdb_connection():
    """
    Connect to InfluxDB and print connection details.
    
    Returns:
    - Boolean indicating connection success
    - Error message if connection fails
    """
    try:
        # Create InfluxDB client
        client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        
        # Test connection by listing buckets
        buckets_api = client.buckets_api()
        buckets = buckets_api.find_buckets()
        
        # Print connection details
        print("\n--- InfluxDB Connection Test ---")
        print(f"Connection URL: {INFLUXDB_URL}")
        print(f"Organization: {INFLUXDB_ORG}")
        print(f"Available Buckets:")
        for bucket in buckets.buckets:
            print(f"  - {bucket.name}")
        
        # Close the client
        client.close()
        
        print("InfluxDB Connection: Successful ✅")
        return True, None
    
    except Exception as e:
        print("\n--- InfluxDB Connection Test Failed ---")
        print(f"Connection URL: {INFLUXDB_URL}")
        print(f"Organization: {INFLUXDB_ORG}")
        print(f"Error: {e}")
        print("InfluxDB Connection: Failed ❌")
        return False, str(e)

def main() -> None:
    """Run the bot."""
    # Test InfluxDB connection first
    connection_success, error_message = influxdb_connection()
    
    # Exit if connection fails
    if not connection_success:
        print("Cannot start bot due to InfluxDB connection failure.")
        sys.exit(1)
    
    # Create the Application and pass it your bot's token
    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN", "your-telegram-bot-token")).build()

    # Register handlers
    application.add_handler(CommandHandler("info", info_command))

    # Start the Bot
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
