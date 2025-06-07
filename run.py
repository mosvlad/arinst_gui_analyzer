#!/usr/bin/env python3
"""
Enhanced Arinst Spectrum Analyzer GUI with Advanced RF Analysis Features
Professional-grade spectrum analyzer with markers, measurements, and data export
"""

import sys
import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import time
import csv
import json
from datetime import datetime
from collections import deque
from arinst_device import ArinstDevice

# Configure PyQtGraph for better performance
pg.setConfigOptions(antialias=True, useOpenGL=True)

class SpectrumThread(QThread):
    """Enhanced spectrum scanning thread with data recording"""
    spectrum_data = pyqtSignal(list, list, float)
    scan_error = pyqtSignal(str)
    
    def __init__(self, device):
        super().__init__()
        self.device = device
        self.running = False
        self.scan_config = {
            'start': 1500000000,
            'stop': 1700000000,
            'step': 1000000,
            'attenuation': 0,
            'tracking': False
        }
        self.recording = False
        self.recorded_data = []
        
    def configure_scan(self, **params):
        self.scan_config.update(params)
    
    def start_scan(self):
        self.running = True
        self.start()
    
    def stop_scan(self):
        self.running = False
        self.quit()
        self.wait()
    
    def start_recording(self):
        self.recording = True
        self.recorded_data = []
    
    def stop_recording(self):
        self.recording = False
        return self.recorded_data.copy()
    
    def run(self):
        while self.running:
            try:
                # Convert config keys to match device method parameters
                scan_params = {
                    'start': self.scan_config.get('start_freq', self.scan_config.get('start', 1500000000)),
                    'stop': self.scan_config.get('stop_freq', self.scan_config.get('stop', 1700000000)),
                    'step': self.scan_config.get('step_freq', self.scan_config.get('step', 1000000)),
                    'attenuation': self.scan_config.get('attenuation', 0),
                    'tracking': self.scan_config.get('tracking', False)
                }
                
                amplitudes = self.device.get_scan_range(**scan_params)
                
                if amplitudes:
                    num_points = len(amplitudes)
                    start_freq = scan_params['start']
                    step_freq = scan_params['step']
                    frequencies = [start_freq + i * step_freq for i in range(num_points)]
                    
                    timestamp = time.time()
                    
                    if self.recording:
                        self.recorded_data.append({
                            'timestamp': timestamp,
                            'frequencies': frequencies,
                            'amplitudes': amplitudes
                        })
                    
                    self.spectrum_data.emit(frequencies, amplitudes, timestamp)
                else:
                    self.scan_error.emit("No data received")
                
                self.msleep(50)  # 20 Hz update rate
                
            except Exception as e:
                self.scan_error.emit(f"Scan error: {str(e)}")
                self.msleep(1000)

class WaterfallWidget(QWidget):
    """Waterfall display for time-frequency analysis"""
    
    def __init__(self):
        super().__init__()
        self.waterfall_data = deque(maxlen=100)  # Store exactly 100 traces max
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Waterfall plot
        self.waterfall_plot = pg.PlotWidget()
        self.waterfall_plot.setLabel('left', 'Time (traces)', color='white')
        self.waterfall_plot.setLabel('bottom', 'Frequency (GHz)', color='white')
        self.waterfall_plot.setBackground('#1a1a1a')
        
        # Configure axes
        for axis in ['left', 'bottom']:
            ax = self.waterfall_plot.getAxis(axis)
            ax.setPen(pg.mkPen(color='white', width=1))
            ax.setTextPen(pg.mkPen(color='white'))
        
        # Image item for waterfall
        self.waterfall_img = pg.ImageItem()
        self.waterfall_plot.addItem(self.waterfall_img)
        
        # Color map
        colormap = pg.colormap.get('viridis')
        self.waterfall_img.setColorMap(colormap)
        
        layout.addWidget(self.waterfall_plot)
        
        # Status bar
        self.status_label = QLabel("Traces: 0 | Range: -- MHz | Duration: --")
        self.status_label.setStyleSheet("color: #888888; font-size: 8pt; padding: 2px;")
        layout.addWidget(self.status_label)
        
        # Controls
        controls = QHBoxLayout()
        
        # Colormap selection
        self.colormap_selector = QComboBox()
        self.colormap_selector.addItems(['viridis', 'plasma', 'inferno', 'magma', 'hot', 'cool', 'jet'])
        self.colormap_selector.currentTextChanged.connect(self.change_colormap)
        controls.addWidget(QLabel("Color:"))
        controls.addWidget(self.colormap_selector)
        
        # Intensity controls
        self.auto_levels_cb = QCheckBox("Auto Levels")
        self.auto_levels_cb.setChecked(True)
        self.auto_levels_cb.toggled.connect(self.toggle_auto_levels)
        controls.addWidget(self.auto_levels_cb)
        
        controls.addStretch()
        
        self.clear_btn = QPushButton("🗑 Clear")
        self.clear_btn.clicked.connect(self.clear_waterfall)
        controls.addWidget(self.clear_btn)
        
        self.save_btn = QPushButton("💾 Save")
        self.save_btn.clicked.connect(self.save_waterfall)
        controls.addWidget(self.save_btn)
        
        layout.addLayout(controls)
    
    def add_trace(self, frequencies, amplitudes):
        """Add a new trace to the waterfall with sliding window (max 100 traces)"""
        if len(frequencies) == 0 or len(amplitudes) == 0:
            return
            
        try:
            # Ensure we have consistent data length
            if len(self.waterfall_data) > 0:
                # Check if new data has same length as existing data
                existing_length = len(self.waterfall_data[0])
                if len(amplitudes) != existing_length:
                    # Data length changed - clear old data to avoid issues
                    self.waterfall_data.clear()
                    print(f"Waterfall: Data length changed from {existing_length} to {len(amplitudes)}, clearing buffer")
            
            # Add new trace - deque automatically removes oldest when maxlen=100 is reached
            self.waterfall_data.append(list(amplitudes))  # Convert to list to avoid reference issues
            
            # Update display and status
            self.update_display(frequencies)
            self.update_status(frequencies)
            
        except Exception as e:
            print(f"Waterfall add_trace error: {e}")
            # Recovery: clear data and try again
            self.waterfall_data.clear()
            self.waterfall_data.append(list(amplitudes))
    
    def update_display(self, frequencies):
        """Update waterfall display with robust error handling for 100-trace limit"""
        try:
            if len(self.waterfall_data) == 0:
                return
                
            # Create numpy array from deque data
            # Convert each trace to list to ensure we have clean data
            trace_list = [list(trace) for trace in self.waterfall_data]
            
            # Verify all traces have same length
            if len(trace_list) > 0:
                first_len = len(trace_list[0])
                if not all(len(trace) == first_len for trace in trace_list):
                    print(f"Waterfall: Inconsistent trace lengths detected, cleaning up")
                    # Keep only traces with the most common length
                    from collections import Counter
                    length_counts = Counter(len(trace) for trace in trace_list)
                    most_common_length = length_counts.most_common(1)[0][0]
                    trace_list = [trace for trace in trace_list if len(trace) == most_common_length]
                    
                    # Update the deque with cleaned data
                    self.waterfall_data = deque(trace_list, maxlen=100)
            
            if len(trace_list) == 0:
                return
                
            # Convert to numpy array and transpose
            # Shape will be [frequency_points, time_traces]
            data_array = np.array(trace_list).T
            
            if data_array.size == 0:
                return
                
            # Update image
            auto_levels = self.auto_levels_cb.isChecked()
            self.waterfall_img.setImage(data_array, autoLevels=auto_levels)
            
            if not auto_levels:
                # Set fixed levels for better contrast
                self.waterfall_img.setLevels([-120, -40])
            
            # Set proper scaling
            if frequencies and len(frequencies) > 0:
                freq_min = frequencies[0] / 1e9  # Convert to GHz
                freq_max = frequencies[-1] / 1e9  # Convert to GHz
                time_range = len(trace_list)
                
                # setRect(x, y, width, height)
                # x = frequency start, y = 0 (time start)
                # width = frequency span, height = number of traces
                self.waterfall_img.setRect(QRectF(freq_min, 0, freq_max - freq_min, time_range))
                
        except Exception as e:
            print(f"Waterfall update_display error: {e}")
            # Recovery: clear all data
            self.waterfall_data.clear()
            self.waterfall_img.clear()
    
    def clear_waterfall(self):
        """Clear waterfall data and display"""
        self.waterfall_data.clear()
        self.waterfall_img.clear()
        # Force update to ensure display is properly cleared
        self.waterfall_img.setImage(np.array([]), autoLevels=True)
        self.status_label.setText("Traces: 0 | Range: -- MHz | Duration: --")
    
    def save_waterfall(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Waterfall", 
            f"waterfall_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            "PNG Files (*.png)"
        )
        if filename:
            exporter = pg.exporters.ImageExporter(self.waterfall_plot.plotItem)
            exporter.export(filename)
    
    def change_colormap(self, colormap_name):
        """Change the waterfall colormap"""
        try:
            colormap = pg.colormap.get(colormap_name)
            self.waterfall_img.setColorMap(colormap)
        except:
            # Fallback to default if colormap not found
            colormap = pg.colormap.get('viridis')
            self.waterfall_img.setColorMap(colormap)
    
    def toggle_auto_levels(self, auto):
        """Toggle automatic level adjustment for 100-trace waterfall"""
        try:
            if len(self.waterfall_data) > 0:
                # Create consistent data array
                trace_list = [list(trace) for trace in self.waterfall_data]
                data_array = np.array(trace_list).T
                
                if data_array.size > 0:
                    self.waterfall_img.setImage(data_array, autoLevels=auto)
                    if not auto:
                        # Set fixed levels for better contrast
                        self.waterfall_img.setLevels([-120, -40])
        except Exception as e:
            print(f"Auto levels toggle error: {e}")
            # Clear problematic data
            self.waterfall_data.clear()
    
    def update_status(self, frequencies):
        """Update waterfall status information for 100-trace sliding window"""
        num_traces = len(self.waterfall_data)
        max_traces = 100
        
        if frequencies and len(frequencies) > 0:
            freq_range = (frequencies[-1] - frequencies[0]) / 1e6  # MHz
            duration_min = num_traces * 0.05 / 60  # Assuming ~50ms per trace
            
            # Show sliding window status
            if num_traces >= max_traces:
                status_text = f"Traces: {num_traces}/{max_traces} (sliding) | Range: {freq_range:.1f} MHz | Duration: {duration_min:.1f} min"
            else:
                status_text = f"Traces: {num_traces}/{max_traces} | Range: {freq_range:.1f} MHz | Duration: {duration_min:.1f} min"
                
            self.status_label.setText(status_text)
        else:
            self.status_label.setText(f"Traces: {num_traces}/{max_traces} | Range: -- MHz | Duration: --")
 
