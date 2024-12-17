import os
import subprocess
import traceback
import re
import math
from collections import defaultdict, deque
from threading import Thread, Lock, Event
from grid_visualizer import GridVisualizer
from dataclasses import dataclass, field
from parsed_data import ParsedDataBLE, ParsedDataRadar, parse_string
from typing import Tuple, Optional, Dict, Deque
import numpy as np
import time
# Configuration constants
some_constant = 825
gwm = 6
ghm = 10
pixels_per_meter = int(some_constant/ghm)

anchor1_dist = -0.825
anchor2_dist = -anchor1_dist
radar_dist = 0

rectw = 90
recth = 40

kpthm = 2
kpthwm = 1

azlw = 1

RADAR_POINTS_TRESHOLD = 2

# Smoothing configuration
ANGLE_SMOOTHING_WINDOW = 2  # Number of samples for moving average
POSITION_SMOOTHING_WINDOW = 2
SMOOTHING_WEIGHT = 0.3  # Weight for exponential smoothing (0-1)

@dataclass
class SmoothingConfig:
    enable_angle_smoothing: bool = True
    enable_position_smoothing: bool = True
    angle_window_size: int = ANGLE_SMOOTHING_WINDOW
    position_window_size: int = POSITION_SMOOTHING_WINDOW
    smoothing_weight: float = SMOOTHING_WEIGHT

@dataclass
class TagConfig:
    enabled: bool = True
    color: str = "dodgerblue"
    name: str = "Tag"

@dataclass
class UI_elements:
    viz: Optional[GridVisualizer] = None
    # Azimuth TAG, ANCHOR
    azimuth1_1: Optional[object] = None
    azimuth1_2: Optional[object] = None
    azimuth2_1: Optional[object] = None
    azimuth2_2: Optional[object] = None
    tag1: Optional[object] = None
    tag2: Optional[object] = None

    keepout: Optional[object] = None
    radarDetected: Optional[object] = None
    bleDetected: Optional[object] = None

    radarPoints: list[Optional[object]] = field(default_factory=lambda: [None, None])
    
    elevation1_1: float = 0
    elevation1_2: float = 0
    elevation2_1: float = 0
    elevation2_2: float = 0
    
    # Smoothing buffers
    angle_buffers: Dict[str, Deque[float]] = None
    position_buffers: Dict[str, Deque[Tuple[float, float]]] = None
    
    # Thread control
    stop_event: Event = None
    
    def __post_init__(self):
        self.angle_buffers = {
            'az1_1': deque(maxlen=ANGLE_SMOOTHING_WINDOW),
            'az1_2': deque(maxlen=ANGLE_SMOOTHING_WINDOW),
            'az2_1': deque(maxlen=ANGLE_SMOOTHING_WINDOW),
            'az2_2': deque(maxlen=ANGLE_SMOOTHING_WINDOW),
        }
        self.position_buffers = {
            'tag1': deque(maxlen=POSITION_SMOOTHING_WINDOW),
            'tag2': deque(maxlen=POSITION_SMOOTHING_WINDOW),
        }
        self.stop_event = Event()

class SmoothingFilter:
    @staticmethod
    def smooth_angle(value: float, buffer: deque, config: SmoothingConfig) -> float:
        if not config.enable_angle_smoothing:
            return value
            
        buffer.append(value)
        if len(buffer) < 2:
            return value
            
        # Exponential moving average
        return (config.smoothing_weight * value + 
                (1 - config.smoothing_weight) * sum(buffer)/len(buffer))

    @staticmethod
    def smooth_position(x: float, y: float, buffer: deque, config: SmoothingConfig) -> Tuple[float, float]:
        if not config.enable_position_smoothing:
            return x, y
            
        buffer.append((x, y))
        if len(buffer) < 2:
            return x, y
            
        # Average x and y separately
        smooth_x = config.smoothing_weight * x + (1 - config.smoothing_weight) * np.mean([p[0] for p in buffer])
        smooth_y = config.smoothing_weight * y + (1 - config.smoothing_weight) * np.mean([p[1] for p in buffer])
        return smooth_x, smooth_y

ui_elements = UI_elements()
smoothing_config = SmoothingConfig()
tag_configs = {
    1: TagConfig(enabled=True, color="dodgerblue", name="Tag 1"),
    2: TagConfig(enabled=False, color="firebrick1", name="Tag 2")
}

