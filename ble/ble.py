import serial
import re
import os
import glob
import json
import threading
import time
from collections import defaultdict, deque

CONFIG_FILE = "config.json"
BAUD_RATE = 115200

AZIMUTH_PATTERN = re.compile(r'\+UUDF:([0-9A-Fa-f]{12}),(-?\d+),(-?\d+),(-?\d+),(\d+),(\d+),"([0-9A-Fa-f]{12})","",(\d+),(\d+)')
DIRECT_PATTERN = re.compile(r'\+UUDF:([0-9A-Fa-f]{12}),(-?\d+),(-?\d+),(-?\d+),(\d+),(\d+),"([0-9A-Fa-f]{12})","",(\d+),(\d+)')


tag_ids = []

# Initialize dictionaries to hold the latest timestamp, readout time, and frequency data for each station
freq_data = defaultdict(lambda: {
    "last_timestamp": None,
    "frequencies": deque(maxlen=10),  # stores recent frequencies for averaging
})

def calculate_frequency(identifier, timestamp):
    data = freq_data[identifier]
    
    # Calculate frequency based on timestamp
    if data["last_timestamp"] is not None:
        delta_time = (timestamp - data["last_timestamp"]) / 1000.0  # timestamp difference in seconds
        if delta_time > 0:
            data["frequencies"].append(1 / delta_time)
    
    # Update the last timestamp and readout time
    data["last_timestamp"] = timestamp

    # Average frequency
    if data["frequencies"]:
        avg_frequency = sum(data["frequencies"]) / len(data["frequencies"])
        return avg_frequency
    return None

def parse_message(message, station):
    match = AZIMUTH_PATTERN.match(message) or DIRECT_PATTERN.match(message)
    if match:
        # Parse values from the message
        ed_instance_id = match.group(1)
        rssi = int(match.group(2))
        angle_1 = int(match.group(3))
        angle_2 = int(match.group(4))
        channel = int(match.group(6))
        anchor_id = match.group(7)
        timestamp = int(match.group(8))
        periodic_event_counter = int(match.group(9))
        
        # match and save the tag ids
        if ed_instance_id not in tag_ids:
            tag_ids.append(ed_instance_id)

        tag_num = tag_ids.index(ed_instance_id) + 1

        # Calculate average frequency for the tag based on the current timestamp and readout time
        avg_frequency = calculate_frequency(tag_num, timestamp)


        # Display the parsed data in a formatted way with set width
        print(
            f"Station: {station:<1} | "
            f"Tag: {tag_num:<1} | "
            # f"Anchor ID: {anchor_id:<12} | "
            # f"ED ID: {ed_instance_id:<12} | "
            f"RSSI: {rssi:<3} dBm | "
            f"Azimuth: {angle_1:<5}° | "
            f"Elevation: {angle_2:<5}° | "
            # f"Channel: {channel:<3} | "
            f"Timestamp: {timestamp:<10} ms | "
            # f"Counter: {periodic_event_counter:<4} | "
            f"Avg Frequency: {avg_frequency:.2f} Hz" if avg_frequency else "Calculating..."
        )
    else:
        print("Invalid message format:", message)


def select_two_ports():
    ports = glob.glob('/dev/ttyUSB*')
    if len(ports) < 2:
        print("Not enough /dev/ttyUSBX ports found.")
        return None
    print("Available /dev/ttyUSBX ports:")
    for i, port in enumerate(ports):
        print(f"{i}: {port}")
    selected_ports = []
    for selection_num in range(2):
        while True:
            try:
                selection = int(input(f"Select port {selection_num + 1}: "))
                if 0 <= selection < len(ports) and ports[selection] not in selected_ports:
                    selected_ports.append(ports[selection])
                    print(f"Selected port {selection_num + 1}: {ports[selection]}")
                    break
                elif ports[selection] in selected_ports:
                    print("You've already selected this port. Choose a different one.")
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Enter a valid number.")
    return selected_ports

def load_or_select_ports():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                if "ports" in config and len(config["ports"]) == 2:
                    print("Loaded ports from config:", config["ports"])
                    return config["ports"]
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading config file: {e}")
    selected_ports = select_two_ports()
    if selected_ports:
        with open(CONFIG_FILE, 'w') as f:
            json.dump({"ports": selected_ports}, f)
        print("Saved selected ports to config.")
    return selected_ports

def read_from_port(port, station):
    while True:
        try:
            with serial.Serial(port, BAUD_RATE, timeout=1) as ser:
                ser.reset_input_buffer()  # Flush input buffer
                print(f"Listening on {port}...")
                while True:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        parse_message(line, station)
        except serial.SerialException as e:
            print(f"Error opening serial port {port}: {e}. Retrying in 5 seconds...")
            time.sleep(5)  # Retry every 5 seconds if the port is busy or encounters an error
        except KeyboardInterrupt:
            print(f"Stopping listening on {port}.")
            break

def main():
    selected_ports = load_or_select_ports()
    if selected_ports and len(selected_ports) == 2:
        port1, port2 = selected_ports
        print(f"Using ports: {port1} and {port2}")
        thread1 = threading.Thread(target=read_from_port, args=(port1, "1",))
        thread2 = threading.Thread(target=read_from_port, args=(port2, "2",))
        thread1.start()
        thread2.start()
        try:
            thread1.join()
            thread2.join()
        except KeyboardInterrupt:
            print("Exiting...")
            
if __name__ == "__main__":
    main()
