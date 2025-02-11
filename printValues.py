import serial
import time

# UART setup
SERIAL_PORT = "/dev/ttyAMA1"  # Default UART port on Raspberry Pi
BAUDRATE = 9600  # Baudrate as per the sensor specification

# Command to send to the sensor
COMMAND = bytes([0xFF, 0x01, 0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x79])

def parse_sensor_data(data):
    """
    Parses the 26-byte data received from the sensor and prints the values.
    """
    if len(data) != 26:
        print(f"Invalid data length: {len(data)} bytes received.")
        return

    # Parse the values as per the datasheet
    PM1 = data[2] * 256 + data[3]
    PM2_5 = data[4] * 256 + data[5]
    PM10 = data[6] * 256 + data[7]
    CO2 = data[8] * 256 + data[9]
    VOC = data[10]
    TEMP = ((data[11] * 256 + data[12]) - 500) * 0.1
    HUM = data[13] * 256 + data[14]
    CH2O = (data[15] * 256 + data[16]) * 0.001
    CO = (data[17] * 256 + data[18]) * 0.1
    O3 = (data[19] * 256 + data[20]) * 0.01
    NO2 = (data[21] * 256 + data[22]) * 0.01

    # Print the parsed values
    print("Parsed Sensor Data:")
    print(f"PM1   : {PM1} µg/m³")
    print(f"PM2.5 : {PM2_5} µg/m³")
    print(f"PM10  : {PM10} µg/m³")
    print(f"CO2   : {CO2} ppm")
    print(f"VOC   : {VOC} grade")
    print(f"TEMP  : {TEMP:.1f} °C")
    print(f"HUM   : {HUM} %RH")
    print(f"CH2O  : {CH2O:.3f} mg/m³")
    print(f"CO    : {CO:.1f} ppm")
    print(f"O3    : {O3:.2f} ppm")
    print(f"NO2   : {NO2:.2f} ppm")
    print("-" * 30)

# Open the serial connection
try:
    ser = serial.Serial(
        port=SERIAL_PORT,
        baudrate=BAUDRATE,
        timeout=2
    )
    print(f"Serial connection established on {SERIAL_PORT} at {BAUDRATE} baudrate.")
except serial.SerialException as e:
    print(f"Error initializing serial connection: {e}")
    exit(1)

# Communicating with the sensor
while True:
    try:
        # Send the command
        ser.write(COMMAND)
        print(f"Command sent: {COMMAND.hex()}")

        # Wait for the sensor to process the command
        time.sleep(0.1)

        # Read 26 bytes from the sensor
        response = ser.read(26)
        parse_sensor_data(response)

    except Exception as e:
        print(f"Error during communication: {e}")
    finally:
        time.sleep(10)