def check_points_in_box(cords_x, cords_y, width, height, min_points):
    half_width = width / 2
    points_in_box = 0
    
    for i in range(0, len(parsed_data.x_coords)):
        # Get coordinates from the visualization object
        x = parsed_data.x_coords[i]
        y = parsed_data.y_coords[i]
        
        # Check if point is within box boundaries
        if abs(x) <= half_width and 0 <= y <= height:
            points_in_box += 1
            
        # Early exit if we've found enough points
        if points_in_box >= min_points:
            return True
            
    return False

def calculate_tag_position(
    anchor_distance: float,
    azimuth1: float,
    elevation1: float,
    azimuth2: float,
    elevation2: float
) -> Tuple[float, float, float]:
    """
    Calculate the 2D position of a BLE tag using data from two anchors.
    
    Angle Convention:
    - Azimuth: 0° points up (+Y), 90° points right (+X), -90° points left (-X)
    - Elevation: 0° is horizontal, 90° is straight up
    
    Args:
        anchor_distance: Distance between anchors in meters (along X axis)
        azimuth1: Azimuth angle from first anchor in degrees
        elevation1: Elevation angle from first anchor in degrees
        azimuth2: Azimuth angle from second anchor in degrees
        elevation2: Elevation angle from second anchor in degrees
    
    Returns:
        Tuple containing:
        - x: X coordinate relative to midpoint between anchors (in meters)
        - y: Y coordinate (in meters)
        - uncertainty_radius: Estimated uncertainty radius based on vector differences
    """
    # Convert angles to radians
    az1_rad = math.radians(azimuth1)
    az2_rad = math.radians(azimuth2)
    el1_rad = math.radians(elevation1)
    el2_rad = math.radians(elevation2)
    
    # Position anchors at (-distance/2, 0) and (distance/2, 0)
    anchor1_x = -anchor_distance / 2
    anchor2_x = anchor_distance / 2
    
    # Calculate 3D direction vectors from each anchor
    vec1_x = math.sin(az1_rad) * math.cos(el1_rad)
    vec1_y = math.cos(az1_rad) * math.cos(el1_rad)
    vec1_z = math.sin(el1_rad)
    
    vec2_x = math.sin(az2_rad) * math.cos(el2_rad)
    vec2_y = math.cos(az2_rad) * math.cos(el2_rad)
    vec2_z = math.sin(el2_rad)
    
    # Use least squares to find intersection point (2D)
    A = np.array([
        [vec1_x, -vec2_x],
        [vec1_y, -vec2_y]
    ])
    b = np.array([anchor2_x - anchor1_x, 0])
    
    try:
        # Solve for scaling factors
        t1, t2 = np.linalg.lstsq(A, b, rcond=None)[0]
        
        # Calculate intersection point from first anchor
        x = anchor1_x + vec1_x * t1
        y = vec1_y * t1
        
        # Calculate uncertainty based on the difference between 3D vectors
        # Dot product of normalized vectors gives cosine of angle between them
        vec1_norm = math.sqrt(vec1_x*vec1_x + vec1_y*vec1_y + vec1_z*vec1_z)
        vec2_norm = math.sqrt(vec2_x*vec2_x + vec2_y*vec2_y + vec2_z*vec2_z)
        
        dot_product = (vec1_x*vec2_x + vec1_y*vec2_y + vec1_z*vec2_z) / (vec1_norm * vec2_norm)
        # Clamp dot product to [-1, 1] to avoid numerical errors
        dot_product = max(min(dot_product, 1), -1)
        angle_between_vectors = math.acos(dot_product)
        
        # Scale uncertainty based on:
        # 1. The angle between vectors (more angle = more uncertainty)
        # 2. Distance from the anchors (further = more uncertainty)
        base_uncertainty = 0.2  # minimum uncertainty in meters
        distance_from_center = math.sqrt(x*x + y*y)
        angle_factor = math.sin(angle_between_vectors/2)  # 0 when vectors parallel, 1 when perpendicular
        
        uncertainty_radius = base_uncertainty + (angle_factor * distance_from_center) /2 # divide by 2 because i said so
        
        return x, y, uncertainty_radius
        
    except np.linalg.LinAlgError:
        # Handle case where lines are parallel or calculation fails
        return None, None, None


