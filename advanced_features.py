#!/usr/bin/env python3
"""
Advanced Features Module for Arinst Spectrum Analyzer
Adds professional RF analysis capabilities
"""

import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import csv
import json
from datetime import datetime
from collections import deque

class MarkerManager(QWidget):
    """Professional marker management with delta measurements"""
    
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
        title = QLabel("📍 MARKERS & MEASUREMENTS")
        title.setFont(QFont("Arial", 10, QFont.Bold))
        title.setStyleSheet("color: #00ff88; padding: 5px;")
        layout.addWidget(title)
        
        # Add marker controls
        controls = QHBoxLayout()
        self.add_marker_btn = QPushButton("+ Add")
        self.add_marker_btn.setMaximumWidth(60)
        self.add_marker_btn.clicked.connect(self.add_marker)
        
        self.clear_markers_btn = QPushButton("Clear")
        self.clear_markers_btn.setMaximumWidth(60)
        self.clear_markers_btn.clicked.connect(self.clear_markers)
        
        controls.addWidget(self.add_marker_btn)
        controls.addWidget(self.clear_markers_btn)
        controls.addStretch()
        layout.addLayout(controls)
        
        # Marker list
        self.marker_list = QListWidget()
        self.marker_list.setMaximumHeight(100)
        layout.addWidget(self.marker_list)
        
        # Delta measurements
        delta_label = QLabel("DELTA MEASUREMENTS")
        delta_label.setFont(QFont("Arial", 9, QFont.Bold))
        layout.addWidget(delta_label)
        
        self.delta_display = QTextEdit()
        self.delta_display.setMaximumHeight(80)
        self.delta_display.setReadOnly(True)
        layout.addWidget(self.delta_display)
    
    def add_marker(self):
        """Add marker at peak or specified frequency"""
        if not self.current_data['amplitudes']:
            QMessageBox.warning(self, "No Data", "No spectrum data available for marker placement")
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
            pos=peak_freq/1e9,  # Convert to GHz for display
            pen=pg.mkPen(color=color, width=2),
            label=marker_id,
            labelOpts={'position': 0.95, 'color': color}
        )
        
        self.plot_widget.addItem(marker_line)
        
        # Store marker data
        self.markers[marker_id] = {
            'frequency': peak_freq,
            'amplitude': peak_amp,
            'color': color,
            'line': marker_line
        }
        
        self.marker_lines[marker_id] = marker_line
        self.update_marker_display()
    
    def get_marker_color(self, index):
        """Get unique color for each marker"""
        colors = ['#ff4444', '#44ff44', '#4444ff', '#ffff44', '#ff44ff', '#44ffff']
        return colors[index % len(colors)]
    
    def clear_markers(self):
        """Remove all markers"""
        for marker_line in self.marker_lines.values():
            self.plot_widget.removeItem(marker_line)
        
        self.markers.clear()
        self.marker_lines.clear()
        self.update_marker_display()
    
    def update_data(self, frequencies, amplitudes):
        """Update current spectrum data"""
        self.current_data = {'frequencies': frequencies, 'amplitudes': amplitudes}
        
        # Update marker amplitudes
        for marker_id, marker in self.markers.items():
            if frequencies:
                freq_array = np.array(frequencies)
                closest_idx = np.argmin(np.abs(freq_array - marker['frequency']))
                marker['amplitude'] = amplitudes[closest_idx]
        
        self.update_marker_display()
    
    def update_marker_display(self):
        """Update marker list and delta measurements"""
        self.marker_list.clear()
        
        for marker_id, marker in self.markers.items():
            text = f"{marker_id}: {marker['frequency']/1e6:.3f} MHz → {marker['amplitude']:.2f} dBm"
            self.marker_list.addItem(text)
        
        # Calculate delta measurements
        self.update_delta_measurements()
    
    def update_delta_measurements(self):
        """Calculate and display delta measurements"""
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

