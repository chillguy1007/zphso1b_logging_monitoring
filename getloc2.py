import serial
import pynmea2
import time

# Configure the serial port
ser = serial.Serial(
    port='/dev/ttyAMA1',  # or '/dev/ttyS0' depending on your Pi model
    baudrate=115200,        # Common baud rate for GPS modules
    timeout=1
)

def convert_to_degrees(nmea_value):
    # Convert NMEA latitude/longitude format to decimal degrees
    value = float(nmea_value)
    degrees = int(value / 100)
    minutes = value - (degrees * 100)
    decimal_degrees = degrees + (minutes / 60)
    return decimal_degrees

while True:
    try:
        # Read a line from the GPS module
        line = ser.readline().decode('ascii', errors='replace')
        
        # Check if it's a GNRMC sentence
        if line.startswith('$GNRMC'):
            msg = pynmea2.parse(line)
            
            if msg.status == 'A':  # If status is valid
                # Get latitude and longitude
                lat = convert_to_degrees(msg.lat)
                if msg.lat_dir == 'S':
                    lat = -lat
                    
                lon = convert_to_degrees(msg.lon)
                if msg.lon_dir == 'W':
                    lon = -lon
                
                print(f"Latitude: {lat:.6f}°, Longitude: {lon:.6f}°")
                print(f"Time: {msg.timestamp}, Speed: {msg.spd_over_grnd} knots")
            else:
                print("GPS signal not valid")
            
    except serial.SerialException as e:
        print(f"Serial port error: {e}")
        time.sleep(1)
    except pynmea2.ParseError as e:
        print(f"Parse error: {e}")
        continue
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(1)
        continue
