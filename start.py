#!/usr/bin/env python3
"""
Simple launcher for Arinst Spectrum Analyzer GUI
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import numpy as np
    import pyqtgraph as pg
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from arinst_device import ArinstDevice
    print("All dependencies loaded successfully!")
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Please run: pip install -r requirements.txt")
    sys.exit(1)

# Import the main GUI
try:
    from run import EnhancedSpectrumAnalyzer, main
    print("GUI module loaded successfully!")
    
    if __name__ == "__main__":
        main()
        
except Exception as e:
    print(f"Error starting application: {e}")
    sys.exit(1) 