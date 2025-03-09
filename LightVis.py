import sys
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QSlider, QPushButton, QComboBox, QGroupBox, QFrame,
                            QCheckBox, QTabWidget, QRadioButton, QButtonGroup)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPainter,QFont, QColor, QPen, QBrush
import pyqtgraph as pg

# Define wavelength to RGB color mapping
def wavelength_to_rgb(wavelength):
    """Convert wavelength in nm to RGB color"""
    # Map simulation wavelength to approximate visible spectrum (380-750nm)
    # Assuming wavelength 10-100 in simulation maps to 380-750nm
    nm = wavelength
    
    # Based on algorithm by Dan Bruton (www.physics.sfasu.edu/astro/color/spectra.html)
    if 380 <= nm < 440:
        r = -(nm - 440) / (440 - 380)
        g = 0.0
        b = 1.0
    elif 440 <= nm < 490:
        r = 0.0
        g = (nm - 440) / (490 - 440)
        b = 1.0
    elif 490 <= nm < 510:
        r = 0.0
        g = 1.0
        b = -(nm - 510) / (510 - 490)
    elif 510 <= nm < 580:
        r = (nm - 510) / (580 - 510)
        g = 1.0
        b = 0.0
    elif 580 <= nm < 645:
        r = 1.0
        g = -(nm - 645) / (645 - 580)
        b = 0.0
    elif 645 <= nm <= 750:
        r = 1.0
        g = 0.0
        b = 0.0
    else:
        r, g, b = 0.5, 0.5, 0.5  # Outside visible spectrum
    
    # Attenuate brightness at the edges of the visible spectrum
    if 380 <= nm < 420:
        factor = 0.3 + 0.7 * (nm - 380) / (420 - 380)
    elif 420 <= nm < 700:
        factor = 1.0
    elif 700 <= nm <= 750:
        factor = 0.3 + 0.7 * (750 - nm) / (750 - 700)
    else:
        factor = 0.0
        
    r = round(255 * r * factor)
    g = round(255 * g * factor)
    b = round(255 * b * factor)
    
    return (r, g, b)