class MarkerManager(QWidget):
    """Advanced marker management with delta measurements"""
    
    def __init__(self, plot_widget):
        super().__init__()
        self.plot_widget = plot_widget
        self.markers = {}
        self.marker_lines = {}
        self.current_data = {'frequencies': [], 'amplitudes': []}
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("📍 MARKERS")
        title.setFont(QFont("Arial", 10, QFont.Bold))
        title.setStyleSheet("color: #00ff88; padding: 5px;")
        layout.addWidget(title)
        
        # Controls
        controls = QHBoxLayout()
        self.add_btn = QPushButton("+ Add")
        self.add_btn.clicked.connect(self.add_marker)
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self.clear_markers)
        
        controls.addWidget(self.add_btn)
        controls.addWidget(self.clear_btn)
        layout.addLayout(controls)
        
        # Marker list
        self.marker_list = QListWidget()
        self.marker_list.setMaximumHeight(120)
        layout.addWidget(self.marker_list)
        
        # Delta measurements
        delta_label = QLabel("DELTA MEASUREMENTS")
        delta_label.setFont(QFont("Arial", 9, QFont.Bold))
        layout.addWidget(delta_label)
        
        self.delta_display = QTextEdit()
        self.delta_display.setMaximumHeight(100)
        self.delta_display.setReadOnly(True)
        layout.addWidget(self.delta_display)
    
    def add_marker(self):
        if not self.current_data['amplitudes']:
            QMessageBox.warning(self, "No Data", "No spectrum data available")
            return
        
        # Find peak automatically
        amps = np.array(self.current_data['amplitudes'])
        freqs = np.array(self.current_data['frequencies'])
        peak_idx = np.argmax(amps)
        peak_freq = freqs[peak_idx]
        peak_amp = amps[peak_idx]
        
        marker_id = f"M{len(self.markers) + 1}"
        color = self.get_marker_color(len(self.markers))
        
        # Create marker line
        marker_line = pg.InfiniteLine(
            angle=90, 
            pos=peak_freq/1e9,  # Convert to GHz
            pen=pg.mkPen(color=color, width=2),
            label=marker_id,
            labelOpts={'position': 0.95, 'color': color}
        )
        
        self.plot_widget.addItem(marker_line)
        
        # Store marker
        self.markers[marker_id] = {
            'frequency': peak_freq,
            'amplitude': peak_amp,
            'color': color,
            'line': marker_line
        }
        
        self.marker_lines[marker_id] = marker_line
        self.update_display()
    
    def get_marker_color(self, index):
        colors = ['#ff4444', '#44ff44', '#4444ff', '#ffff44', '#ff44ff', '#44ffff']
        return colors[index % len(colors)]
    
    def clear_markers(self):
        for marker_line in self.marker_lines.values():
            self.plot_widget.removeItem(marker_line)
        
        self.markers.clear()
        self.marker_lines.clear()
        self.update_display()
    
    def update_data(self, frequencies, amplitudes):
        self.current_data = {'frequencies': frequencies, 'amplitudes': amplitudes}
        
        # Update marker amplitudes
        for marker_id, marker in self.markers.items():
            if frequencies:
                freq_array = np.array(frequencies)
                closest_idx = np.argmin(np.abs(freq_array - marker['frequency']))
                marker['amplitude'] = amplitudes[closest_idx]
        
        self.update_display()
    
    def update_display(self):
        self.marker_list.clear()
        
        for marker_id, marker in self.markers.items():
            text = f"{marker_id}: {marker['frequency']/1e6:.3f} MHz → {marker['amplitude']:.2f} dBm"
            self.marker_list.addItem(text)
        
        self.update_delta_measurements()
    
    def update_delta_measurements(self):
        if len(self.markers) < 2:
            self.delta_display.clear()
            return
        
        markers = list(self.markers.values())
        text = ""
        
        for i in range(len(markers)):
            for j in range(i + 1, len(markers)):
                m1, m2 = markers[i], markers[j]
                delta_freq = abs(m1['frequency'] - m2['frequency'])
                delta_amp = m2['amplitude'] - m1['amplitude']
                
                text += f"M{i+1}→M{j+1}: Δf={delta_freq/1e6:.3f}MHz, Δa={delta_amp:.2f}dB\n"
        
        self.delta_display.setPlainText(text)