def update_tag_1_pos():
    if not tag_configs[1].enabled or ui_elements.tag1 is None:
        return
        
    x, y, radius = calculate_tag_position(
        anchor2_dist-anchor1_dist,
        ui_elements.azimuth1_1.angle,
        ui_elements.elevation1_1,
        ui_elements.azimuth1_2.angle,
        ui_elements.elevation1_2)
        
    if x is not None and y is not None:
        x, y = SmoothingFilter.smooth_position(
            x, y, 
            ui_elements.position_buffers['tag1'],
            smoothing_config
        )
        ui_elements.tag1.x = x
        ui_elements.tag1.y = y
        ui_elements.tag1.radius_pixels = radius * pixels_per_meter
        ui_elements.viz.update_object(ui_elements.tag1)

def update_tag_2_pos():
    if not tag_configs[2].enabled or ui_elements.tag2 is None:
        return
        
    x, y, radius = calculate_tag_position(
        anchor2_dist-anchor1_dist,
        ui_elements.azimuth2_1.angle,
        ui_elements.elevation2_1,
        ui_elements.azimuth2_2.angle,
        ui_elements.elevation2_2)
        
    if x is not None and y is not None:
        x, y = SmoothingFilter.smooth_position(
            x, y,
            ui_elements.position_buffers['tag2'],
            smoothing_config
        )
        ui_elements.tag2.x = x
        ui_elements.tag2.y = y
        ui_elements.tag2.radius_pixels = radius * pixels_per_meter
        ui_elements.viz.update_object(ui_elements.tag2)

def update_ble(parsed_data):
    if str(parsed_data.tag) == "1" and tag_configs[1].enabled:
        # TAG 1
        if str(parsed_data.station) == "1" and ui_elements.azimuth1_1 is not None:
            smooth_angle = SmoothingFilter.smooth_angle(
                parsed_data.azimuth,
                ui_elements.angle_buffers['az1_1'],
                smoothing_config
            )
            ui_elements.azimuth1_1.angle = smooth_angle
            ui_elements.azimuth1_1.text = f"{smooth_angle:.1f}°"
            ui_elements.elevation1_1 = parsed_data.elevation
            ui_elements.viz.update_object(ui_elements.azimuth1_1)
        elif ui_elements.azimuth1_2 is not None:
            smooth_angle = SmoothingFilter.smooth_angle(
                parsed_data.azimuth,
                ui_elements.angle_buffers['az1_2'],
                smoothing_config
            )
            ui_elements.azimuth1_2.angle = smooth_angle
            ui_elements.azimuth1_2.text = f"{smooth_angle:.1f}°"
            ui_elements.elevation1_2 = parsed_data.elevation
            ui_elements.viz.update_object(ui_elements.azimuth1_2)
        update_tag_1_pos()
    elif str(parsed_data.tag) == "2" and tag_configs[2].enabled:
        # TAG 2
        if str(parsed_data.station) == "1" and ui_elements.azimuth2_1 is not None:
            smooth_angle = SmoothingFilter.smooth_angle(
                parsed_data.azimuth,
                ui_elements.angle_buffers['az2_1'],
                smoothing_config
            )
            ui_elements.azimuth2_1.angle = smooth_angle
            ui_elements.azimuth2_1.text = f"{smooth_angle:.1f}°"
            ui_elements.elevation2_1 = parsed_data.elevation
            ui_elements.viz.update_object(ui_elements.azimuth2_1)
        elif ui_elements.azimuth2_2 is not None:
            smooth_angle = SmoothingFilter.smooth_angle(
                parsed_data.azimuth,
                ui_elements.angle_buffers['az2_2'],
                smoothing_config
            )
            ui_elements.azimuth2_2.angle = smooth_angle
            ui_elements.azimuth2_2.text = f"{smooth_angle:.1f}°"
            ui_elements.elevation2_2 = parsed_data.elevation
            ui_elements.viz.update_object(ui_elements.azimuth2_2)
        update_tag_2_pos()

def update_radar(parsed_data):
    # delete old points
    for point in ui_elements.radarPoints:
        ui_elements.viz.remove_object(point)
    
    # Counter for points in box
    points_in_box = 0
    half_width = kpthwm / 2
    
    for i in range(0, len(parsed_data.x_coords)):
        # Skip symmetrical points near y=0
        if (abs(parsed_data.y_coords[i]) < 0.1 and 
            any(abs(parsed_data.x_coords[i] + parsed_data.x_coords[j]) < 0.15 
                for j in range(len(parsed_data.x_coords)) 
                if j != i and abs(parsed_data.y_coords[j]) < 0.1)):
            continue
        
        # Check if point is in box before adding it
        if abs(parsed_data.x_coords[i]) <= half_width and 0 <= parsed_data.y_coords[i] <= kpthm:
            points_in_box += 1
            
        ui_elements.radarPoints.append(
            ui_elements.viz.add_point(
                parsed_data.x_coords[i], 
                parsed_data.y_coords[i], 
                5, 
                "orange red", 
                ""
            )
        )
    if points_in_box >= RADAR_POINTS_TRESHOLD and ui_elements.radarDetected == None:
        ui_elements.radarDetected = ui_elements.viz.add_text(-1, -2, "Radar detected unexpected person!", "Red")

    if points_in_box == 0 and ui_elements.radarDetected != None:
            ui_elements.viz.remove_object(ui_elements.radarDetected)
            ui_elements.radarDetected = None



