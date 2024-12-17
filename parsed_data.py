import re
import json

class ParsedDataBLE:
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
        #print(f"Skipping line: {input_string.strip()}")  # Debugging output
        return None

    data = match.groupdict()
    return ParsedDataBLE(
        station=int(data['station']),
        tag=int(data['tag']),
        rssi=int(data['rssi']),
        azimuth=int(data['azimuth']),
        elevation=int(data['elevation']),
        timestamp=int(data['timestamp']),
        avg_frequency=float(data['avg_frequency'])
    )

class ParsedDataRadar:
    def __init__(self):
        self.frame_number = 0
        self.num_det_obj = 0
        self.x_coords = []
        self.y_coords = []
        
    def parse_string(self, line):
        """
        Parse a line of JSON output and store the data in class variables
        Returns True if parsing successful, False otherwise
        """
        try:
            data = json.loads(line)
            
            self.frame_number = data["frame_number"]
            self.num_det_obj = data["num_det_obj"]
            self.x_coords = data["x_coords"]
            self.y_coords = data["y_coords"]
            
            return True
            
        except json.JSONDecodeError:
            # print(f"Error parsing line: {line}")
            return False