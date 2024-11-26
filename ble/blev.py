import os
import subprocess
import tkinter as tk
import math
import traceback
import tkinter as tk
import math
import re

class ParsedData:
    def __init__(self, station, tag, rssi, azimuth, elevation, timestamp, avg_frequency):
        self.station = station
        self.tag = tag
        self.rssi = rssi
        self.azimuth = azimuth
        self.elevation = elevation
        self.timestamp = timestamp
        self.avg_frequency = avg_frequency

    def __repr__(self):
        return (f"ParsedData("
                f"station={self.station}, tag={self.tag}, rssi={self.rssi}, "
                f"azimuth={self.azimuth}, elevation={self.elevation}, "
                f"timestamp={self.timestamp}, avg_frequency={self.avg_frequency})")


def parse_string(input_string):
    # Regex to match each field in the string
    pattern = (
        r"Station:\s*(?P<station>\d+)\s*\|\s*"
        r"Tag:\s*(?P<tag>\d+)\s*\|\s*"
        r"RSSI:\s*(?P<rssi>-?\d+)\s*dBm\s*\|\s*"
        r"Azimuth:\s*(?P<azimuth>-?\d+)\s*°\s*\|\s*"
        r"Elevation:\s*(?P<elevation>-?\d+)\s*°\s*\|\s*"
        r"Timestamp:\s*(?P<timestamp>\d+)\s*ms\s*\|\s*"
        r"Avg Frequency:\s*(?P<avg_frequency>[\d.]+)\s*Hz"
    )

    match = re.match(pattern, input_string)
    if not match:
        raise ValueError("Input string does not match the expected format.")

    # Convert matched groups to appropriate types and create ParsedData object
    data = match.groupdict()
    return ParsedData(
        station=int(data['station']),
        tag=int(data['tag']),
        rssi=int(data['rssi']),
        azimuth=int(data['azimuth']),
        elevation=int(data['elevation']),
        timestamp=int(data['timestamp']),
        avg_frequency=float(data['avg_frequency'])
    )



def run_ble():
    process = subprocess.Popen(
        ['python', '-u', 'ble.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,  # Ensures strings (not bytes) are captured
        bufsize=1   # Line buffering
    )

    try:
        # Read lines from stdout and stderr
        for stdout_line in process.stdout:
            if "Station" in stdout_line: # correct message (hopefully)
                parsed_data = parse_string(stdout_line)
                #TODO visualisation update code here
                #TODO pair station data for calculation
                # (station 1 tag 1) & (station 2 tag 1)
                # (station 1 tag 2) & (station 2 tag 2)
                print(parsed_data) 

    except KeyboardInterrupt:
        print("Interrupted! Terminating subprocess...")
        process.terminate()
    finally:
        print(traceback.format_exc())
        process.terminate()
        process.wait()  # Wait for the subprocess to clean up


def main():
    #TODO visualisation create here
    run_ble()
            
if __name__ == "__main__":
    main()