class MeasurementWidget(QWidget):
    """Advanced RF measurements"""
    
    def __init__(self):
        super().__init__()
        self.current_data = {'frequencies': [], 'amplitudes': []}
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("📏 MEASUREMENTS")
        title.setFont(QFont("Arial", 10, QFont.Bold))
        title.setStyleSheet("color: #00ff88; padding: 5px;")
        layout.addWidget(title)
        
        # Quick measurements
        quick_group = QGroupBox("Quick Analysis")
        quick_layout = QGridLayout()
        
        measurements = [
            ("📊 Channel Power", self.channel_power),
            ("🎯 Peak Search", self.peak_search),
            ("📡 Occupied BW", self.occupied_bw),
            ("📈 Noise Floor", self.noise_floor)
        ]
        
        for i, (text, callback) in enumerate(measurements):
            btn = QPushButton(text)
            btn.clicked.connect(callback)
            quick_layout.addWidget(btn, i // 2, i % 2)
        
        quick_group.setLayout(quick_layout)
        layout.addWidget(quick_group)
        
        # Results display
        self.results = QTextEdit()
        self.results.setMaximumHeight(200)
        layout.addWidget(self.results)
        
        # Quick stats
        stats_label = QLabel("LIVE STATISTICS")
        stats_label.setFont(QFont("Arial", 9, QFont.Bold))
        layout.addWidget(stats_label)
        
        self.stats = QTextEdit()
        self.stats.setMaximumHeight(100)
        self.stats.setReadOnly(True)
        layout.addWidget(self.stats)
    
    def update_data(self, frequencies, amplitudes):
        self.current_data = {'frequencies': frequencies, 'amplitudes': amplitudes}
        self.update_stats()
    
    def update_stats(self):
        if not self.current_data['amplitudes']:
            return
        
        freqs = np.array(self.current_data['frequencies'])
        amps = np.array(self.current_data['amplitudes'])
        
        peak_idx = np.argmax(amps)
        peak_freq = freqs[peak_idx] / 1e6
        peak_amp = amps[peak_idx]
        avg_amp = np.mean(amps)
        min_amp = np.min(amps)
        
        stats_text = f"""Peak: {peak_freq:.3f} MHz @ {peak_amp:.1f} dBm
Average: {avg_amp:.1f} dBm | Min: {min_amp:.1f} dBm
Dynamic Range: {peak_amp - min_amp:.1f} dB
Points: {len(amps)} | Span: {(freqs[-1]-freqs[0])/1e6:.1f} MHz"""
        
        self.stats.setPlainText(stats_text)
    
    def channel_power(self):
        if not self.current_data['frequencies']:
            return
        
        # Simple dialog for parameters
        center, ok1 = QInputDialog.getDouble(self, "Channel Power", "Center Freq (MHz):", 2450, 1, 6000, 3)
        if not ok1:
            return
        
        bw, ok2 = QInputDialog.getDouble(self, "Channel Power", "Bandwidth (MHz):", 20, 0.1, 1000, 3)
        if not ok2:
            return
        
        freqs = np.array(self.current_data['frequencies'])
        amps = np.array(self.current_data['amplitudes'])
        
        # Channel boundaries
        start_freq = (center - bw/2) * 1e6
        stop_freq = (center + bw/2) * 1e6
        
        mask = (freqs >= start_freq) & (freqs <= stop_freq)
        if not np.any(mask):
            self.results.append("❌ No data in channel\n")
            return
        
        # Calculate power
        channel_amps = amps[mask]
        linear_power = 10**(channel_amps/10)
        total_power_mw = np.sum(linear_power)
        total_power_dbm = 10 * np.log10(total_power_mw)
        
        result = f"""📊 CHANNEL POWER
Center: {center:.3f} MHz | BW: {bw:.3f} MHz
Total Power: {total_power_dbm:.2f} dBm
Peak in Channel: {np.max(channel_amps):.2f} dBm
Time: {datetime.now().strftime('%H:%M:%S')}

"""
        self.results.append(result)
    
    def peak_search(self):
        if not self.current_data['frequencies']:
            return
        
        freqs = np.array(self.current_data['frequencies'])
        amps = np.array(self.current_data['amplitudes'])
        
        # Find peaks
        peaks = []
        threshold = np.max(amps) - 20  # 20dB below peak
        
        for i in range(1, len(amps)-1):
            if (amps[i] > amps[i-1] and amps[i] > amps[i+1] and 
                amps[i] > threshold):
                peaks.append((freqs[i], amps[i]))
        
        peaks.sort(key=lambda x: x[1], reverse=True)
        
        result = f"""🎯 PEAK SEARCH (Top 5)
Threshold: {threshold:.1f} dBm

"""
        for i, (freq, amp) in enumerate(peaks[:5]):
            result += f"{i+1}. {freq/1e6:8.3f} MHz → {amp:6.2f} dBm\n"
        
        result += f"\nTime: {datetime.now().strftime('%H:%M:%S')}\n\n"
        self.results.append(result)
    
    def occupied_bw(self):
        if not self.current_data['frequencies']:
            return
        
        freqs = np.array(self.current_data['frequencies'])
        amps = np.array(self.current_data['amplitudes'])
        
        # 99% occupied bandwidth
        linear_power = 10**(amps/10)
        cumulative_power = np.cumsum(linear_power)
        total_power = cumulative_power[-1]
        
        lower_idx = np.argmax(cumulative_power >= 0.005 * total_power)
        upper_idx = np.argmax(cumulative_power >= 0.995 * total_power)
        
        if lower_idx == upper_idx:
            self.results.append("❌ Insufficient data for OBW\n")
            return
        
        obw_hz = freqs[upper_idx] - freqs[lower_idx]
        center_freq = (freqs[upper_idx] + freqs[lower_idx]) / 2
        
        result = f"""📡 OCCUPIED BANDWIDTH (99%)
OBW: {obw_hz/1e6:.3f} MHz
Center: {center_freq/1e6:.3f} MHz
Lower: {freqs[lower_idx]/1e6:.3f} MHz
Upper: {freqs[upper_idx]/1e6:.3f} MHz
Time: {datetime.now().strftime('%H:%M:%S')}

"""
        self.results.append(result)
    
    def noise_floor(self):
        if not self.current_data['frequencies']:
            return
        
        amps = np.array(self.current_data['amplitudes'])
        
        # Statistical noise floor
        sorted_amps = np.sort(amps)
        bottom_10_pct = sorted_amps[:len(sorted_amps)//10]
        noise_floor = np.mean(bottom_10_pct)
        noise_std = np.std(bottom_10_pct)
        
        peak_amp = np.max(amps)
        dynamic_range = peak_amp - noise_floor
        
        result = f"""📈 NOISE FLOOR ANALYSIS
Estimated Floor: {noise_floor:.2f} dBm
Noise Std Dev: {noise_std:.2f} dB
Peak Amplitude: {peak_amp:.2f} dBm
Dynamic Range: {dynamic_range:.1f} dB
Time: {datetime.now().strftime('%H:%M:%S')}

"""
        self.results.append(result)

class EnhancedSpectrumAnalyzer(QMainWindow):
    """Enhanced spectrum analyzer with advanced features"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize
        self.device = None
        self.scan_thread = None
        self.scanning = False
        self.peak_hold_data = []
        self.max_hold_data = []
        self.reference_data = []
        
        # Setup UI
        self.setup_ui()
        self.disable_device_controls()
        
        # Status timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(1000)
    
    def setup_ui(self):
        self.setWindowTitle("Arinst Professional Spectrum Analyzer - Advanced RF Analysis Tool")
        self.setGeometry(50, 50, 1800, 1000)
        
        # Apply enhanced styling
        self.apply_professional_theme()
        
        # Main layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        
        # Left panel - device controls
        left_panel = self.create_control_panel()
        main_layout.addWidget(left_panel, 0)
        
        # Center panel - displays
        center_panel = self.create_display_panel()
        main_layout.addWidget(center_panel, 2)
        
        # Right panel - analysis tools
        right_panel = self.create_analysis_panel()
        main_layout.addWidget(right_panel, 0)
        
        self.create_status_bar()
        self.create_menu_bar()
    
    def apply_professional_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QWidget {
                background-color: #1a1a1a;
                color: #ffffff;
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 9pt;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #404040;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 15px;
                background-color: #2a2a2a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                color: #00cc88;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a90e2, stop:1 #357abd);
                border: 2px solid #357abd;
                border-radius: 6px;
                color: white;
                font-weight: bold;
                font-size: 9pt;
                padding: 6px 12px;
                min-height: 25px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5ba0f2, stop:1 #4a90e2);
            }
            QPushButton:pressed {
                background: #357abd;
            }
            QPushButton:disabled {
                background: #555555;
                border-color: #333333;
                color: #888888;
            }
            QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #3a3a3a;
                border: 2px solid #555555;
                border-radius: 4px;
                padding: 4px 8px;
                color: #ffffff;
                font-size: 9pt;
                min-height: 22px;
            }
            QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border-color: #00cc88;
            }
            QTextEdit, QListWidget {
                background-color: #2a2a2a;
                border: 2px solid #555555;
                border-radius: 4px;
                color: #ffffff;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 8pt;
                padding: 4px;
            }
            QTabWidget::pane {
                border: 2px solid #555555;
                background-color: #2a2a2a;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #3a3a3a;
                color: #ffffff;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #00cc88;
                color: #000000;
            }
            QCheckBox {
                color: #ffffff;
                font-size: 9pt;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #555555;
                background-color: #3a3a3a;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #00cc88;
                background-color: #00cc88;
                border-radius: 3px;
            }
        """)

    def create_control_panel(self):
        panel = QWidget()
        panel.setFixedWidth(280)
        layout = QVBoxLayout(panel)
        
        # Device connection
        conn_group = QGroupBox("Device Connection")
        conn_layout = QFormLayout()
        
        self.port_selector = QComboBox()
        self.update_ports()
        conn_layout.addRow("Port:", self.port_selector)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.update_ports)
        conn_layout.addRow(refresh_btn)
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.toggle_connection)
        conn_layout.addRow(self.connect_btn)
        
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)
        
        # Generator controls
        gen_group = QGroupBox("Signal Generator")
        gen_layout = QFormLayout()
        
        gen_buttons = QHBoxLayout()
        self.gen_on_btn = QPushButton("ON")
        self.gen_off_btn = QPushButton("OFF")
        self.gen_on_btn.clicked.connect(self.generator_on)
        self.gen_off_btn.clicked.connect(self.generator_off)
        gen_buttons.addWidget(self.gen_on_btn)
        gen_buttons.addWidget(self.gen_off_btn)
        gen_layout.addRow("Power:", gen_buttons)
        
        self.freq_input = QDoubleSpinBox()
        self.freq_input.setRange(1, 6000)
        self.freq_input.setValue(1500)
        self.freq_input.setSuffix(" MHz")
        self.freq_input.setDecimals(3)
        gen_layout.addRow("Frequency:", self.freq_input)
        
        self.amp_input = QSpinBox()
        self.amp_input.setRange(-25, -15)
        self.amp_input.setValue(-20)
        self.amp_input.setSuffix(" dBm")
        gen_layout.addRow("Amplitude:", self.amp_input)
        
        self.apply_gen_btn = QPushButton("⚡ Apply Settings")
        self.apply_gen_btn.clicked.connect(self.apply_generator_settings)
        gen_layout.addRow(self.apply_gen_btn)
        
        gen_group.setLayout(gen_layout)
        layout.addWidget(gen_group)
        
        # Scan controls
        scan_group = QGroupBox("Spectrum Scan")
        scan_layout = QFormLayout()
        
        self.start_freq = QDoubleSpinBox()
        self.start_freq.setRange(1, 6000)
        self.start_freq.setValue(2450)
        self.start_freq.setSuffix(" MHz")
        self.start_freq.setDecimals(3)
        scan_layout.addRow("Start:", self.start_freq)
        
        self.stop_freq = QDoubleSpinBox()
        self.stop_freq.setRange(1, 6000)
        self.stop_freq.setValue(2500)
        self.stop_freq.setSuffix(" MHz")
        self.stop_freq.setDecimals(3)
        scan_layout.addRow("Stop:", self.stop_freq)
        
        self.step_freq = QDoubleSpinBox()
        self.step_freq.setRange(0.001, 100)
        self.step_freq.setValue(1)
        self.step_freq.setSuffix(" MHz")
        self.step_freq.setDecimals(3)
        scan_layout.addRow("Step:", self.step_freq)
        
        self.attenuation_input = QSpinBox()
        self.attenuation_input.setRange(-30, 0)
        self.attenuation_input.setValue(-20)
        self.attenuation_input.setSuffix(" dB")
        scan_layout.addRow("Attenuation:", self.attenuation_input)
        
        self.tracking_mode = QCheckBox("Tracking Mode")
        scan_layout.addRow(self.tracking_mode)
        
        # Scan buttons
        scan_buttons = QHBoxLayout()
        self.scan_btn = QPushButton("▶ Start Scan")
        self.scan_btn.clicked.connect(self.toggle_scan)
        scan_buttons.addWidget(self.scan_btn)
        
        self.single_btn = QPushButton("Single")
        self.single_btn.clicked.connect(self.single_sweep)
        scan_buttons.addWidget(self.single_btn)
        
        scan_layout.addRow(scan_buttons)
        
        scan_group.setLayout(scan_layout)
        layout.addWidget(scan_group)
        
        # Display options
        display_group = QGroupBox("Display")
        display_layout = QFormLayout()
        
        self.peak_hold_cb = QCheckBox("Peak Hold")
        display_layout.addRow(self.peak_hold_cb)
        
        self.max_hold_cb = QCheckBox("Max Hold")
        display_layout.addRow(self.max_hold_cb)
        
        self.averaging_cb = QCheckBox("Averaging")
        display_layout.addRow(self.averaging_cb)
        
        # Reference controls
        ref_buttons = QHBoxLayout()
        self.save_ref_btn = QPushButton("Save Ref")
        self.save_ref_btn.clicked.connect(self.save_reference)
        ref_buttons.addWidget(self.save_ref_btn)
        
        self.clear_ref_btn = QPushButton("Clear Ref")
        self.clear_ref_btn.clicked.connect(self.clear_reference)
        ref_buttons.addWidget(self.clear_ref_btn)
        
        display_layout.addRow("Reference:", ref_buttons)
        
        self.clear_all_btn = QPushButton("🗑 Clear All")
        self.clear_all_btn.clicked.connect(self.clear_all_traces)
        display_layout.addRow(self.clear_all_btn)
        
        display_group.setLayout(display_layout)
        layout.addWidget(display_group)
        
        layout.addStretch()
        return panel
    
    def create_display_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Tabbed display
        self.display_tabs = QTabWidget()
        
        # Spectrum tab
        spectrum_tab = QWidget()
        spectrum_layout = QVBoxLayout(spectrum_tab)
        
        # Main spectrum plot
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#1a1a1a')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('left', 'Amplitude', units='dBm', color='white', size='11pt')
        self.plot_widget.setLabel('bottom', 'Frequency', units='GHz', color='white', size='11pt')
        
        # Configure axes
        for axis in ['left', 'bottom']:
            ax = self.plot_widget.getAxis(axis)
            ax.setPen(pg.mkPen(color='white', width=1))
            ax.setTextPen(pg.mkPen(color='white'))
        
        # Plot curves
        self.main_curve = self.plot_widget.plot(
            pen=pg.mkPen(color='#00ff88', width=2),
            name='Live Spectrum'
        )
        
        self.peak_hold_curve = self.plot_widget.plot(
            pen=pg.mkPen(color='#ff4444', width=1, style=Qt.DotLine),
            name='Peak Hold'
        )
        
        self.max_hold_curve = self.plot_widget.plot(
            pen=pg.mkPen(color='#ffaa00', width=1, style=Qt.DashLine),
            name='Max Hold'
        )
        
        self.ref_curve = self.plot_widget.plot(
            pen=pg.mkPen(color='#4444ff', width=1, style=Qt.DashLine),
            name='Reference'
        )
        
        # Crosshair
        self.crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen='y')
        self.crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen='y')
        self.plot_widget.addItem(self.crosshair_v, ignoreBounds=True)
        self.plot_widget.addItem(self.crosshair_h, ignoreBounds=True)
        
        self.plot_widget.scene().sigMouseMoved.connect(self.mouse_moved)
        
        spectrum_layout.addWidget(self.plot_widget)
        
        # Measurement display
        meas_layout = QHBoxLayout()
        self.freq_label = QLabel("Freq: -- MHz")
        self.amp_label = QLabel("Amp: -- dBm")
        self.peak_freq_label = QLabel("Peak: -- MHz")
        self.peak_amp_label = QLabel("Peak Amp: -- dBm")
        
        meas_layout.addWidget(self.freq_label)
        meas_layout.addWidget(self.amp_label)
        meas_layout.addWidget(self.peak_freq_label)
        meas_layout.addWidget(self.peak_amp_label)
        meas_layout.addStretch()
        
        spectrum_layout.addLayout(meas_layout)
        
        self.display_tabs.addTab(spectrum_tab, "📊 Spectrum")
        
        # Waterfall tab
        self.waterfall_widget = WaterfallWidget()
        self.display_tabs.addTab(self.waterfall_widget, "🌊 Waterfall")
        
        layout.addWidget(self.display_tabs)
        return panel
    
    def create_analysis_panel(self):
        panel = QWidget()
        panel.setFixedWidth(350)
        layout = QVBoxLayout(panel)
        
        # Analysis tabs
        analysis_tabs = QTabWidget()
        
        # Markers
        self.marker_manager = MarkerManager(self.plot_widget)
        analysis_tabs.addTab(self.marker_manager, "📍 Markers")
        
        # Measurements
        self.measurement_widget = MeasurementWidget()
        analysis_tabs.addTab(self.measurement_widget, "📏 Measure")
        
        # Data export
        export_tab = self.create_export_tab()
        analysis_tabs.addTab(export_tab, "💾 Export")
        
        layout.addWidget(analysis_tabs)
        
        # System log
        log_group = QGroupBox("System Log")
        log_layout = QVBoxLayout()
        
        self.log_display = QTextEdit()
        self.log_display.setMaximumHeight(120)
        log_layout.addWidget(self.log_display)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        return panel
    
    def create_export_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Export controls
        export_label = QLabel("📤 DATA EXPORT")
        export_label.setFont(QFont("Arial", 10, QFont.Bold))
        export_label.setStyleSheet("color: #00ff88; padding: 5px;")
        layout.addWidget(export_label)
        
        self.export_csv_btn = QPushButton("📄 Export CSV")
        self.export_csv_btn.clicked.connect(self.export_csv)
        layout.addWidget(self.export_csv_btn)
        
        self.screenshot_btn = QPushButton("📷 Screenshot")
        self.screenshot_btn.clicked.connect(self.save_screenshot)
        layout.addWidget(self.screenshot_btn)
        
        # Recording
        rec_group = QGroupBox("Data Recording")
        rec_layout = QVBoxLayout()
        
        self.record_btn = QPushButton("🔴 Start Recording")
        self.record_btn.clicked.connect(self.toggle_recording)
        rec_layout.addWidget(self.record_btn)
        
        self.record_status = QLabel("Status: Stopped")
        rec_layout.addWidget(self.record_status)
        
        rec_group.setLayout(rec_layout)
        layout.addWidget(rec_group)
        
        layout.addStretch()
        return tab

    def update_ports(self):
        """Update the list of available serial ports"""
        self.port_selector.clear()
        ports = ArinstDevice.list_available_ports()
        for port, description in ports:
            self.port_selector.addItem(f"{port} - {description}", port)
        
        if not ports:
            self.port_selector.addItem("No ports found", None)
            self.log_message("No serial ports found")
        else:
            self.log_message(f"Found {len(ports)} serial port(s)")

    def toggle_connection(self):
        """Toggle device connection"""
        if self.device and self.device.is_connected():
            self.disconnect_device()
        else:
            self.connect_device()

    def connect_device(self):
        """Connect to the selected device"""
        selected_port = self.port_selector.currentData()
        if not selected_port:
            self.log_message("No valid port selected")
            return

        try:
            self.device = ArinstDevice(device=selected_port)
            if self.device.is_connected():
                self.connect_btn.setText("Disconnect")
                self.connect_btn.setStyleSheet("background-color: #cc4400;")
                self.enable_device_controls()
                self.log_message(f"Connected to {selected_port}")
            else:
                self.log_message(f"Failed to connect to {selected_port}")
        except Exception as e:
            self.log_message(f"Connection error: {str(e)}")

    def disconnect_device(self):
        """Disconnect from device"""
        if self.device:
            self.stop_scan()
            self.device.close()
            self.device = None
        
        self.connect_btn.setText("Connect")
        self.connect_btn.setStyleSheet("")
        self.disable_device_controls()
        self.log_message("Device disconnected")

    def enable_device_controls(self):
        """Enable device control widgets"""
        controls = [
            self.gen_on_btn, self.gen_off_btn, self.apply_gen_btn,
            self.scan_btn, self.single_btn, self.freq_input, 
            self.amp_input, self.start_freq, self.stop_freq, 
            self.step_freq, self.attenuation_input
        ]
        for control in controls:
            control.setEnabled(True)

    def disable_device_controls(self):
        """Disable device control widgets"""
        controls = [
            self.gen_on_btn, self.gen_off_btn, self.apply_gen_btn,
            self.scan_btn, self.single_btn, self.freq_input, 
            self.amp_input, self.start_freq, self.stop_freq, 
            self.step_freq, self.attenuation_input
        ]
        for control in controls:
            control.setEnabled(False)

    def generator_on(self):
        """Turn generator on"""
        if self.device:
            try:
                success = self.device.on()
                if success:
                    self.log_message("Generator ON")
                else:
                    self.log_message("Failed to turn generator ON")
            except Exception as e:
                self.log_message(f"Generator ON error: {str(e)}")

    def generator_off(self):
        """Turn generator off"""
        if self.device:
            try:
                success = self.device.off()
                if success:
                    self.log_message("Generator OFF")
                else:
                    self.log_message("Failed to turn generator OFF")
            except Exception as e:
                self.log_message(f"Generator OFF error: {str(e)}")

    def apply_generator_settings(self):
        """Apply generator frequency and amplitude settings"""
        if not self.device:
            return

        try:
            # Convert MHz to Hz for device - use round to avoid floating point precision errors
            freq_hz = round(self.freq_input.value() * 1_000_000)
            amplitude = self.amp_input.value()
            
            freq_success = self.device.set_frequency(freq_hz)
            amp_success = self.device.set_amplitude(amplitude)
            
            if freq_success and amp_success:
                self.log_message(f"Generator set: {self.freq_input.value()} MHz, {amplitude} dBm")
            else:
                self.log_message("Failed to apply generator settings")
        except Exception as e:
            self.log_message(f"Generator settings error: {str(e)}")

    def toggle_scan(self):
        """Toggle spectrum scanning"""
        if self.scanning:
            self.stop_scan()
        else:
            self.start_scan()

    def start_scan(self):
        """Start continuous spectrum scanning"""
        if not self.device:
            self.log_message("No device connected")
            return

        if self.scan_thread and self.scan_thread.isRunning():
            return

        self.scan_thread = SpectrumThread(self.device)
        self.scan_thread.spectrum_data.connect(self.update_spectrum_display)
        self.scan_thread.scan_error.connect(self.log_message)
        
        # Configure scan parameters - use round to avoid floating point precision errors
        start_hz = round(self.start_freq.value() * 1_000_000)
        stop_hz = round(self.stop_freq.value() * 1_000_000)
        step_hz = round(self.step_freq.value() * 1_000_000)
        
        # Validate step size (minimum 1000 Hz = 0.001 MHz)
        if step_hz < 1000:
            step_hz = 1000
            self.log_message("Step size too small, using minimum 0.001 MHz (1000 Hz)")
        
        # Validate frequency range
        if start_hz >= stop_hz:
            self.log_message("Error: Start frequency must be less than stop frequency")
            return
            
        # Check number of scan points (prevent device overload)
        num_points = int((stop_hz - start_hz) / step_hz) + 1
        max_points = 2000
        
        if num_points > max_points:
            # Suggest a better step size
            min_step_hz = int((stop_hz - start_hz) / max_points)
            min_step_mhz = min_step_hz / 1_000_000
            self.log_message(f"Error: Too many scan points ({num_points}). Try step size ≥ {min_step_mhz:.3f} MHz")
            return
            
        self.log_message(f"Scan configuration: {num_points} points")
        
        self.scan_thread.configure_scan(
            start_freq=start_hz,
            stop_freq=stop_hz,
            step_freq=step_hz,
            attenuation=self.attenuation_input.value(),
            tracking=self.tracking_mode.isChecked()
        )
        
        self.scan_thread.start_scan()
        self.scan_thread.start()
        
        self.scanning = True
        self.scan_btn.setText("⏹ Stop Scan")
        self.log_message(f"Started scanning: {self.start_freq.value()}-{self.stop_freq.value()} MHz, step: {self.step_freq.value()} MHz ({step_hz} Hz)")

    def stop_scan(self):
        """Stop spectrum scanning"""
        if self.scan_thread:
            self.scan_thread.stop_scan()
            self.scan_thread.quit()
            self.scan_thread.wait()
            self.scan_thread = None
        
        self.scanning = False
        self.scan_btn.setText("▶ Start Scan")
        self.log_message("Scanning stopped")

    def single_sweep(self):
        """Perform a single spectrum sweep"""
        if not self.device:
            self.log_message("No device connected")
            return

        try:
            # Use round to avoid floating point precision errors
            start_hz = round(self.start_freq.value() * 1_000_000)
            stop_hz = round(self.stop_freq.value() * 1_000_000)
            step_hz = round(self.step_freq.value() * 1_000_000)
            
            # Validate step size (minimum 1000 Hz = 0.001 MHz)
            if step_hz < 1000:
                step_hz = 1000
                self.log_message("Step size too small, using minimum 0.001 MHz (1000 Hz)")
            
            # Validate frequency range
            if start_hz >= stop_hz:
                self.log_message("Error: Start frequency must be less than stop frequency")
                return
                
            # Check number of scan points (prevent device overload)
            num_points = int((stop_hz - start_hz) / step_hz) + 1
            max_points = 2000
            
            if num_points > max_points:
                # Suggest a better step size
                min_step_hz = int((stop_hz - start_hz) / max_points)
                min_step_mhz = min_step_hz / 1_000_000
                self.log_message(f"Error: Too many scan points ({num_points}). Try step size ≥ {min_step_mhz:.3f} MHz")
                return
                
            self.log_message(f"Single sweep: {num_points} points")
            
            amplitudes = self.device.get_scan_range(
                start=start_hz,
                stop=stop_hz,
                step=step_hz,
                attenuation=self.attenuation_input.value(),
                tracking=self.tracking_mode.isChecked()
            )
            
            if amplitudes:
                frequencies = []
                freq = start_hz
                for _ in amplitudes:
                    frequencies.append(freq / 1_000_000)  # Convert to MHz
                    freq += step_hz
                
                self.update_spectrum_display(frequencies, amplitudes, time.time())
                self.log_message("Single sweep completed")
            else:
                self.log_message("Single sweep failed")
        except Exception as e:
            self.log_message(f"Single sweep error: {str(e)}")

    def update_spectrum_display(self, frequencies, amplitudes, timestamp):
        """Update the spectrum display with new data"""
        if not frequencies or not amplitudes:
            return

        # Ensure arrays are the same length (fix device data inconsistency)
        min_len = min(len(frequencies), len(amplitudes))
        if min_len == 0:
            return
            
        frequencies = frequencies[:min_len]
        amplitudes = amplitudes[:min_len]
        
        # Convert MHz to GHz for display
        freq_ghz = [f / 1000.0 for f in frequencies]
        
        try:
            # Update main trace
            self.main_curve.setData(freq_ghz, amplitudes)
            
            # Update peak hold with length validation
            if self.peak_hold_cb.isChecked():
                if not self.peak_hold_data or len(self.peak_hold_data) != len(amplitudes):
                    self.peak_hold_data = amplitudes.copy()
                else:
                    self.peak_hold_data = [max(p, a) for p, a in zip(self.peak_hold_data, amplitudes)]
                self.peak_hold_curve.setData(freq_ghz, self.peak_hold_data)
            
            # Update max hold with length validation
            if self.max_hold_cb.isChecked():
                if not self.max_hold_data or len(self.max_hold_data) != len(amplitudes):
                    self.max_hold_data = amplitudes.copy()
                else:
                    self.max_hold_data = [max(m, a) for m, a in zip(self.max_hold_data, amplitudes)]
                self.max_hold_curve.setData(freq_ghz, self.max_hold_data)
            
            # Update reference if exists and length matches
            if self.reference_data and len(self.reference_data) == len(amplitudes):
                self.ref_curve.setData(freq_ghz, self.reference_data)
        
        except Exception as e:
            self.log_message(f"Display update error: {str(e)}")
            return
        
        # Update waterfall
        self.waterfall_widget.add_trace(frequencies, amplitudes)
        
        # Update analysis widgets
        self.marker_manager.update_data(frequencies, amplitudes)
        self.measurement_widget.update_data(frequencies, amplitudes)
        
        # Find and display peak
        if amplitudes:
            peak_idx = amplitudes.index(max(amplitudes))
            peak_freq = frequencies[peak_idx]
            peak_amp = amplitudes[peak_idx]
            
            self.peak_freq_label.setText(f"Peak: {peak_freq:.3f} MHz")
            self.peak_amp_label.setText(f"Peak Amp: {peak_amp:.1f} dBm")

    def mouse_moved(self, event):
        """Handle mouse movement over plot"""
        if self.plot_widget.plotItem.vb.mapSceneToView(event):
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(event)
            x, y = mouse_point.x(), mouse_point.y()
            
            self.crosshair_v.setPos(x)
            self.crosshair_h.setPos(y)
            
            self.freq_label.setText(f"Freq: {x*1000:.3f} MHz")
            self.amp_label.setText(f"Amp: {y:.1f} dBm")

    def save_reference(self):
        """Save current trace as reference"""
        if hasattr(self, 'main_curve') and self.main_curve.getData()[1] is not None:
            self.reference_data = list(self.main_curve.getData()[1])
            self.log_message("Reference trace saved")

    def clear_reference(self):
        """Clear reference trace"""
        self.reference_data = []
        self.ref_curve.setData([], [])
        self.log_message("Reference trace cleared")

    def clear_all_traces(self):
        """Clear all traces"""
        self.peak_hold_data = []
        self.max_hold_data = []
        self.reference_data = []
        
        self.peak_hold_curve.setData([], [])
        self.max_hold_curve.setData([], [])
        self.ref_curve.setData([], [])
        
        self.waterfall_widget.clear_waterfall()
        self.marker_manager.clear_markers()
        
        self.log_message("All traces cleared")

    def export_csv(self):
        """Export current spectrum data to CSV"""
        if hasattr(self, 'main_curve') and self.main_curve.getData()[0] is not None:
            from PyQt5.QtWidgets import QFileDialog
            filename, _ = QFileDialog.getSaveFileName(
                self, "Export Spectrum Data", "", "CSV Files (*.csv)"
            )
            if filename:
                try:
                    import csv
                    freq_data = self.main_curve.getData()[0]
                    amp_data = self.main_curve.getData()[1]
                    
                    with open(filename, 'w', newline='') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(['Frequency (GHz)', 'Amplitude (dBm)'])
                        for f, a in zip(freq_data, amp_data):
                            writer.writerow([f, a])
                    
                    self.log_message(f"Data exported to {filename}")
                except Exception as e:
                    self.log_message(f"Export error: {str(e)}")

    def save_screenshot(self):
        """Save screenshot of the plot"""
        from PyQt5.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Screenshot", "", "PNG Files (*.png)"
        )
        if filename:
            try:
                exporter = pg.exporters.ImageExporter(self.plot_widget.plotItem)
                exporter.export(filename)
                self.log_message(f"Screenshot saved to {filename}")
            except Exception as e:
                self.log_message(f"Screenshot error: {str(e)}")

    def toggle_recording(self):
        """Toggle data recording"""
        if hasattr(self, 'recording') and self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        """Start data recording"""
        if self.scan_thread:
            self.scan_thread.start_recording()
            self.recording = True
            self.record_btn.setText("⏹ Stop Recording")
            self.record_status.setText("Status: Recording...")
            self.log_message("Data recording started")

    def stop_recording(self):
        """Stop data recording"""
        if self.scan_thread:
            self.scan_thread.stop_recording()
        self.recording = False
        self.record_btn.setText("🔴 Start Recording")
        self.record_status.setText("Status: Stopped")
        self.log_message("Data recording stopped")

    def update_status(self):
        """Update status bar"""
        if hasattr(self, 'status_bar'):
            if self.device and self.device.is_connected():
                self.status_bar.showMessage("Device connected - Ready")
            else:
                self.status_bar.showMessage("No device connected")

    def create_status_bar(self):
        """Create status bar"""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Initializing...")

    def create_menu_bar(self):
        """Create functional menu bar with actions"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('📁 File')
        
        # Export submenu
        export_action = QAction('📄 Export CSV...', self)
        export_action.setShortcut('Ctrl+E')
        export_action.triggered.connect(self.export_csv)
        file_menu.addAction(export_action)
        
        screenshot_action = QAction('📷 Save Screenshot...', self)
        screenshot_action.setShortcut('Ctrl+S')
        screenshot_action.triggered.connect(self.save_screenshot)
        file_menu.addAction(screenshot_action)
        
        file_menu.addSeparator()
        
        # Settings
        settings_action = QAction('⚙️ Settings...', self)
        settings_action.triggered.connect(self.show_settings)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        # Exit
        exit_action = QAction('🚪 Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Device menu
        device_menu = menubar.addMenu('🔌 Device')
        
        connect_action = QAction('🔗 Connect', self)
        connect_action.setShortcut('Ctrl+C')
        connect_action.triggered.connect(self.toggle_connection)
        device_menu.addAction(connect_action)
        
        refresh_ports_action = QAction('🔄 Refresh Ports', self)
        refresh_ports_action.setShortcut('F5')
        refresh_ports_action.triggered.connect(self.update_ports)
        device_menu.addAction(refresh_ports_action)
        
        device_menu.addSeparator()
        
        # Generator controls
        gen_on_action = QAction('⚡ Generator ON', self)
        gen_on_action.triggered.connect(self.generator_on)
        device_menu.addAction(gen_on_action)
        
        gen_off_action = QAction('⏹️ Generator OFF', self)
        gen_off_action.triggered.connect(self.generator_off)
        device_menu.addAction(gen_off_action)
        
        # View menu
        view_menu = menubar.addMenu('👁️ View')
        
        # Display modes
        spectrum_action = QAction('📊 Spectrum View', self)
        spectrum_action.triggered.connect(lambda: self.display_tabs.setCurrentIndex(0))
        view_menu.addAction(spectrum_action)
        
        waterfall_action = QAction('🌊 Waterfall View', self)
        waterfall_action.triggered.connect(lambda: self.display_tabs.setCurrentIndex(1))
        view_menu.addAction(waterfall_action)
        
        view_menu.addSeparator()
        
        # Clear functions
        clear_traces_action = QAction('🗑️ Clear All Traces', self)
        clear_traces_action.setShortcut('Ctrl+Delete')
        clear_traces_action.triggered.connect(self.clear_all_traces)
        view_menu.addAction(clear_traces_action)
        
        clear_waterfall_action = QAction('🧹 Clear Waterfall', self)
        clear_waterfall_action.triggered.connect(lambda: self.waterfall_widget.clear_waterfall())
        view_menu.addAction(clear_waterfall_action)
        
        # Scan menu
        scan_menu = menubar.addMenu('📡 Scan')
        
        start_scan_action = QAction('▶️ Start Scan', self)
        start_scan_action.setShortcut('Space')
        start_scan_action.triggered.connect(self.toggle_scan)
        scan_menu.addAction(start_scan_action)
        
        single_sweep_action = QAction('🔍 Single Sweep', self)
        single_sweep_action.setShortcut('Ctrl+1')
        single_sweep_action.triggered.connect(self.single_sweep)
        scan_menu.addAction(single_sweep_action)
        
        scan_menu.addSeparator()
        
        # Recording
        record_action = QAction('🔴 Toggle Recording', self)
        record_action.setShortcut('Ctrl+R')
        record_action.triggered.connect(self.toggle_recording)
        scan_menu.addAction(record_action)
        
        # Help menu
        help_menu = menubar.addMenu('❓ Help')
        
        shortcuts_action = QAction('⌨️ Keyboard Shortcuts', self)
        shortcuts_action.triggered.connect(self.show_shortcuts)
        help_menu.addAction(shortcuts_action)
        
        help_menu.addSeparator()
        
        about_action = QAction('ℹ️ About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def log_message(self, message):
        """Log message to display"""
        timestamp = time.strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {message}"
        
        if hasattr(self, 'log_display'):
            cursor = self.log_display.textCursor()
            cursor.movePosition(cursor.End)
            cursor.insertText(formatted_msg + "\n")
            self.log_display.setTextCursor(cursor)
            self.log_display.ensureCursorVisible()
        
        print(formatted_msg)  # Also print to console
    
    def show_settings(self):
        """Show settings dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.setModal(True)
        dialog.resize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # Create settings form
        form_layout = QFormLayout()
        
        # Auto-connect setting
        auto_connect_cb = QCheckBox()
        auto_connect_cb.setChecked(True)
        form_layout.addRow("Auto-connect on startup:", auto_connect_cb)
        
        # Max hold setting
        max_hold_cb = QCheckBox()
        if hasattr(self, 'max_hold_check'):
            max_hold_cb.setChecked(self.max_hold_check.isChecked())
        form_layout.addRow("Enable Max Hold:", max_hold_cb)
        
        # Scan interval
        interval_spin = QSpinBox()
        interval_spin.setRange(100, 5000)
        interval_spin.setValue(500)
        interval_spin.setSuffix(" ms")
        form_layout.addRow("Scan Interval:", interval_spin)
        
        layout.addLayout(form_layout)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec_() == QDialog.Accepted:
            # Apply settings
            if hasattr(self, 'max_hold_check'):
                self.max_hold_check.setChecked(max_hold_cb.isChecked())
            self.log_message("Settings applied")
    
    def show_shortcuts(self):
        """Show keyboard shortcuts dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Keyboard Shortcuts")
        dialog.setModal(True)
        dialog.resize(500, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Create shortcuts table
        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml("""
        <h3>Keyboard Shortcuts</h3>
        <table border="1" cellpadding="5">
        <tr><th>Action</th><th>Shortcut</th></tr>
        <tr><td>Start/Stop Scan</td><td>Space</td></tr>
        <tr><td>Single Sweep</td><td>Ctrl+1</td></tr>
        <tr><td>Toggle Connection</td><td>Ctrl+C</td></tr>
        <tr><td>Refresh Ports</td><td>F5</td></tr>
        <tr><td>Export CSV</td><td>Ctrl+E</td></tr>
        <tr><td>Save Screenshot</td><td>Ctrl+S</td></tr>
        <tr><td>Toggle Recording</td><td>Ctrl+R</td></tr>
        <tr><td>Clear All Traces</td><td>Ctrl+Delete</td></tr>
        <tr><td>Exit</td><td>Ctrl+Q</td></tr>
        </table>
        """)
        layout.addWidget(text)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.exec_()
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About Arinst Spectrum Analyzer", 
                         """
                         <h2>Arinst Spectrum Analyzer GUI</h2>
                         <p>Professional RF spectrum analysis tool</p>
                         <p><b>Features:</b></p>
                         <ul>
                         <li>Real-time spectrum scanning</li>
                         <li>Waterfall visualization</li>
                         <li>Advanced RF measurements</li>
                         <li>Data export and recording</li>
                         <li>Peak detection and markers</li>
                         </ul>
                         <p><b>Version:</b> 1.0</p>
                         <p><b>Created by @Vladmos</b></p>
                         <p><b>Supported Devices:</b> Arinst VR 120-6000</p>
                         """)

def main():
    app = QApplication(sys.argv)
    app.setOrganizationName("TechLab")
    app.setApplicationName("Arinst Spectrum Analyzer")
    
    window = EnhancedSpectrumAnalyzer()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 