class AdvancedMeasurements(QWidget):
    """Advanced RF measurement tools"""
    
    def __init__(self):
        super().__init__()
        self.current_data = {'frequencies': [], 'amplitudes': []}
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("📏 ADVANCED MEASUREMENTS")
        title.setFont(QFont("Arial", 10, QFont.Bold))
        title.setStyleSheet("color: #00ff88; padding: 5px;")
        layout.addWidget(title)
        
        # Measurement buttons
        btn_layout = QGridLayout()
        
        measurements = [
            ("📊 Channel Power", self.measure_channel_power),
            ("📡 Occupied BW", self.measure_obw),
            ("🎯 Peak Search", self.peak_search),
            ("📈 Noise Floor", self.measure_noise_floor),
            ("⚡ ACPR", self.measure_acpr),
            ("📏 3dB BW", self.measure_3db_bw)
        ]
        
        for i, (text, callback) in enumerate(measurements):
            btn = QPushButton(text)
            btn.clicked.connect(callback)
            btn.setMaximumHeight(30)
            btn_layout.addWidget(btn, i // 2, i % 2)
        
        layout.addLayout(btn_layout)
        
        # Results display
        results_label = QLabel("MEASUREMENT RESULTS")
        results_label.setFont(QFont("Arial", 9, QFont.Bold))
        layout.addWidget(results_label)
        
        self.results_display = QTextEdit()
        self.results_display.setMaximumHeight(200)
        layout.addWidget(self.results_display)
        
        # Quick stats
        stats_label = QLabel("QUICK STATISTICS")
        stats_label.setFont(QFont("Arial", 9, QFont.Bold))
        layout.addWidget(stats_label)
        
        self.stats_display = QTextEdit()
        self.stats_display.setMaximumHeight(80)
        self.stats_display.setReadOnly(True)
        layout.addWidget(self.stats_display)
    
    def update_data(self, frequencies, amplitudes):
        """Update measurement data and quick stats"""
        self.current_data = {'frequencies': frequencies, 'amplitudes': amplitudes}
        self.update_quick_stats()
    
    def update_quick_stats(self):
        """Update quick statistics display"""
        if not self.current_data['amplitudes']:
            return
        
        freqs = np.array(self.current_data['frequencies'])
        amps = np.array(self.current_data['amplitudes'])
        
        # Calculate statistics
        peak_idx = np.argmax(amps)
        peak_freq = freqs[peak_idx] / 1e6  # MHz
        peak_amp = amps[peak_idx]
        avg_amp = np.mean(amps)
        min_amp = np.min(amps)
        std_dev = np.std(amps)
        dynamic_range = peak_amp - min_amp
        
        stats_text = f"""Peak: {peak_freq:.3f} MHz @ {peak_amp:.1f} dBm
Average: {avg_amp:.1f} dBm | Min: {min_amp:.1f} dBm
Std Dev: {std_dev:.2f} dB | Range: {dynamic_range:.1f} dB
Points: {len(amps)} | Span: {(freqs[-1]-freqs[0])/1e6:.1f} MHz"""
        
        self.stats_display.setPlainText(stats_text)
    
    def measure_channel_power(self):
        """Measure total power in specified channel"""
        if not self.current_data['frequencies']:
            return
        
        # Get parameters from user
        dialog = ChannelPowerDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            center_freq, bandwidth = dialog.get_values()
            
            freqs = np.array(self.current_data['frequencies'])
            amps = np.array(self.current_data['amplitudes'])
            
            # Define channel boundaries
            start_freq = (center_freq - bandwidth/2) * 1e6
            stop_freq = (center_freq + bandwidth/2) * 1e6
            
            # Find data in channel
            mask = (freqs >= start_freq) & (freqs <= stop_freq)
            if not np.any(mask):
                self.results_display.append("❌ No data in specified channel\n")
                return
            
            # Calculate channel power
            channel_amps = amps[mask]
            channel_freqs = freqs[mask]
            
            # Convert dBm to linear power and integrate
            linear_power = 10**(channel_amps/10)  # mW
            freq_step = np.mean(np.diff(channel_freqs))
            total_power_mw = np.trapz(linear_power, dx=freq_step)
            total_power_dbm = 10 * np.log10(total_power_mw)
            
            # Power spectral density
            psd_dbm_hz = total_power_dbm - 10*np.log10(bandwidth * 1e6)
            
            result = f"""📊 CHANNEL POWER MEASUREMENT
Center: {center_freq:.3f} MHz | BW: {bandwidth:.3f} MHz
Total Power: {total_power_dbm:.2f} dBm
Power Density: {psd_dbm_hz:.2f} dBm/Hz
Peak in Channel: {np.max(channel_amps):.2f} dBm
Time: {datetime.now().strftime('%H:%M:%S')}

"""
            self.results_display.append(result)
    
    def measure_obw(self):
        """Measure 99% occupied bandwidth"""
        if not self.current_data['frequencies']:
            return
        
        freqs = np.array(self.current_data['frequencies'])
        amps = np.array(self.current_data['amplitudes'])
        
        # Convert to linear power
        linear_power = 10**(amps/10)
        
        # Calculate cumulative power
        cumulative_power = np.cumsum(linear_power)
        total_power = cumulative_power[-1]
        
        # Find 0.5% and 99.5% points
        lower_idx = np.argmax(cumulative_power >= 0.005 * total_power)
        upper_idx = np.argmax(cumulative_power >= 0.995 * total_power)
        
        if lower_idx == upper_idx:
            self.results_display.append("❌ Insufficient data for OBW calculation\n")
            return
        
        obw_hz = freqs[upper_idx] - freqs[lower_idx]
        center_freq = (freqs[upper_idx] + freqs[lower_idx]) / 2
        
        result = f"""📡 OCCUPIED BANDWIDTH (99%)
OBW: {obw_hz/1e6:.3f} MHz
Center: {center_freq/1e6:.3f} MHz
Lower Edge: {freqs[lower_idx]/1e6:.3f} MHz
Upper Edge: {freqs[upper_idx]/1e6:.3f} MHz
Time: {datetime.now().strftime('%H:%M:%S')}

"""
        self.results_display.append(result)
    
    def peak_search(self):
        """Find and list strongest peaks"""
        if not self.current_data['frequencies']:
            return
        
        freqs = np.array(self.current_data['frequencies'])
        amps = np.array(self.current_data['amplitudes'])
        
        # Simple peak detection
        peaks = []
        threshold = np.max(amps) - 20  # 20dB below peak
        
        for i in range(1, len(amps)-1):
            if (amps[i] > amps[i-1] and amps[i] > amps[i+1] and 
                amps[i] > threshold):
                peaks.append((freqs[i], amps[i]))
        
        # Sort by amplitude
        peaks.sort(key=lambda x: x[1], reverse=True)
        
        result = f"""🎯 PEAK SEARCH RESULTS (Top 10)
Threshold: {threshold:.1f} dBm
Found {len(peaks)} peaks above threshold

"""
        for i, (freq, amp) in enumerate(peaks[:10]):
            result += f"{i+1:2d}. {freq/1e6:8.3f} MHz → {amp:6.2f} dBm\n"
        
        result += f"\nTime: {datetime.now().strftime('%H:%M:%S')}\n\n"
        self.results_display.append(result)
    
    def measure_noise_floor(self):
        """Estimate noise floor using statistical analysis"""
        if not self.current_data['frequencies']:
            return
        
        amps = np.array(self.current_data['amplitudes'])
        
        # Use histogram to find noise floor
        hist, bins = np.histogram(amps, bins=50)
        noise_bin = np.argmax(hist)  # Most common amplitude level
        noise_floor = (bins[noise_bin] + bins[noise_bin+1]) / 2
        
        # Alternative: use bottom 10%
        sorted_amps = np.sort(amps)
        bottom_10_pct = sorted_amps[:len(sorted_amps)//10]
        noise_floor_alt = np.mean(bottom_10_pct)
        noise_std = np.std(bottom_10_pct)
        
        # Peak to noise ratio
        peak_amp = np.max(amps)
        pnr = peak_amp - noise_floor_alt
        
        result = f"""📈 NOISE FLOOR ANALYSIS
Histogram Method: {noise_floor:.2f} dBm
Statistical Method: {noise_floor_alt:.2f} dBm
Noise Std Dev: {noise_std:.2f} dB
Peak Amplitude: {peak_amp:.2f} dBm
Peak-to-Noise Ratio: {pnr:.1f} dB
Dynamic Range: {peak_amp - noise_floor_alt:.1f} dB
Time: {datetime.now().strftime('%H:%M:%S')}

"""
        self.results_display.append(result)
    
    def measure_acpr(self):
        """Measure Adjacent Channel Power Ratio"""
        # Placeholder for ACPR measurement
        self.results_display.append("⚡ ACPR measurement coming soon...\n")
    
    def measure_3db_bw(self):
        """Measure 3dB bandwidth around peak"""
        if not self.current_data['frequencies']:
            return
        
        freqs = np.array(self.current_data['frequencies'])
        amps = np.array(self.current_data['amplitudes'])
        
        # Find peak
        peak_idx = np.argmax(amps)
        peak_amp = amps[peak_idx]
        threshold = peak_amp - 3  # 3dB down
        
        # Find 3dB points
        left_idx = peak_idx
        while left_idx > 0 and amps[left_idx] > threshold:
            left_idx -= 1
        
        right_idx = peak_idx
        while right_idx < len(amps)-1 and amps[right_idx] > threshold:
            right_idx += 1
        
        if left_idx == 0 or right_idx == len(amps)-1:
            self.results_display.append("❌ 3dB points not found in scan range\n")
            return
        
        bw_3db = freqs[right_idx] - freqs[left_idx]
        center_freq = freqs[peak_idx]
        
        result = f"""📏 3dB BANDWIDTH MEASUREMENT
Center Frequency: {center_freq/1e6:.3f} MHz
Peak Amplitude: {peak_amp:.2f} dBm
3dB Bandwidth: {bw_3db/1e6:.3f} MHz
Lower 3dB Point: {freqs[left_idx]/1e6:.3f} MHz
Upper 3dB Point: {freqs[right_idx]/1e6:.3f} MHz
Q Factor: {center_freq/bw_3db:.1f}
Time: {datetime.now().strftime('%H:%M:%S')}

"""
        self.results_display.append(result)

class ChannelPowerDialog(QDialog):
    """Dialog for channel power measurement parameters"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Channel Power Measurement")
        self.setModal(True)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QFormLayout(self)
        
        self.center_freq = QDoubleSpinBox()
        self.center_freq.setRange(1, 6000)
        self.center_freq.setValue(2450)
        self.center_freq.setSuffix(" MHz")
        self.center_freq.setDecimals(3)
        layout.addRow("Center Frequency:", self.center_freq)
        
        self.bandwidth = QDoubleSpinBox()
        self.bandwidth.setRange(0.001, 1000)
        self.bandwidth.setValue(20)
        self.bandwidth.setSuffix(" MHz")
        self.bandwidth.setDecimals(3)
        layout.addRow("Bandwidth:", self.bandwidth)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
    
    def get_values(self):
        return self.center_freq.value(), self.bandwidth.value()

class DataExporter(QWidget):
    """Data export and recording functionality"""
    
    def __init__(self):
        super().__init__()
        self.recorded_data = []
        self.recording = False
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("💾 DATA EXPORT & RECORDING")
        title.setFont(QFont("Arial", 10, QFont.Bold))
        title.setStyleSheet("color: #00ff88; padding: 5px;")
        layout.addWidget(title)
        
        # Export buttons
        self.export_csv_btn = QPushButton("📄 Export Current Trace (CSV)")
        self.export_csv_btn.clicked.connect(self.export_current_csv)
        layout.addWidget(self.export_csv_btn)
        
        self.export_all_btn = QPushButton("📊 Export All Data (JSON)")
        self.export_all_btn.clicked.connect(self.export_all_data)
        layout.addWidget(self.export_all_btn)
        
        # Screenshot
        self.screenshot_btn = QPushButton("📷 Save Screenshot")
        self.screenshot_btn.clicked.connect(self.save_screenshot)
        layout.addWidget(self.screenshot_btn)
        
        # Recording controls
        record_group = QGroupBox("Continuous Recording")
        record_layout = QVBoxLayout()
        
        self.record_btn = QPushButton("🔴 Start Recording")
        self.record_btn.clicked.connect(self.toggle_recording)
        record_layout.addWidget(self.record_btn)
        
        self.record_status = QLabel("Status: Stopped")
        record_layout.addWidget(self.record_status)
        
        self.record_count = QLabel("Traces: 0")
        record_layout.addWidget(self.record_count)
        
        record_group.setLayout(record_layout)
        layout.addWidget(record_group)
        
        layout.addStretch()
    
    def export_current_csv(self):
        """Export current spectrum trace to CSV"""
        # This would be called with current data from main GUI
        pass
    
    def export_all_data(self):
        """Export all collected data to JSON"""
        pass
    
    def save_screenshot(self):
        """Save plot screenshot"""
        pass
    
    def toggle_recording(self):
        """Toggle data recording"""
        self.recording = not self.recording
        
        if self.recording:
            self.record_btn.setText("⏹ Stop Recording")
            self.record_btn.setStyleSheet("background-color: #ff4444;")
            self.record_status.setText("Status: Recording...")
            self.recorded_data = []
        else:
            self.record_btn.setText("🔴 Start Recording")
            self.record_btn.setStyleSheet("")
            self.record_status.setText("Status: Stopped")
    
    def add_data_point(self, frequencies, amplitudes, timestamp):
        """Add data point to recording"""
        if self.recording:
            self.recorded_data.append({
                'timestamp': timestamp,
                'frequencies': frequencies,
                'amplitudes': amplitudes
            })
            self.record_count.setText(f"Traces: {len(self.recorded_data)}")

# Helper function to integrate advanced features into existing GUI
def add_advanced_features_to_gui(main_gui):
    """Add advanced features to existing spectrum analyzer GUI"""
    
    # Create new right panel with advanced features
    advanced_panel = QWidget()
    advanced_panel.setFixedWidth(350)
    advanced_layout = QVBoxLayout(advanced_panel)
    
    # Create tabbed interface for advanced features
    advanced_tabs = QTabWidget()
    
    # Add marker manager
    marker_manager = MarkerManager(main_gui.plot_widget)
    advanced_tabs.addTab(marker_manager, "📍 Markers")
    
    # Add advanced measurements
    measurements = AdvancedMeasurements()
    advanced_tabs.addTab(measurements, "📏 Measure")
    
    # Add data export
    exporter = DataExporter()
    advanced_tabs.addTab(exporter, "💾 Export")
    
    advanced_layout.addWidget(advanced_tabs)
    
    # Function to update all advanced features with new data
    def update_advanced_features(frequencies, amplitudes):
        marker_manager.update_data(frequencies, amplitudes)
        measurements.update_data(frequencies, amplitudes)
        # Could add timestamp for exporter
    
    return advanced_panel, update_advanced_features 