class WaveSimulationWidget(pg.PlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

        # Set up the plot
        self.setAntialiasing(True)
        self.setBackground('k')
        self.setLabel('left', 'Amplitude', color='w')
        self.setLabel('bottom', 'Position', color='w')
        self.setTitle('Light Wave Refraction Visualization', color='w')
        
        # Add grid
        self.showGrid(x=True, y=True, alpha=0.5)
        self.getPlotItem().getAxis('left').setPen('w')
        self.getPlotItem().getAxis('bottom').setPen('w')

        # Hide the auto-range button
        self.getPlotItem().hideButtons()

        # Set grid line spacing
        self.getPlotItem().getAxis('left').setTicks([[(i, str(i)) for i in range(-2, 3, 1)]])
        self.getPlotItem().getAxis('bottom').setTicks([[(i, str(i)) for i in range(0, 3001, 500)]])
        
        # Initial parameters
        self.wavelength = 550
        self.amplitude = 5
        self.speed = 2
        self.visualization_scale = 0.1  # Add visualization scaling factor
        self.n1 = 1.0003  # Air
        self.n2 = 1.33    # Water
        self.n3 = 1.52    # Glass (Crown)
        self.time = 0
        
        # Simulation mode
        self.prism_mode = False
        self.white_light = False
        
        # Medium boundaries
        self.boundary1 = 1000
        self.boundary2 = 2000
        
        # Set up the x-axis
        self.x = np.linspace(0, 3000, 3000)
        # Set fixed Y-axis range to show waves better
        self.setXRange(0, 3000, padding=0)
        self.setYRange(-2, 2, padding=0)

        # Disable mouse interaction
        self.setMouseEnabled(x=False, y=False)
        # Disable auto-range
        self.enableAutoRange(axis='x', enable=False)
        self.enableAutoRange(axis='y', enable=False)

        # Medium colors
        self.medium_colors = {
            'Air': (230, 230, 255, 50),        # Very light blue
            'Water': (153, 204, 255, 80),      # Light blue
            'Glass (Crown)': (204, 230, 230, 100),  # Light cyan
            'Glass (Flint)': (179, 204, 204, 100),  # Darker cyan
            'Diamond': (242, 242, 255, 130),   # White/blue tint
            'Acrylic': (230, 230, 179, 80),    # Light yellow
            'Glycerine': (230, 204, 230, 80),  # Light purple
            'Ethanol': (204, 204, 230, 80),    # Light purple-blue
            'Quartz': (255, 255, 230, 80),     # Very light yellow
            'Sapphire': (179, 179, 230, 100)   # Medium blue
        }
        
        # Current medium selections
        self.current_medium1 = 'Air'
        self.current_medium2 = 'Water'
        self.current_medium3 = 'Glass (Crown)'
        
        # Create the medium regions (transparent colored rectangles)
        self.medium1_region = pg.LinearRegionItem([0, self.boundary1], movable=False, 
                                                brush=QBrush(QColor(*self.medium_colors['Air'])))
        self.medium2_region = pg.LinearRegionItem([self.boundary1, self.boundary2], movable=False, 
                                                brush=QBrush(QColor(*self.medium_colors['Water'])))
        self.medium3_region = pg.LinearRegionItem([self.boundary2, 3000], movable=False, 
                                                brush=QBrush(QColor(*self.medium_colors['Glass (Crown)'])))
        
        # Add regions to plot
        self.addItem(self.medium1_region)
        self.addItem(self.medium2_region)
        self.addItem(self.medium3_region)
        
        # Add boundary lines
        self.boundary1_line = pg.InfiniteLine(pos=self.boundary1, angle=90, pen=pg.mkPen('w', width=2, style=Qt.DashLine))
        self.boundary2_line = pg.InfiniteLine(pos=self.boundary2, angle=90, pen=pg.mkPen('w', width=2, style=Qt.DashLine))
        self.addItem(self.boundary1_line)
        self.addItem(self.boundary2_line)
        
        # Add medium labels
        self.medium1_label = pg.TextItem(f'{self.current_medium1} (n₁ = {self.n1:.4f})', anchor=(0.5, 0), color='w')
        self.medium1_label.setPos(self.boundary1/2, 40)
        self.medium1_label.setFont(QFont("Arial", 12, QFont.Bold))
        
        self.medium2_label = pg.TextItem(f'{self.current_medium2} (n₂ = {self.n2:.4f})', anchor=(0.5, 0), color='w')
        self.medium2_label.setPos(self.boundary1 + (self.boundary2-self.boundary1)/2, 40)
        
        self.medium3_label = pg.TextItem(f'{self.current_medium3} (n₃ = {self.n3:.4f})', anchor=(0.5, 0), color='w')
        self.medium3_label.setPos(self.boundary2 + (3000-self.boundary2)/2, 40)
        
        self.addItem(self.medium1_label)
        self.addItem(self.medium2_label)
        self.addItem(self.medium3_label)
        
        # Create the wave curve for single wavelength
        wave = self.calculate_wave(self.wavelength)
        self.wave_curve = self.plot(self.x, wave, pen=pg.mkPen('b', width=4))
        
        # For white light/prism mode - create multiple curves for different wavelengths
        self.wave_curves = []
        self.prism_wavelengths = [400, 450, 500, 550, 600, 650, 700]  # Different wavelengths
        
        for wl in self.prism_wavelengths:
            # Calculate wave for this wavelength
            wave = self.calculate_wave(wl)
            
            # Get color for this wavelength
            color = wavelength_to_rgb(wl)
            
            # Create curve with this color
            curve = self.plot(self.x, wave, pen=pg.mkPen(color, width=4))
            
            # Hide initially
            curve.setVisible(False)
            
            # Add to list
            self.wave_curves.append((wl, curve))
        
        # Set up the animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(10)  # 50ms interval (20 fps)
        
    def calculate_wave(self, wavelength):
        """Calculate the wave based on current parameters for a specific wavelength"""
        wave = np.zeros_like(self.x)
        
        # We need to adjust refractive indices for wavelength in prism mode
        # This simulates dispersion - different wavelengths refract differently
        if self.prism_mode:
            # Calculate approximate wavelength in nm (for dispersion calculation)
            # Map wavelength 10-100 to 380-750nm (visible spectrum)
            wl_nm = wavelength
            
            # Apply Cauchy's equation for dispersion: n(λ) = A + B/λ² + C/λ⁴
            # Using simplified coefficients for glass-like materials
            n2_wl = self.n2 + 0.0006 * (550 / wl_nm) ** 2
            n3_wl = self.n3 + 0.0008 * (550 / wl_nm) ** 2
        else:
            # No dispersion in normal mode
            n2_wl = self.n2
            n3_wl = self.n3
            
        # Wave parameters for each medium
        k1 = (2 * np.pi * self.n1) / wavelength  # Wave number in medium 1
        k2 = (2 * np.pi * n2_wl) / wavelength    # Wave number in medium 2
        k3 = (2 * np.pi * n3_wl) / wavelength    # Wave number in medium 3
        
        omega = self.speed  # Angular frequency
        
        # Calculate wave in medium 1
        mask1 = self.x <= self.boundary1
        phase1 = k1 * self.x[mask1] - omega * self.time
        wave[mask1] = self.amplitude * self.visualization_scale * np.sin(phase1)
        
        # Calculate wave in medium 2
        mask2 = (self.x > self.boundary1) & (self.x <= self.boundary2)
        phase1_boundary = k1 * self.boundary1 - omega * self.time
        phase2 = k2 * (self.x[mask2] - self.boundary1) - omega * self.time
        wave[mask2] = self.amplitude * self.visualization_scale * np.sin(phase2)
        
        # Calculate wave in medium 3
        mask3 = self.x > self.boundary2
        phase1_boundary = k1 * self.boundary1 - omega * self.time
        phase2_boundary = k2 * (self.boundary2 - self.boundary1)
        phase3 = k3 * (self.x[mask3] - self.boundary2) - omega * self.time
        wave[mask3] = self.amplitude * self.visualization_scale * np.sin(phase3)
        
        return wave
        
    def update_animation(self):
        """Update the animation for each timer tick"""
        self.time += 0.01
        
        if self.white_light:
            # Update multiple waves with different wavelengths
            for wl, curve in self.wave_curves:
                wave = self.calculate_wave(wl)
                curve.setData(self.x, wave)
        else:
            # Update single wave
            wave = self.calculate_wave(self.wavelength)
            self.wave_curve.setData(self.x, wave)
        
    def update_plot(self):
        """Update the plot with current parameters"""
        # Update medium labels
        self.medium1_label.setText(f"{self.current_medium1} (n₁ = {self.n1:.4f})")
        self.medium2_label.setText(f"{self.current_medium2} (n₂ = {self.n2:.4f})")
        self.medium3_label.setText(f"{self.current_medium3} (n₃ = {self.n3:.4f})")
        
        # Update medium colors
        self.medium1_region.setBrush(QBrush(QColor(*self.medium_colors[self.current_medium1])))
        self.medium2_region.setBrush(QBrush(QColor(*self.medium_colors[self.current_medium2])))
        self.medium3_region.setBrush(QBrush(QColor(*self.medium_colors[self.current_medium3])))
        
        # Update wavelength color for single wave mode
        if not self.white_light:
            color = wavelength_to_rgb(self.wavelength)
            self.wave_curve.setPen(pg.mkPen(color, width=4))

      
    def update_wavelength(self, value):
        self.wavelength = value
        self.update_plot()
        
    def update_amplitude(self, value):
        self.amplitude = value
        # Let the zoom control handle the Y range adjustment if it exists
        if hasattr(self, 'parent') and hasattr(self.parent, 'zoom_slider'):
            zoom_factor = self.parent.zoom_slider.value() / 10.0
            y_range = self.amplitude * self.visualization_scale * 1.5 / zoom_factor
            self.setYRange(-y_range, y_range)
        else:
            # Default behavior with visualization scaling
            self.setYRange(-1, 1, padding=0)

    def update_speed(self, value):
        self.speed = value
        
    def update_n1(self, value):
        self.n1 = value
        self.update_plot()
        
    def update_n2(self, value):
        self.n2 = value
        self.update_plot()
        
    def update_n3(self, value):
        self.n3 = value
        self.update_plot()
        
    def update_medium1(self, medium_name):
        self.current_medium1 = medium_name
        self.update_plot()
        
    def update_medium2(self, medium_name):
        self.current_medium2 = medium_name
        self.update_plot()
        
    def update_medium3(self, medium_name):
        self.current_medium3 = medium_name
        self.update_plot()
        
    def toggle_prism_mode(self, enabled):
        """Toggle between normal and prism simulation mode"""
        self.prism_mode = enabled
        self.update_plot()
        
    def toggle_white_light(self, enabled):
        """Toggle between single wavelength and white light (multiple wavelengths)"""
        self.white_light = enabled
        
        # Show/hide appropriate wave curves
        self.wave_curve.setVisible(not enabled)
        
        for _, curve in self.wave_curves:
            curve.setVisible(enabled)
        
        # Update title
        if enabled:
            self.setTitle('White Light Dispersion (Prism Effect)')
        else:
            self.setTitle('Light Wave Refraction Visualization')



class LightSimulationApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Light Wave Refraction Simulation")
        self.setGeometry(100, 100, 1000, 800)
        
        # Set dark mode stylesheet
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QGroupBox {
                border: 1px solid #ffffff;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
            }
            QLabel, QSlider, QComboBox, QCheckBox, QPushButton {
                color: #ffffff;
            }
            QTabWidget::pane {
                border: 1px solid #ffffff;
            }
            QTabBar::tab {
                background: #3c3c3c;
                color: #ffffff;
                padding: 5px;
            }
            QTabBar::tab:selected {
                background: #2b2b2b;
            }
        """)

        # Medium presets (refractive indices at ~550nm wavelength)
        self.medium_presets = {
            'Air': 1.0003,
            'Water': 1.33,
            'Glass (Crown)': 1.52,
            'Glass (Flint)': 1.62,
            'Diamond': 2.42,
            'Acrylic': 1.49,
            'Glycerine': 1.47,
            'Ethanol': 1.36,
            'Quartz': 1.54,
            'Sapphire': 1.77
        }
        
        # Preset scenarios
        self.scenario_materials = {
            'Air → Water → Glass': ('Air', 'Water', 'Glass (Crown)'),
            'Air → Glass → Water': ('Air', 'Glass (Crown)', 'Water'),
            'Water → Air → Glass': ('Water', 'Air', 'Glass (Crown)'),
            'Air → Diamond → Glass': ('Air', 'Diamond', 'Glass (Crown)'),
            'Glass → Air → Water': ('Glass (Crown)', 'Air', 'Water')
        }
        
        # Create the main widget and layout
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        
        self.main_layout = QVBoxLayout()
        self.main_widget.setLayout(self.main_layout)
        
        # Create tabs for different modes
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)
        
        # Create the wave tab
        self.wave_tab = QWidget()
        self.wave_layout = QVBoxLayout()
        self.wave_tab.setLayout(self.wave_layout)
        
        # Create the wave visualization
        self.wave_widget = WaveSimulationWidget()
        self.wave_layout.addWidget(self.wave_widget)
        
        # Add wave controls
        self.setup_wave_controls()
        
       
        
       
        
       
        
        # Add tabs to the tab widget
        self.tabs.addTab(self.wave_tab, "Wave Refraction")
        
        
        # Connect the tab change event
        self.tabs.currentChanged.connect(self.on_tab_changed)
    
    def setup_wave_controls(self):
        """Set up the control panel for wave simulation"""
        # Create controls container
        controls_container = QWidget()
        controls_layout = QHBoxLayout()
        controls_container.setLayout(controls_layout)
        
        
        # Add to main layout
        self.wave_layout.addWidget(controls_container)
        
        # Left controls group (wave properties)
        wave_group = QGroupBox("Wave Properties")
        wave_layout = QVBoxLayout()
        wave_group.setLayout(wave_layout)
        controls_layout.addWidget(wave_group)
        
        # Wavelength slider
        wavelength_layout = QHBoxLayout()
        wavelength_label = QLabel("Wavelength:")
        self.wavelength_slider = QSlider(Qt.Horizontal)
        self.wavelength_slider.setMinimum(380)
        self.wavelength_slider.setMaximum(750)
        self.wavelength_slider.setValue(550)
        self.wavelength_value = QLabel("550 nm")
        
        wavelength_layout.addWidget(wavelength_label)
        wavelength_layout.addWidget(self.wavelength_slider)
        wavelength_layout.addWidget(self.wavelength_value)
        wave_layout.addLayout(wavelength_layout)
        
        # Amplitude slider
        amplitude_layout = QHBoxLayout()
        amplitude_label = QLabel("Amplitude:")
        self.amplitude_slider = QSlider(Qt.Horizontal)
        self.amplitude_slider.setMinimum(1)
        self.amplitude_slider.setMaximum(10)
        self.amplitude_slider.setValue(5)
        self.amplitude_value = QLabel("20")
        
        amplitude_layout.addWidget(amplitude_label)
        amplitude_layout.addWidget(self.amplitude_slider)
        amplitude_layout.addWidget(self.amplitude_value)
        wave_layout.addLayout(amplitude_layout)
        
        # Speed slider
        speed_layout = QHBoxLayout()
        speed_label = QLabel("Wave Speed:")
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setMinimum(1)
        self.speed_slider.setMaximum(10)
        self.speed_slider.setValue(2)
        self.speed_value = QLabel("2")
        
        speed_layout.addWidget(speed_label)
        speed_layout.addWidget(self.speed_slider)
        speed_layout.addWidget(self.speed_value)
        wave_layout.addLayout(speed_layout)

        # In the setup_wave_controls method, add this code
        zoom_layout = QHBoxLayout()
        zoom_label = QLabel("Vertical Scale:")
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setMinimum(1)
        self.zoom_slider.setMaximum(20)
        self.zoom_slider.setValue(10)  # Default value
        self.zoom_value = QLabel("1.0x")
        zoom_layout.addWidget(zoom_label)
        zoom_layout.addWidget(self.zoom_slider)
        zoom_layout.addWidget(self.zoom_value)
        wave_layout.addLayout(zoom_layout)  # Add to the wave controls layout

        # Connect the zoom slider to the update_zoom method
        self.zoom_slider.valueChanged.connect(self.update_zoom)
        
        # Simulation modes
        mode_layout = QHBoxLayout()
        self.prism_mode_check = QCheckBox("Enable Dispersion")
        self.white_light_check = QCheckBox("White Light")
        
        mode_layout.addWidget(self.prism_mode_check)
        mode_layout.addWidget(self.white_light_check)
        wave_layout.addLayout(mode_layout)
        
        # Middle group (medium 1)
        medium1_group = QGroupBox("Medium 1")
        medium1_layout = QVBoxLayout()
        medium1_group.setLayout(medium1_layout)
        controls_layout.addWidget(medium1_group)
        
        # Medium 1 selection
        self.medium1_combo = QComboBox()
        for medium in sorted(self.medium_presets.keys()):
            self.medium1_combo.addItem(medium)
        medium1_layout.addWidget(self.medium1_combo)
        
        # Medium 1 n slider
        n1_layout = QHBoxLayout()
        n1_label = QLabel("n₁:")
        self.n1_slider = QSlider(Qt.Horizontal)
        self.n1_slider.setMinimum(100)
        self.n1_slider.setMaximum(300)
        self.n1_slider.setValue(100)
        self.n1_value = QLabel("1.0003")
        
        n1_layout.addWidget(n1_label)
        n1_layout.addWidget(self.n1_slider)
        n1_layout.addWidget(self.n1_value)
        medium1_layout.addLayout(n1_layout)
        
        # Middle group (medium 2)
        medium2_group = QGroupBox("Medium 2")
        medium2_layout = QVBoxLayout()
        medium2_group.setLayout(medium2_layout)
        controls_layout.addWidget(medium2_group)
        
        # Medium 2 selection
        self.medium2_combo = QComboBox()
        for medium in sorted(self.medium_presets.keys()):
            self.medium2_combo.addItem(medium)
        self.medium2_combo.setCurrentText("Water")
        medium2_layout.addWidget(self.medium2_combo)
        
        # Medium 2 n slider
        n2_layout = QHBoxLayout()
        n2_label = QLabel("n₂:")
        self.n2_slider = QSlider(Qt.Horizontal)
        self.n2_slider.setMinimum(100)
        self.n2_slider.setMaximum(300)
        self.n2_slider.setValue(133)
        self.n2_value = QLabel("1.33")
        
        n2_layout.addWidget(n2_label)
        n2_layout.addWidget(self.n2_slider)
        n2_layout.addWidget(self.n2_value)
        medium2_layout.addLayout(n2_layout)
        
        # Right group (medium 3)
        medium3_group = QGroupBox("Medium 3")
        medium3_layout = QVBoxLayout()
        medium3_group.setLayout(medium3_layout)
        controls_layout.addWidget(medium3_group)
        
        # Medium 3 selection
        self.medium3_combo = QComboBox()
        for medium in sorted(self.medium_presets.keys()):
            self.medium3_combo.addItem(medium)
        self.medium3_combo.setCurrentText("Glass (Crown)")
        medium3_layout.addWidget(self.medium3_combo)
        
        # Medium 3 n slider
        n3_layout = QHBoxLayout()
        n3_label = QLabel("n₃:")
        self.n3_slider = QSlider(Qt.Horizontal)
        self.n3_slider.setMinimum(100)
        self.n3_slider.setMaximum(300)
        self.n3_slider.setValue(152)
        self.n3_value = QLabel("1.52")
        
        n3_layout.addWidget(n3_label)
        n3_layout.addWidget(self.n3_slider)
        n3_layout.addWidget(self.n3_value)
        medium3_layout.addLayout(n3_layout)
        
        # Scenario presets
        scenario_group = QGroupBox("Presets")
        scenario_layout = QVBoxLayout()
        scenario_group.setLayout(scenario_layout)
        controls_layout.addWidget(scenario_group)
        
        self.scenario_combo = QComboBox()
        for scenario in self.scenario_materials.keys():
            self.scenario_combo.addItem(scenario)
        scenario_layout.addWidget(self.scenario_combo)
        
        apply_button = QPushButton("Apply Preset")
        scenario_layout.addWidget(apply_button)
        
        # Connect signals
        self.wavelength_slider.valueChanged.connect(self.update_wavelength)
        self.amplitude_slider.valueChanged.connect(self.update_amplitude)
        self.speed_slider.valueChanged.connect(self.update_speed)
        
        self.n1_slider.valueChanged.connect(self.update_n1)
        self.n2_slider.valueChanged.connect(self.update_n2)
        self.n3_slider.valueChanged.connect(self.update_n3)
        
        self.medium1_combo.currentTextChanged.connect(self.update_medium1)
        self.medium2_combo.currentTextChanged.connect(self.update_medium2)
        self.medium3_combo.currentTextChanged.connect(self.update_medium3)
        
        
        self.white_light_check.stateChanged.connect(self.toggle_white_light)
        
        apply_button.clicked.connect(self.apply_scenario)
    
    
    def on_tab_changed(self, index):
        """Handle tab change event"""
        # Pause/resume appropriate timers based on visible tab
        if index == 0:  # Wave tab
            self.wave_widget.timer.start(50)
        else:
            self.wave_widget.timer.stop()
            
    # --- Wave Control Event Handlers ---
    def update_wavelength(self, value):
        """Update wavelength value"""
        self.wavelength_value.setText(f"{value} nm")
        self.wave_widget.update_wavelength(value)
        
    def update_amplitude(self, value):
        """Update amplitude value"""
        self.amplitude_value.setText(str(value))
        self.wave_widget.update_amplitude(value)
        
    def update_speed(self, value):
        """Update speed value"""
        self.speed_value.setText(str(value))
        self.wave_widget.update_speed(value)
        
    def update_n1(self, value):
        """Update refractive index of medium 1"""
        n = value / 100
        self.n1_value.setText(f"{n:.4f}")
        self.wave_widget.update_n1(n)
        
    def update_n2(self, value):
        """Update refractive index of medium 2"""
        n = value / 100
        self.n2_value.setText(f"{n:.4f}")
        self.wave_widget.update_n2(n)
        
    def update_n3(self, value):
        """Update refractive index of medium 3"""
        n = value / 100
        self.n3_value.setText(f"{n:.4f}")
        self.wave_widget.update_n3(n)
        
    def update_medium1(self, medium_name):
        """Update medium 1 selection"""
        n = self.medium_presets[medium_name]
        self.n1_slider.setValue(int(n * 100))
        self.wave_widget.update_medium1(medium_name)
        
    def update_medium2(self, medium_name):
        """Update medium 2 selection"""
        n = self.medium_presets[medium_name]
        self.n2_slider.setValue(int(n * 100))
        self.wave_widget.update_medium2(medium_name)
        
    def update_medium3(self, medium_name):
        """Update medium 3 selection"""
        n = self.medium_presets[medium_name]
        self.n3_slider.setValue(int(n * 100))
        self.wave_widget.update_medium3(medium_name)
        
    

    def update_zoom(self, value):
    #Update vertical zoom factor#
        zoom_factor = value / 10.0  # Convert to a scale where 10 = 1.0x
        self.zoom_value.setText(f"{zoom_factor:.1f}x")
    # Adjust the y-range of the plot widget
        amplitude = self.wave_widget.amplitude
        y_range = amplitude * 1.5 / zoom_factor
        self.wave_widget.setYRange(-y_range, y_range)
        
            
    def toggle_white_light(self, state):
        """Toggle white light mode"""
        enabled = state == Qt.Checked
        self.wave_widget.toggle_white_light(enabled)
        
    def apply_scenario(self):
        """Apply selected scenario preset"""
        scenario = self.scenario_combo.currentText()
        medium1, medium2, medium3 = self.scenario_materials[scenario]
        
        self.medium1_combo.setCurrentText(medium1)
        self.medium2_combo.setCurrentText(medium2)
        self.medium3_combo.setCurrentText(medium3)
  
    

# Run the application
if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWindow = LightSimulationApp()
    mainWindow.show()
    sys.exit(app.exec_())