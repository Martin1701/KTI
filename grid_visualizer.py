import tkinter as tk
from threading import Lock
from math import cos, sin, radians
from queue import Queue
from dataclasses import dataclass
import threading
import colorsys

# [Previous dataclass definitions remain the same...]
@dataclass
class VisualPoint:
    x: float  # meters
    y: float  # meters
    radius_pixels: float
    color: str
    text: str = ""
    id: int = None
    text_id: int = None

@dataclass
class VisualLine:
    x: float
    y: float
    angle: float
    color: str = "white"
    text: str = ""
    thickness: int = 1  # default 1px
    id: int = None
    text_id: int = None

@dataclass
class VisualText:
    x: float
    y: float
    text: str
    color: str = "white"
    background: str = None
    id: int = None
    background_id: int = None

@dataclass
class VisualSquare:
    x: float
    y: float
    size_pixels: float
    color: str
    text: str = ""
    relative_to_grid: bool = True
    id: int = None
    text_id: int = None

@dataclass
class VisualRectangle:
    x: float
    y: float
    width_pixels: float
    height_pixels: float
    fill: str = None
    outline: str = None
    outline_width: int = 1
    text: str = ""
    id: int = None
    text_id: int = None

class GridVisualizer:
    def __init__(self, width_meters, height_meters, background_ui="black", 
                 background_canvas="black", pixels_per_meter=50, margin_pixels=100,
                 default_text_size=12):
        self.width_meters = width_meters
        self.height_meters = height_meters
        self.pixels_per_meter = pixels_per_meter
        self.margin_pixels = margin_pixels
        self.default_text_size = default_text_size
        
        # Grid dimensions (in pixels)
        self.grid_width_pixels = int(width_meters * pixels_per_meter)
        self.grid_height_pixels = int(height_meters * pixels_per_meter)
        
        # Full canvas dimensions
        self.canvas_width = self.grid_width_pixels + 2 * margin_pixels
        self.canvas_height = self.grid_height_pixels + 3 * margin_pixels
        
        # Grid offset from canvas top-left
        self.grid_x_offset = margin_pixels
        self.grid_y_offset = margin_pixels
        
        self.command_queue = Queue()
        self.lock = Lock()
        self.points = {}
        self.lines = {}
        self.texts = {}
        self.squares = {}
        self.rectangles = {}
        
        # Initialize Tkinter
        self.root = tk.Tk()
        self.root.configure(bg=background_ui)
        
        self.canvas = tk.Canvas(
            self.root,
            width=self.canvas_width,
            height=self.canvas_height,
            bg=background_canvas,
            highlightthickness=0
        )
        self.canvas.pack(expand=True, fill='both')
        
        # Draw grid area with border
        self.canvas.create_rectangle(
            self.grid_x_offset,
            self.grid_y_offset,
            self.grid_x_offset + self.grid_width_pixels,
            self.grid_y_offset + self.grid_height_pixels,
            outline='white',
            width=2
        )
        
        # Draw grid lines and dimension labels
        # X-axis labels (horizontal)
        for x in range(0, self.grid_width_pixels + 1, pixels_per_meter):
            # Draw vertical grid line
            self.canvas.create_line(
                self.grid_x_offset + x,
                self.grid_y_offset,
                self.grid_x_offset + x,
                self.grid_y_offset + self.grid_height_pixels,
                fill='gray20',
            )
            
            # Add X-axis label
            x_meters = x / pixels_per_meter - width_meters/2
            if abs(x_meters) >= 0.001:  # Avoid showing "0" multiple times
                self.canvas.create_text(
                    self.grid_x_offset + x,
                    self.grid_y_offset - 10,
                    text=f"{x_meters:.1f}",
                    fill='white',
                    anchor='s',
                    font=("Arial", default_text_size)
                )

        # Y-axis labels (vertical)
        for y in range(0, self.grid_height_pixels + 1, pixels_per_meter):
            # Draw horizontal grid line
            self.canvas.create_line(
                self.grid_x_offset,
                self.grid_y_offset + y,
                self.grid_x_offset + self.grid_width_pixels,
                self.grid_y_offset + y,
                fill='gray20'
            )
            
            # Add Y-axis label
            y_meters = (self.grid_height_pixels - y) / pixels_per_meter
            if abs(y_meters) >= 0.001:  # Avoid showing "0" multiple times
                # Left side label
                self.canvas.create_text(
                    self.grid_x_offset - 10,
                    self.grid_y_offset + y,
                    text=f"{y_meters:.1f}",
                    fill='white',
                    anchor='e',
                    font=("Arial", default_text_size)
                )
                # Right side label
                self.canvas.create_text(
                    self.grid_x_offset + self.grid_width_pixels + 10,
                    self.grid_y_offset + y,
                    text=f"{y_meters:.1f}",
                    fill='white',
                    anchor='w',
                    font=("Arial", default_text_size)
                )

        # Add axis labels
        self.canvas.create_text(
            self.grid_x_offset + self.grid_width_pixels/2,
            self.grid_y_offset - 30,
            text="X [m]",
            fill='white',
            anchor='s',
            font=("Arial", default_text_size)
        )
        self.canvas.create_text(
            self.grid_x_offset - 40,
            self.grid_y_offset + self.grid_height_pixels/2,
            text="Y [m]",
            fill='white',
            anchor='e',
            font=("Arial", default_text_size)
        )
            
        self.running = True
        self.update()

    def get_contrasting_text_color(self, background_color):
        return "black"
        """Calculate readable text color based on background color"""
        if background_color is None or background_color == "":
            return "black"
            
        # Remove the '#' if present
        if background_color.startswith('#'):
            background_color = background_color[1:]
            
        # Convert hex to RGB
        r = int(background_color[:2], 16) / 255.0
        g = int(background_color[2:4], 16) / 255.0
        b = int(background_color[4:], 16) / 255.0
        
        # Calculate luminance
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        
        return "black" if luminance > 0.5 else "white"

    def meters_to_pixels(self, x_meters, y_meters, use_grid_offset=True):
        """Convert meters to pixels, with (0,0) at bottom center of grid"""
        x_pixels = (x_meters + self.width_meters/2) * self.pixels_per_meter
        y_pixels = self.grid_height_pixels - y_meters * self.pixels_per_meter
        
        if use_grid_offset:
            x_pixels += self.grid_x_offset
            y_pixels += self.grid_y_offset
            
        return x_pixels, y_pixels

    def update(self):
        while not self.command_queue.empty():
            cmd, args = self.command_queue.get()
            with self.lock:
                if cmd == 'point':
                    self._add_point(*args)
                elif cmd == 'line':
                    self._add_line(*args)
                elif cmd == 'text':
                    self._add_text(*args)
                elif cmd == 'square':
                    self._add_square(*args)
                elif cmd == 'rectangle':
                    self._add_rectangle(*args)
                elif cmd == 'remove':
                    self._remove_object(*args)
        
        if self.running:
            self.root.after(16, self.update)

    def _add_point(self, point):
        x_pixels, y_pixels = self.meters_to_pixels(point.x, point.y)
        
        if point.id in self.points:
            self.canvas.delete(self.points[point.id])
            if point.text_id:
                self.canvas.delete(point.text_id)
        
        point.id = self.canvas.create_oval(
            x_pixels - point.radius_pixels,
            y_pixels - point.radius_pixels,
            x_pixels + point.radius_pixels,
            y_pixels + point.radius_pixels,
            fill=point.color,
            outline=point.color
        )
        
        if point.text:
            text_color = self.get_contrasting_text_color(point.color)
            point.text_id = self.canvas.create_text(
                x_pixels,
                y_pixels - point.radius_pixels - 5,  # Position text above point
                text=point.text,
                fill=text_color,
                font=("Arial", self.default_text_size),
                anchor='s'  # Bottom center anchor
            )
        
        self.points[point.id] = point.id

    def _calculate_line_endpoint(self, x_start, y_start, angle_rad):
        """
        Calculate endpoint for a line starting from bottom going up,
        stopping at first boundary it hits (top, left, or right)
        """
        # Grid boundaries
        left = self.grid_x_offset
        right = self.grid_x_offset + self.grid_width_pixels
        top = self.grid_y_offset
        
        # First calculate how far the line would go at this angle to reach the top
        height_pixels = self.grid_height_pixels
        t_to_top = height_pixels / cos(angle_rad)
        
        # Calculate where that would put our x coordinate
        end_x = x_start + sin(angle_rad) * t_to_top
        
        # If that x position is outside grid boundaries, we need to find where we hit the side instead
        if end_x < left:
            # Hit left boundary
            dx = left - x_start
            t = dx / sin(angle_rad)
            end_x = left
            end_y = y_start - t * cos(angle_rad)
        elif end_x > right:
            # Hit right boundary
            dx = right - x_start
            t = dx / sin(angle_rad)
            end_x = right
            end_y = y_start - t * cos(angle_rad)
        else:
            # Hit top boundary as originally calculated
            end_x = x_start + sin(angle_rad) * t_to_top
            end_y = top  # top of grid
        
        return end_x, end_y

    def _add_line(self, line, text_position_percent=10):
        """
        Add or update a line with text positioned along its length
        text_position_percent: 0-100, where 0 is start of line, 100 is end, 50 is middle
        """
        x_pixels, _ = self.meters_to_pixels(line.x, 0)
        y_pixels = self.grid_y_offset + self.grid_height_pixels  # Bottom of grid
        
        angle_rad = radians(line.angle)
        end_x, end_y = self._calculate_line_endpoint(x_pixels, y_pixels, angle_rad)
        
        if line.id in self.lines:
            self.canvas.delete(self.lines[line.id])
            if line.text_id:
                self.canvas.delete(line.text_id)
        
        line.id = self.canvas.create_line(
            x_pixels, y_pixels,
            end_x, end_y,
            fill=line.color,
            width=line.thickness
        )
        
        if line.text:
            # Calculate text position based on percentage
            text_x = x_pixels + (end_x - x_pixels) * (text_position_percent / 100)
            text_y = y_pixels + (end_y - y_pixels) * (text_position_percent / 100)
            
            text_color = self.get_contrasting_text_color(line.color)
            line.text_id = self.canvas.create_text(
                text_x,
                text_y,
                text=line.text,
                fill=text_color,
                font=("Arial", self.default_text_size),
                anchor='center'
            )
        
        self.lines[line.id] = line.id


    def _add_text(self, text):
        x_pixels, y_pixels = self.meters_to_pixels(text.x, text.y, use_grid_offset=False)
        
        if text.id in self.texts:
            self.canvas.delete(self.texts[text.id])
            if text.background_id:
                self.canvas.delete(text.background_id)
        
        temp_text = self.canvas.create_text(
            0, 0,
            text=text.text,
            anchor='center'
        )
        bbox = self.canvas.bbox(temp_text)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        self.canvas.delete(temp_text)
        
        if text.background:
            padding = 4
            text.background_id = self.canvas.create_rectangle(
                x_pixels - width/2 - padding,
                y_pixels - height/2 - padding,
                x_pixels + width/2 + padding,
                y_pixels + height/2 + padding,
                fill=text.background,
                outline=text.background
            )
        
        text_color = self.get_contrasting_text_color(text.background) if text.background else text.color
        text.id = self.canvas.create_text(
            x_pixels, y_pixels,
            text=text.text,
            fill=text_color,
            font=("Arial", self.default_text_size),
            anchor='center'
        )
        self.texts[text.id] = text.id

    def _add_square(self, square):
        x_pixels, _ = self.meters_to_pixels(square.x, 0)
        
        if square.relative_to_grid:
            y_pixels = self.grid_y_offset + self.grid_height_pixels + square.size_pixels/2
        else:
            _, y_pixels = self.meters_to_pixels(square.x, square.y, use_grid_offset=True)
            
        if square.id in self.squares:
            self.canvas.delete(self.squares[square.id])
            if square.text_id:
                self.canvas.delete(square.text_id)
            
        square.id = self.canvas.create_rectangle(
            x_pixels - square.size_pixels/2,
            y_pixels - square.size_pixels/2,
            x_pixels + square.size_pixels/2,
            y_pixels + square.size_pixels/2,
            fill=square.color,
            outline=square.color
        )
        
        if square.text:
            text_color = self.get_contrasting_text_color(square.color)
            square.text_id = self.canvas.create_text(
                x_pixels,
                y_pixels,
                text=square.text,
                fill=text_color,
                font=("Arial", self.default_text_size),
                anchor='center'
            )
        
        self.squares[square.id] = square.id

    def _add_rectangle(self, rect):
        x_pixels, y_pixels = self.meters_to_pixels(rect.x, rect.y)
        
        if rect.id in self.rectangles:
            self.canvas.delete(self.rectangles[rect.id])
            if rect.text_id:
                self.canvas.delete(rect.text_id)
        
        rect.id = self.canvas.create_rectangle(
            x_pixels - rect.width_pixels/2,
            y_pixels - rect.height_pixels/2,
            x_pixels + rect.width_pixels/2,
            y_pixels + rect.height_pixels/2,
            fill=rect.fill if rect.fill else "",
            outline=rect.outline if rect.outline else "",
            width=rect.outline_width
        )
        
        if rect.text:
            text_color = self.get_contrasting_text_color(rect.fill) if rect.fill else "black"
            rect.text_id = self.canvas.create_text(
                x_pixels,
                y_pixels,
                text=rect.text,
                fill=text_color,
                font=("Arial", self.default_text_size),
                anchor='center'
            )
        
        self.rectangles[rect.id] = rect.id

    def _remove_object(self, obj):
        """Internal method to remove an object from the canvas"""
        if isinstance(obj, VisualPoint):
            if obj.id in self.points:
                self.canvas.delete(obj.id)
                if obj.text_id:
                    self.canvas.delete(obj.text_id)
                del self.points[obj.id]
        elif isinstance(obj, VisualLine):
            if obj.id in self.lines:
                self.canvas.delete(obj.id)
                if obj.text_id:
                    self.canvas.delete(obj.text_id)
                del self.lines[obj.id]
        elif isinstance(obj, VisualText):
            if obj.id in self.texts:
                self.canvas.delete(obj.id)
                if obj.background_id:
                    self.canvas.delete(obj.background_id)
                del self.texts[obj.id]
        elif isinstance(obj, VisualSquare):
            if obj.id in self.squares:
                self.canvas.delete(obj.id)
                if obj.text_id:
                    self.canvas.delete(obj.text_id)
                del self.squares[obj.id]
        elif isinstance(obj, VisualRectangle):
            if obj.id in self.rectangles:
                self.canvas.delete(obj.id)
                if obj.text_id:
                    self.canvas.delete(obj.text_id)
                del self.rectangles[obj.id]

    # Public methods
    def add_point(self, x_meters, y_meters, radius_pixels, color, text=""):
        point = VisualPoint(x_meters, y_meters, radius_pixels, color, text)
        self.command_queue.put(('point', (point,)))
        return point

    def add_line(self, x_meters, y_meters, angle_degrees, color="black", text="", thickness=1):
        line = VisualLine(x_meters, y_meters, angle_degrees, color, text, thickness)
        self.command_queue.put(('line', (line,)))
        return line

    def add_text(self, x_meters, y_meters, text, color="black", background=None):
        text_obj = VisualText(x_meters, y_meters, text, color, background)
        self.command_queue.put(('text', (text_obj,)))
        return text_obj

    def add_square(self, x_meters, y_meters, size_pixels, color, text="", relative_to_grid=True):
        square = VisualSquare(x_meters, y_meters, size_pixels, color, text, relative_to_grid)
        self.command_queue.put(('square', (square,)))
        return square

    def add_rectangle(self, x_meters, y_meters, width_pixels, height_pixels, 
                     fill=None, outline=None, outline_width=1, text=""):
        rect = VisualRectangle(x_meters, y_meters, width_pixels, height_pixels,
                             fill, outline, outline_width, text)
        self.command_queue.put(('rectangle', (rect,)))
        return rect

    def update_object(self, obj):
        """Update any visual object's position or properties"""
        if isinstance(obj, (VisualPoint, VisualLine, VisualText, VisualSquare, VisualRectangle)):
            if isinstance(obj, VisualPoint):
                self.command_queue.put(('point', (obj,)))
            elif isinstance(obj, VisualLine):
                self.command_queue.put(('line', (obj,)))
            elif isinstance(obj, VisualText):
                self.command_queue.put(('text', (obj,)))
            elif isinstance(obj, VisualSquare):
                self.command_queue.put(('square', (obj,)))
            elif isinstance(obj, VisualRectangle):
                self.command_queue.put(('rectangle', (obj,)))

    def remove_object(self, obj):
        """Remove a visual object from the canvas"""
        self.command_queue.put(('remove', (obj,)))

    def pixels_to_meters_x(self, pixels):
        """
        Convert X pixels (from canvas coordinates) to meters relative to grid center
        """
        return (pixels - self.grid_x_offset) / self.pixels_per_meter - self.width_meters/2

    def pixels_to_meters_y(self, pixels):
        """
        Convert Y pixels (from canvas coordinates) to meters relative to grid center
        """
        return -(pixels - self.grid_y_offset - self.grid_height_pixels) / self.pixels_per_meter

    # And a convenience function that does both at once:
    def pixels_to_meters(self, x_pixels, y_pixels):
        """
        Convert pixel coordinates to meters relative to grid center
        Returns: (x_meters, y_meters)
        """
        return (self.pixels_to_meters_x(x_pixels), 
                self.pixels_to_meters_y(y_pixels))

    def start(self):
        """Start the visualization (must be called from main thread)"""
        if threading.current_thread() is threading.main_thread():
            self.root.mainloop()
        else:
            raise RuntimeError("Visualization must be started from main thread")

    def stop(self):
        """Stop the visualization"""
        self.running = False
        self.root.quit()