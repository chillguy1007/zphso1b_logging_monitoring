from flask import Flask, render_template
from flask_socketio import SocketIO
import threading
import serial
import time
import json
from datetime import datetime
import requests
import os
import socket
import pynmea2
class DataLogger:
    def __init__(self):
        """Initialize the data logger with a new file for each session"""
        self.log_dir = 'sensor_logs'
        self.ensure_log_directory()
        self.current_file = self.create_new_logfile()
        self.data_buffer = []
        self.buffer_size = 1  # Write to file after these many readings
        
    def ensure_log_directory(self):
        """Create logs directory if it doesn't exist"""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
    
    def create_new_logfile(self):
        """Create a new log file with timestamp in name"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sensor_data_{timestamp}.json"
        filepath = os.path.join(self.log_dir, filename)
        
        # Create file with empty array
        with open(filepath, 'w') as f:
            json.dump([], f)
        
        return filepath
    
    def log_data(self, data):
        """Log sensor data to JSON file"""
        self.data_buffer.append(data)
        
        # Write to file when buffer is full
        if len(self.data_buffer) >= self.buffer_size:
            self.flush_buffer()
    
    def flush_buffer(self):
        """Write buffered data to file"""
        try:
            # Read existing data
            with open(self.current_file, 'r') as f:
                existing_data = json.load(f)
            
            # Append new data
            existing_data.extend(self.data_buffer)
            
            # Write back to file
            with open(self.current_file, 'w') as f:
                json.dump(existing_data, f, indent=2)
            
            # Clear buffer
            self.data_buffer = []
            
        except Exception as e:
            print(f"Error writing to log file: {e}")
    
    def close(self):
        """Flush remaining data and close logger"""
        if self.data_buffer:
            self.flush_buffer()

# Modify the main app.py to include the logger
data_logger = None

def check_wifi_connection():
    """Check if the Raspberry Pi is connected to WiFi"""
    try:
        # Try to connect to a reliable host
        socket.create_connection(("8.8.8.8", 53), timeout=1)
        return True
    except (socket.timeout, socket.error):
        return False

def initialize_app():
    global data_logger
    data_logger = DataLogger()
    return data_logger


app = Flask(__name__)
socketio = SocketIO(app)

# Global variable to store latest readings
latest_data = {}
historical_data = {
    'timestamps': [],
    'latitude': [],
    'longitude': [],
    'pm1': [],
    'pm25': [],
    'pm10': [],
    'co2': [],
    'voc': [],
    'temperature': [],
    'humidity': [],
    'ch2o': [],
    'co': [],
    'o3': [],
    'no2': []
}
# Maximum number of historical data points to keep
MAX_HISTORY = 2880

def send_to_thingspeak(data):
    """Send sensor data to ThingSpeak server"""
    try:
        # ThingSpeak payload
        # You can use up to 8 fields in free version
        payload = {
            'api_key': "TPUAJU336ISK78H6",
            'field1': data['temperature'],      # PM2.5
            'field2': data['humidity'],       # PM10
            'field3': data['pm2.5'],        # CO2
            'field4': data['pm10'], # Temperature
            'field5': data['co2'],    # Humidity
            'field6': data['co'],       # CH2O
            'field7': data['o3'],         # CO
            'field8': data['no2']          # O3
        }
        
        # Send data to ThingSpeak
        response = requests.post("https://api.thingspeak.com/update", data=payload, timeout=10)
        
        if response.status_code == 200:
            print("Data successfully sent to ThingSpeak")
        else:
            print(f"Failed to send data to ThingSpeak. Status code: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"Error sending data to ThingSpeak: {e}")
    except Exception as e:
        print(f"Unexpected error sending data to ThingSpeak: {e}")


def add_to_history(data):
    """Add new data point to historical data"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    
    historical_data['timestamps'].append(timestamp)
    historical_data['latitude'].append(data['latitude'])
    historical_data['longitude'].append(data['longitude'])
    historical_data['pm1'].append(data['pm1.0'])
    historical_data['pm25'].append(data['pm2.5'])
    historical_data['pm10'].append(data['pm10'])
    historical_data['co2'].append(data['co2'])
    historical_data['voc'].append(data['voc_grade'])
    historical_data['temperature'].append(data['temperature'])
    historical_data['humidity'].append(data['humidity'])
    historical_data['ch2o'].append(data['ch2o'])
    historical_data['co'].append(data['co'])
    historical_data['o3'].append(data['o3'])
    historical_data['no2'].append(data['no2'])
    
    # Keep only last MAX_HISTORY points
    if len(historical_data['timestamps']) > MAX_HISTORY:
        for key in historical_data:
            historical_data[key] = historical_data[key][-MAX_HISTORY:]

@app.route('/')
def index():
    return render_template('index.html')

