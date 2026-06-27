"""
ChronoPlot

A PyQt6-based graphical utility for loading time-series data from CSV files,
visualizing the data, and computing/plotting the Modified Allan Deviation (MDEV).
"""

import sys
import os
import pandas as pd
import numpy as np
import allantools as at
from multiprocessing import Pool
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QComboBox, QLabel, QHBoxLayout, QListWidget, QListWidgetItem,
    QTabWidget
)
from PyQt6.QtCore import Qt
import pyqtgraph as pg
import pyqtgraph.exporters

def load_csv(file_path):
    """
    Worker function to load a CSV file into a pandas DataFrame.
    Designed to be used with multiprocessing.Pool for faster batch loading.

    Args:
        file_path (str): The absolute path to the CSV file.

    Returns:
        tuple: (file_path, DataFrame) or (file_path, None) if an error occurs.
    """
    try:
        df = pd.read_csv(file_path)
        return file_path, df
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return file_path, None

class CSVPlotter(QMainWindow):
    """
    Main application window for the CSV Plotter and Allan Deviation analyzer.
    Handles UI layout, user interactions, and plot rendering.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CSV Plotter with Allan Deviation")
        self.resize(1000, 750)

        # State management
        self.dataframes = {}    # Maps file paths to their respective DataFrames
        self.plot_configs = []  # Stores active plot configurations: list of (file, x_col, y_col)

        # Plot styling
        self.colors = ['r', 'g', 'b', 'c', 'm', 'y', 'k', 'orange', 'purple', 'teal']

        self.init_ui()

    def init_ui(self):
        """Initializes the graphical user interface components."""
        central_widget = QWidget()
        main_layout = QVBoxLayout()

        # Initialize tabbed interface
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # === Tab 1: Plot Configuration ===
        self.plot_tab = QWidget()
        plot_layout = QVBoxLayout()

        # File Selection Controls
        self.load_button = QPushButton("Load CSV Files")
        self.load_button.clicked.connect(self.load_files)
        plot_layout.addWidget(self.load_button)

        dropdown_layout = QHBoxLayout()

        # File dropdown
        self.file_selector = QComboBox()
        self.file_selector.currentTextChanged.connect(self.update_column_selectors)
        dropdown_layout.addWidget(QLabel("File:"))
        dropdown_layout.addWidget(self.file_selector)

        # X-Axis column dropdown
        self.x_selector = QComboBox()
        dropdown_layout.addWidget(QLabel("X Column:"))
        dropdown_layout.addWidget(self.x_selector)

        # Y-Axis column dropdown
        self.y_selector = QComboBox()
        dropdown_layout.addWidget(QLabel("Y Column:"))
        dropdown_layout.addWidget(self.y_selector)

        plot_layout.addLayout(dropdown_layout)

        # Plot Management Controls
        self.add_plot_button = QPushButton("Add Plot")
        self.add_plot_button.clicked.connect(self.add_plot_config)
        plot_layout.addWidget(self.add_plot_button)

        self.plot_list = QListWidget()
        plot_layout.addWidget(self.plot_list)

        self.plot_button = QPushButton("Plot All")
        self.plot_button.clicked.connect(self.plot_all)
        plot_layout.addWidget(self.plot_button)

        # Styling and Export Controls
        style_layout = QHBoxLayout()

        self.color_selector = QComboBox()
        self.color_selector.addItems(self.colors)
        style_layout.addWidget(QLabel("Color:"))
        style_layout.addWidget(self.color_selector)

        self.symbol_selector = QComboBox()
        self.symbol_selector.addItems(['o', 'x', 't', 's', 'd', '+', 'None'])
        style_layout.addWidget(QLabel("Symbol:"))
        style_layout.addWidget(self.symbol_selector)

        self.scale_selector = QComboBox()
        self.scale_selector.addItems(['linear', 'log'])
        style_layout.addWidget(QLabel("Axis Scale:"))
        style_layout.addWidget(self.scale_selector)

        self.export_button = QPushButton("Export Plot as PNG")
        self.export_button.clicked.connect(self.export_plot)
        style_layout.addWidget(self.export_button)

        plot_layout.addLayout(style_layout)

        self.clear_button = QPushButton("Clear All Plots")
        self.clear_button.clicked.connect(self.clear_all_plots)
        plot_layout.addWidget(self.clear_button)

        # Primary Data Plot Widget
        self.plot_widget = pg.PlotWidget()
        plot_layout.addWidget(self.plot_widget)

        self.plot_tab.setLayout(plot_layout)
        self.tabs.addTab(self.plot_tab, "Plots")

        # === Tab 2: Allan Deviation ===
        self.adev_tab = QWidget()
        adev_layout = QVBoxLayout()

        # Allan Deviation Plot Widget
        self.adev_plot_widget = pg.PlotWidget(title="Modified Allan Deviation (MDEV)")
        adev_layout.addWidget(self.adev_plot_widget)

        self.adev_tab.setLayout(adev_layout)
        self.tabs.addTab(self.adev_tab, "Allan Deviation")

        # Finalize central widget setup
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def load_files(self):
        """Opens a file dialog, allowing the user to select and load multiple CSV files concurrently."""
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select CSV Files", "", "CSV Files (*.csv)")
        if not file_paths:
            return

        # Utilize multiprocessing to speed up loading of large/multiple CSVs
        with Pool() as pool:
            results = pool.map(load_csv, file_paths)

        for file_path, df in results:
            if df is not None:
                self.dataframes[file_path] = df

        self.file_selector.clear()
        self.file_selector.addItems(self.dataframes.keys())
        self.update_column_selectors()

    def update_column_selectors(self):
        """Updates the X and Y column dropdowns based on the currently selected CSV file."""
        file = self.file_selector.currentText()
        if not file:
            return

        df = self.dataframes.get(file)
        if df is not None:
            columns = df.columns.tolist()
            self.x_selector.clear()
            self.y_selector.clear()
            self.x_selector.addItems(columns)
            self.y_selector.addItems(columns)

    def add_plot_config(self):
        """Adds a configured plot (File, X-col, Y-col) to the tracking list and UI display."""
        file = self.file_selector.currentText()
        x_col = self.x_selector.currentText()
        y_col = self.y_selector.currentText()

        if not file or not x_col or not y_col:
            return

        config = (file, x_col, y_col)
        self.plot_configs.append(config)
        item_text = f"{os.path.basename(file)}: X={x_col}, Y={y_col}"
        self.plot_list.addItem(QListWidgetItem(item_text))

    def plot_all(self):
        """Renders all configured plots on the main graph and calculates/plots their Allan Deviation."""
        # Reset plot canvases
        self.plot_widget.clear()
        self.adev_plot_widget.clear()

        self.plot_widget.addLegend()
        self.adev_plot_widget.addLegend()

        # Configure scaling
        self.plot_widget.setLogMode(False, False)
        self.adev_plot_widget.setLogMode(True, True) # Allan Dev is traditionally log-log

        scale = self.scale_selector.currentText()
        if scale == 'log':
            self.plot_widget.setLogMode(True, True)

        for i, (file, x_col, y_col) in enumerate(self.plot_configs):
            df = self.dataframes.get(file)
            if df is not None:
                x = df[x_col].values
                y = df[y_col].values

                # Cycle through predefined colors to distinguish datasets
                color = self.colors[i % len(self.colors)]
                symbol = self.symbol_selector.currentText()
                if symbol == 'None':
                    symbol = None

                label = f"{os.path.basename(file)}: {y_col}"

                # Plot original time-series data
                self.plot_widget.plot(
                    x, y,
                    pen=pg.mkPen(color=color, width=2),
                    symbol=symbol,
                    symbolBrush=color,
                    name=label
                )

                # Compute and plot Modified Allan Deviation
                taus, mdev = self.compute_adev(y)
                self.adev_plot_widget.plot(
                    taus, mdev,
                    pen=pg.mkPen(color=color, width=2),
                    symbol='x',
                    symbolBrush=color,
                    name=label
                )

    def compute_adev(self, y):
        """
        Computes the Modified Allan Deviation (MDEV) of a dataset.

        Args:
            y (array-like): The sequence of data points.

        Returns:
            tuple: (taus, mdev) Arrays representing the observation intervals and deviation values.
        """
        # Calculate MDEV assuming a default sample rate of 1 Hz for the timestamps
        taus, mdev, mdev_err, n = at.mdev(y, rate=1)
        return taus, mdev

    def clear_all_plots(self):
        """Clears all plots from the UI and resets the internal configuration list."""
        self.plot_widget.clear()
        self.adev_plot_widget.clear()
        self.plot_configs.clear()
        self.plot_list.clear()

    def export_plot(self):
        """Exports the current view of the main plot widget to a PNG image file."""
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Plot", "", "PNG Files (*.png)")
        if file_path:
            exporter = pg.exporters.ImageExporter(self.plot_widget.plotItem)
            exporter.export(file_path)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CSVPlotter()
    window.show()
    sys.exit(app.exec())
