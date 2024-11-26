import serial
import re
import os
import glob
import json
import threading
import time
from collections import defaultdict, deque
from radar_interface import RadarInterface
from radar_ui import RadarUI

RADAR_CONFIG = "./tdm/profile_2d_3AzimTx.cfg"

CONFIG_FILE = "config.json"
BAUD_RATE_CON = 115200
BAUD_RATE_DAT = 921600

con_timeout = 0.01
dat_timeout = 1


def parse_cfg_file(file_path):
    """
    Parses a radar configuration (.cfg) file and returns an array of commands.
    Comment lines (starting with '%') are ignored.
    
    :param file_path: Path to the .cfg file.
    :return: List of configuration commands (strings).
    """
    commands = []
    
    try:
        with open(file_path, 'r') as file:
            for line in file:
                # Strip whitespace and skip comment lines
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith('%'):
                    commands.append(stripped_line)
        return commands
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return []
    except Exception as e:
        print(f"Error: An error occurred while reading the file - {e}")
        return []


def configure(port):
    with serial.Serial(port, BAUD_RATE_CON, timeout=con_timeout) as ser:
        ser.reset_input_buffer()  # Flush input buffer
        try:
            # parse the config file
            config_commands = parse_cfg_file(RADAR_CONFIG)
            if len(config_commands) == 0: return

            # Send configuration commands to the radar
            for cmd in config_commands:
                ser.write((cmd+"\n").encode())

                if cmd == "sensorStop" or cmd == "sensorStart":
                    time.sleep(.1) # facilitate longer time to execute these commands

                response = ser.readlines()  # Reads all lines as a list of bytes

                response = [line.decode().strip() for line in response]  # Decode and strip newline characters

                # Check for newline and "Done"
                if len(response) >= 2 and response[-2] == "Done":
                    print(".", end="", flush=True)
                else:
                    raise Exception(f"Failed to execute {cmd}\nresponse: {response}")

            print("\nConfiguration commands sent succesfully.")

        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")


        finally:
            # Close the serial port if it's open
            if ser.is_open:
                ser.close()
            print("Serial port closed.")


def select_two_ports():
    ports = glob.glob('/dev/ttyACM*')
    if len(ports) < 2:
        print("Not enough /dev/ttyACMX ports found.")
        return None
    print("Available /dev/ttyACMX ports:")
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

def main():
    selected_ports = load_or_select_ports()
    if selected_ports and len(selected_ports) == 2:
        port1, port2 = selected_ports
        print(f"Using CONSOLE port: {port1} and DATA port: {port2}")
        configure(port1)

        print("Reading data")
        radar = RadarInterface(port=port2, baudrate=BAUD_RATE_DAT)
        radarUI = RadarUI(2, 2)
        # read the data
        try:
            while True:
                # Read data from the radar
                raw_data = radar.read_data()
                
                if raw_data:
                    # Parse the radar data
                    parsed_results = radar.parse_frame(raw_data)
                    # print(parsed_results)
                    radarUI.update(parsed_results)
        except KeyboardInterrupt:
            print("Exiting...")
        finally:
            radar.close()


if __name__ == "__main__":
    main()
