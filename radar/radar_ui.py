import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('TkAgg')  # Force the TkAgg backend for compatibility with Wayland

class RadarUI:
    def __init__(self, x_scale=10, y_scale=10):
        """
        Initialize the Radar UI with custom scaling.

        :param x_scale: Maximum distance for the X-axis in meters.
        :param y_scale: Maximum distance for the Y-axis in meters.
        """
        self.x_scale = x_scale
        self.y_scale = y_scale

        # Set up the plot
        self.fig, self.ax = plt.subplots(figsize=(8, 6))
        self.scatter = None
        self.frame_text = None

        # Configure plot
        self.ax.axhline(0, color='black', linewidth=0.5)
        self.ax.axvline(0, color='black', linewidth=0.5)
        self.ax.grid(True, linestyle='--', alpha=0.6)
        self.ax.set_aspect('equal', adjustable='box')
        self.ax.set_xlim(-self.x_scale, self.x_scale)
        self.ax.set_ylim(-self.y_scale, self.y_scale)
        self.ax.set_title("Radar Detection")
        self.ax.set_xlabel("X (meters)")
        self.ax.set_ylabel("Y (meters)")

        # Initialize plot objects
        self.scatter = self.ax.scatter([], [], c='red', label="Detected Objects")
        self.frame_text = self.ax.text(0.05, 0.95, '', transform=self.ax.transAxes, fontsize=12, verticalalignment='top')
        self.ax.legend()

    def update(self, parsed_data):
        """
        Update the plot with new radar data.
        
        :param parsed_data: Tuple containing parsed radar data.
        """
        (
            _,
            _,
            _,
            frame_number,
            num_det_obj,
            _,
            _,
            detected_x_array,
            detected_y_array,
            *_
        ) = parsed_data

        # Update scatter plot
        self.scatter.set_offsets(list(zip(detected_x_array, detected_y_array)))

        # Update frame information
        self.frame_text.set_text(f"Frame: {frame_number} | Objects: {num_det_obj}")

        # Refresh the plot
        plt.pause(0.01)

    def show(self):
        """
        Display the radar UI in interactive mode.
        """
        plt.ion()
        plt.show()
