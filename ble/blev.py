import os
import subprocess
import traceback
import re
import math
from collections import defaultdict
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from threading import Thread, Lock

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
        print(f"Skipping line: {input_string.strip()}")  # Debugging output
        return None

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

# Global data storage
positions = {}
elevations = {}
lock = Lock()  # To manage thread-safe updates

def calculate_position(parsed_data):
    """Calculate (x, y) position based on azimuth and RSSI."""
    r = max(1, 100 + parsed_data.rssi)  # Estimate distance based on RSSI
    azimuth_rad = math.radians(parsed_data.azimuth)

    x = r * math.cos(azimuth_rad)
    y = r * math.sin(azimuth_rad)
    return x, y

def visualization():
    """Visualize tag positions and elevations."""
    plt.close('all')  # Ensure no lingering figures
    fig = plt.figure(figsize=(12, 6))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 2])
    
    ax_polar = fig.add_subplot(gs[0, 0], projection='polar')  # Polar plot for elevation
    ax_scatter = fig.add_subplot(gs[0, 1])  # 2D scatter plot for positions

    # Configure scatter plot
    ax_scatter.set_xlim(-200, 200)
    ax_scatter.set_ylim(-200, 200)
    ax_scatter.set_title("Tag Positions", fontsize=12)
    ax_scatter.set_xlabel("X Position")
    ax_scatter.set_ylabel("Y Position")
    ax_scatter.grid(True)

    # Configure polar plot
    ax_polar.set_theta_zero_location("N")  # North (top) is 0 degrees
    ax_polar.set_theta_direction(-1)  # Angles increase clockwise
    ax_polar.set_title("Elevation (Polar Plot)", fontsize=12, pad=20)

    # Update function for animation
    def update_plot(frame):
        # Lock data access
        with lock:
            current_positions = positions.copy()
            current_elevations = elevations.copy()

        # Clear scatter plot
        ax_scatter.clear()
        ax_scatter.set_xlim(-200, 200)
        ax_scatter.set_ylim(-200, 200)
        ax_scatter.set_title("Tag Positions", fontsize=12)
        ax_scatter.set_xlabel("X Position")
        ax_scatter.set_ylabel("Y Position")
        ax_scatter.grid(True)

        # Plot each tag's position in scatter plot
        for tag, (x, y) in current_positions.items():
            ax_scatter.scatter(x, y, label=f"Tag {tag}", s=50)
            ax_scatter.annotate(f"Tag {tag}", (x, y), textcoords="offset points", xytext=(5, 5))

        # Add legend if there are tags
        if len(current_positions) > 0:
            ax_scatter.legend(loc="upper right")

        # Clear polar plot
        ax_polar.clear()
        ax_polar.set_theta_zero_location("N")
        ax_polar.set_theta_direction(-1)
        ax_polar.set_title("Elevation (Polar Plot)", fontsize=12, pad=20)

        # Plot each tag's elevation in the polar plot
        for tag, (theta, r) in current_elevations.items():
            ax_polar.scatter(theta, r, label=f"Tag {tag}", s=50)

        # Add polar plot legend
        if len(current_elevations) > 0:
            ax_polar.legend(loc="upper right")

    # Start animation
    ani = FuncAnimation(fig, update_plot, interval=1000, cache_frame_data=False)
    plt.tight_layout()
    plt.show()

def calculation(parsed_data):
    """Update positions and elevations for tags."""
    x, y = calculate_position(parsed_data)
    theta = math.radians(parsed_data.azimuth)
    r = parsed_data.elevation

    # Use lock for thread-safe updates
    with lock:
        positions[parsed_data.tag] = (x, y)
        elevations[parsed_data.tag] = (theta, r)

def run_ble():
    process = subprocess.Popen(
        ['python', '-u', './ble/ble.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    try:
        for stdout_line in process.stdout:
            if "Station" in stdout_line:
                parsed_data = parse_string(stdout_line)
                if parsed_data:
                    calculation(parsed_data)
    except KeyboardInterrupt:
        print("Interrupted! Terminating subprocess...")
        process.terminate()
    finally:
        traceback.print_exc()
        process.terminate()
        process.wait()

def main():
    ble_thread = Thread(target=run_ble, daemon=False)
    ble_thread.start()
    visualization()

if __name__ == "__main__":
    main()