def setup_uart():
    """Setup UART communication with the sensor"""
    try:
        return serial.Serial(
            port='/dev/ttyAMA0',
            baudrate=9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1
        )
    except serial.SerialException as e:
        print(f"Error opening serial port: {e}")
        return None

def calculate_checksum(data):
    """Calculate checksum for verification"""
    total = sum(data[1:25])
    return (~total + 1) & 0xFF

def parse_sensor_data(response, ser_gps):
    """Parse the 26-byte response"""
    if len(response) != 26 or response[0] != 0xFF or response[1] != 0x86:
        return None
    
    if calculate_checksum(response) != response[25]:
        print("Checksum verification failed")
        return None
    
    lat, lon = get_gps_position(ser_gps)

    return {
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'latitude': lat,
        'longitude': lon,
        'pm1.0': (response[2] * 256 + response[3]),
        'pm2.5': (response[4] * 256 + response[5]),
        'pm10': (response[6] * 256 + response[7]),
        'co2': (response[8] * 256 + response[9]),
        'voc_grade': response[10],
        'temperature': ((response[11] * 256 + response[12]) - 500) * 0.1,
        'humidity': (response[13] * 256 + response[14]),
        'ch2o': (response[15] * 256 + response[16]) * 0.001,
        'co': (response[17] * 256 + response[18]) * 0.1,
        'o3': (response[19] * 256 + response[20]) * 0.01,
        'no2': (response[21] * 256 + response[22]) * 0.01
    }

def read_sensor():
    """Read data from sensor and broadcast to websocket clients"""
    ser = setup_uart()
    ser_gps = init_gps()

    if not ser or not ser_gps:
        return
    
    command = bytearray([0xFF, 0x01, 0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x79])
    
    while True:
        try:
            ser.reset_input_buffer()
            ser.write(command)
            response = ser.read(26)
            
            if len(response) == 26:
                data = parse_sensor_data(response, ser_gps)
                if data:
                    # Log data to JSON file
                    if data_logger:
                        data_logger.log_data(data)

                    global latest_data
                    latest_data = data
                    add_to_history(data)
                    socketio.emit('sensor_update', data)
                    # if check_wifi_connection():
                    #     send_to_thingspeak(data)

                    time.sleep(5)
            
        except Exception as e:
            print(f"Error reading sensor: {e}")
            time.sleep(1)

def init_gps(port='/dev/ttyAMA1', baudrate=115200):
    """Initialize GPS serial connection"""
    try:
        return serial.Serial(port=port, baudrate=baudrate, timeout=1)
    except serial.SerialException as e:
        print(f"Error initializing GPS: {e}")
        return None

def convert_to_degrees(nmea_value):
    """Convert NMEA coordinate format to decimal degrees"""
    try:
        value = float(nmea_value)
        degrees = int(value / 100)
        minutes = value - (degrees * 100)
        return degrees + (minutes / 60)
    except (ValueError, TypeError):
        return None

def get_gps_position(ser):
    """
    Get latitude and longitude from GPS
    
    Args:
        ser: Serial connection object
    
    Returns:
        tuple: (latitude, longitude) in decimal degrees, or (None, None) if invalid
    """
    try:
        # attempts =0
        # while attempts<5:
        while True:
            line = ser.readline().decode('ascii', errors='replace')
            if line.startswith('$GNRMC'):
                msg = pynmea2.parse(line)

                if msg.status == 'A':  # If status is valid
                    # Convert latitude
                    lat = convert_to_degrees(msg.lat)
                    if lat is not None and msg.lat_dir == 'S':
                        lat = -lat
                        
                    # Convert longitude
                    lon = convert_to_degrees(msg.lon)
                    if lon is not None and msg.lon_dir == 'W':
                        lon = -lon
                        
                    return lat, lon

            # attempts += 1
            # time.sleep(0.2)
        # print("cannot lock")
        # return None, None
    
    except (serial.SerialException, pynmea2.ParseError) as e:
        print(f"GPS error: {e}")
        return None, None


@socketio.on('connect')
def handle_connect():
    """Send historical data when a client connects"""
    socketio.emit('historical_data', historical_data)
    if latest_data:
        socketio.emit('sensor_update', latest_data)

if __name__ == '__main__':
    data_logger = initialize_app()
    # Start sensor reading in a separate thread
    # sensor_thread = threading.Thread(target=read_sensor, daemon=True)
    # sensor_thread.start()
    
    # # Run the web server
    # socketio.run(app, host='0.0.0.0', port=8080, debug=False)

    try:
        # Start sensor reading in a separate thread
        sensor_thread = threading.Thread(target=read_sensor, daemon=True)
        sensor_thread.start()
        
        # Run the web server
        socketio.run(app, host='0.0.0.0', port=8080, debug=False)
    finally:
        # Ensure any buffered data is written before exit
        if data_logger:
            data_logger.close()