def run_radar():
    parser = ParsedDataRadar()
    process = subprocess.Popen(
        ['python', '-u', './radar/rad.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    try:
        for line in process.stdout:
            line = line.strip()
            if "Connected" in line:
                print("Radar configured succesfully")
                continue
            if line:
                if parser.parse_string(line):
                    update_radar(parser)
    finally:
        traceback.print_exc()
        process.terminate()
        process.wait()


def run_ble():
    process = subprocess.Popen(
        ['python', '-u', './ble/ble.py'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    try:
        while not ui_elements.stop_event.is_set():
            stdout_line = process.stdout.readline()
            if not stdout_line:
                break
            if "Station" in stdout_line:
                parsed_data = parse_string(stdout_line)
                if parsed_data:
                    update_ble(parsed_data)
    finally:
        traceback.print_exc()
        process.terminate()
        process.wait()

def create_ui_elements_for_tag(tag_num: int):
    if not tag_configs[tag_num].enabled:
        return
        
    if tag_num == 1:
        ui_elements.azimuth1_1 = ui_elements.viz.add_line(anchor1_dist, 0, 25, "cyan", "", azlw)
        ui_elements.azimuth1_2 = ui_elements.viz.add_line(anchor2_dist, 0, -25, "cyan", "", azlw)
        ui_elements.tag1 = ui_elements.viz.add_point(0, 100, 0, tag_configs[1].color, tag_configs[1].name)
        ui_elements.azimuth1_1.text = "0°"
        ui_elements.azimuth1_2.text = "0°"
    else:
        ui_elements.azimuth2_1 = ui_elements.viz.add_line(anchor1_dist, 0, 10, "HotPink1", "", azlw)
        ui_elements.azimuth2_2 = ui_elements.viz.add_line(anchor2_dist, 0, -30, "HotPink1", "", azlw)
        ui_elements.tag2 = ui_elements.viz.add_point(0, 100, 0, tag_configs[2].color, tag_configs[2].name)
        ui_elements.azimuth2_1.text = "0°"
        ui_elements.azimuth2_2.text = "0°"

def main():
    ui_elements.viz = GridVisualizer(
        width_meters=gwm,
        height_meters=ghm,
        background_canvas="#6F6F6F",
        background_ui="#353535",
        pixels_per_meter=pixels_per_meter)

    # BLE anchors
    rect1 = ui_elements.viz.add_rectangle(anchor1_dist, -recth/pixels_per_meter/2, rectw, recth, "yellow", None, 1, "Anchor 1")
    rect2 = ui_elements.viz.add_rectangle(anchor2_dist, -recth/pixels_per_meter/2, rectw, recth, "yellow", None, 1, "Anchor 2")
    # Radar
    rect3 = ui_elements.viz.add_rectangle(radar_dist, -recth/pixels_per_meter/2*3, rectw, recth, "red", None, 1, "Radar")
    # Radar keepout
    ui_elements.keepout = ui_elements.viz.add_rectangle(radar_dist, kpthm/2, pixels_per_meter*kpthwm, pixels_per_meter*kpthm, None, "Red", 1)


    # Create UI elements for enabled tags
    create_ui_elements_for_tag(1)
    create_ui_elements_for_tag(2)

    # Update initial positions for enabled tags
    if tag_configs[1].enabled:
        update_tag_1_pos()
    if tag_configs[2].enabled:
        update_tag_2_pos()

    ble_thread = Thread(target=run_ble, daemon=False)
    ble_thread.start()

    radar_thread = Thread(target=run_radar, daemon=False)
    radar_thread.start()

    try:
        ui_elements.viz.start()
    finally:
        # Signal threads to stop
        ui_elements.stop_event.set()
        # Wait for threads to finish
        ble_thread.join(timeout=2.0)

if __name__ == "__main__":
    main()