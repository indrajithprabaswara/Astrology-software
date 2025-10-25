"""PyQt5 user interface for the astrology application."""

from __future__ import annotations

from datetime import datetime
from typing import Dict

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from ai import AIPredictor
from dasha import compute_vimshottari, periods_to_dataframe
from ephemeris import EphemerisCalculator, positions_dataframe
from panchang import PanchangCalculator
from storage import KundaliRecord, load_kundali, save_kundali
from strength import StrengthCalculator
from varga import VargaCalculator
from yoga import YogaDetector


class ChartCanvas(FigureCanvas):
    def __init__(self, parent: QWidget | None = None) -> None:
        self.figure, self.ax = plt.subplots(figsize=(5, 5))
        super().__init__(self.figure)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.updateGeometry()

    def draw_chart(self, houses: Dict[str, float], positions: Dict[str, float]) -> None:
        self.ax.clear()
        self.ax.set_title("North Indian Chart")
        self.ax.axis("off")
        square = plt.Rectangle((0.1, 0.1), 0.8, 0.8, fill=False)
        self.ax.add_patch(square)
        for i in range(4):
            self.ax.plot([0.1, 0.9], [0.1 + 0.2 * i, 0.1 + 0.2 * i], color="black")
            self.ax.plot([0.1 + 0.2 * i, 0.1 + 0.2 * i], [0.1, 0.9], color="black")
        for planet, lon in positions.items():
            house = int(((lon - houses.get("House 1", 0.0) + 360) % 360) // 30) + 1
            self.ax.text(0.2 * ((house - 1) % 4) + 0.2, 0.8 - 0.2 * ((house - 1) // 4), planet[:2], ha="center", va="center")
        self.draw()


class DataTab(QWidget):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.title = title
        self.layout = QVBoxLayout(self)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.layout.addWidget(self.text)

    def update_data(self, df: pd.DataFrame) -> None:
        self.text.setPlainText(df.to_string(index=False))


class YogaTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.layout.addWidget(self.text)

    def update_yogas(self, df: pd.DataFrame) -> None:
        if df.empty:
            self.text.setPlainText("No yogas detected.")
        else:
            self.text.setPlainText(df.to_string(index=False))


class AITab(QWidget):
    def __init__(self, predictor: AIPredictor) -> None:
        super().__init__()
        self.predictor = predictor
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.activity = QComboBox()
        self.activity.addItems(sorted(predictor.activity_weights.keys()))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(datetime.now().date())
        self.start_time = QTimeEdit()
        self.start_time.setTime(datetime.now().time())
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(datetime.now().date())
        self.end_time = QTimeEdit()
        self.end_time.setTime(datetime.now().time())
        form.addRow("Activity", self.activity)
        form.addRow("Start date", self.start_date)
        form.addRow("Start time", self.start_time)
        form.addRow("End date", self.end_date)
        form.addRow("End time", self.end_time)
        layout.addLayout(form)
        self.run_button = QPushButton("Predict")
        self.run_button.clicked.connect(self._run_prediction)
        layout.addWidget(self.run_button)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)
        self.latitude = 0.0
        self.longitude = 0.0

    def set_location(self, latitude: float, longitude: float) -> None:
        self.latitude = latitude
        self.longitude = longitude

    def _run_prediction(self) -> None:
        start_dt = datetime.combine(self.start_date.date().toPyDate(), self.start_time.time().toPyTime())
        end_dt = datetime.combine(self.end_date.date().toPyDate(), self.end_time.time().toPyTime())
        if end_dt <= start_dt:
            QMessageBox.warning(self, "Prediction", "End time must be after start time")
            return
        df = self.predictor.predict(
            self.activity.currentText(),
            start_dt,
            end_dt,
            self.latitude,
            self.longitude,
        )
        self.text.setPlainText(df.to_string(index=False))


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        layout = QFormLayout(self)
        self.ayanamsa = QComboBox()
        self.ayanamsa.addItems(["lahiri", "raman", "krishnamurti"])
        self.house_system = QComboBox()
        self.house_system.addItems(["P", "K", "B"])
        self.chart_style = QComboBox()
        self.chart_style.addItems(["North", "South"])
        layout.addRow("Ayanamsa", self.ayanamsa)
        layout.addRow("House system", self.house_system)
        layout.addRow("Chart style", self.chart_style)
        self.buttons = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        self.buttons.addWidget(ok_button)
        self.buttons.addWidget(cancel_button)
        layout.addRow(self.buttons)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Astrology Suite")
        self.ephemeris = EphemerisCalculator()
        self.varga_calculator = VargaCalculator()
        self.yoga_detector = YogaDetector()
        self.panchang = PanchangCalculator(self.ephemeris)
        self.ai_predictor = AIPredictor(self.ephemeris)
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        self.setCentralWidget(central)

        form_group = QGroupBox("Birth Details")
        form_layout = QGridLayout()
        self.name_edit = QLineEdit()
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.time_edit = QTimeEdit()
        self.lat_spin = QDoubleSpinBox()
        self.lat_spin.setRange(-90.0, 90.0)
        self.lon_spin = QDoubleSpinBox()
        self.lon_spin.setRange(-180.0, 180.0)
        form_layout.addWidget(QLabel("Name"), 0, 0)
        form_layout.addWidget(self.name_edit, 0, 1)
        form_layout.addWidget(QLabel("Date"), 1, 0)
        form_layout.addWidget(self.date_edit, 1, 1)
        form_layout.addWidget(QLabel("Time"), 2, 0)
        form_layout.addWidget(self.time_edit, 2, 1)
        form_layout.addWidget(QLabel("Latitude"), 3, 0)
        form_layout.addWidget(self.lat_spin, 3, 1)
        form_layout.addWidget(QLabel("Longitude"), 4, 0)
        form_layout.addWidget(self.lon_spin, 4, 1)
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        button_layout = QHBoxLayout()
        compute_button = QPushButton("Compute")
        compute_button.clicked.connect(self.compute_kundali)
        settings_button = QPushButton("Settings")
        settings_button.clicked.connect(self.open_settings)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_kundali)
        load_button = QPushButton("Load")
        load_button.clicked.connect(self.load_kundali)
        button_layout.addWidget(compute_button)
        button_layout.addWidget(settings_button)
        button_layout.addWidget(save_button)
        button_layout.addWidget(load_button)
        layout.addLayout(button_layout)

        self.tabs = QTabWidget()
        self.chart_tab = QWidget()
        chart_layout = QVBoxLayout(self.chart_tab)
        self.chart_canvas = ChartCanvas()
        chart_layout.addWidget(self.chart_canvas)
        self.tabs.addTab(self.chart_tab, "Chart")
        self.graha_tab = DataTab("Graha")
        self.tabs.addTab(self.graha_tab, "Graha")
        self.upagraha_tab = DataTab("Upagraha")
        self.tabs.addTab(self.upagraha_tab, "Upagraha")
        self.yoga_tab = YogaTab()
        self.tabs.addTab(self.yoga_tab, "Yoga")
        self.panchang_tab = DataTab("Panchangam")
        self.tabs.addTab(self.panchang_tab, "Panchangam")
        self.dasha_tab = DataTab("Vimshottari Dasha")
        self.tabs.addTab(self.dasha_tab, "Vimshottari Dasha")
        self.ashtaka_tab = DataTab("Ashtaka Varga")
        self.tabs.addTab(self.ashtaka_tab, "Ashtaka Varga")
        self.shadbala_tab = DataTab("Shadbala")
        self.tabs.addTab(self.shadbala_tab, "Shadbala")
        self.bhavabala_tab = DataTab("Bhavabala")
        self.tabs.addTab(self.bhavabala_tab, "Bhavabala")
        self.ai_tab = AITab(self.ai_predictor)
        self.tabs.addTab(self.ai_tab, "AI Prediction")
        layout.addWidget(self.tabs)

    # ------------------------------------------------------------------
    def compute_kundali(self) -> None:
        date = self.date_edit.date().toPyDate()
        time = self.time_edit.time().toPyTime()
        dt = datetime.combine(date, time)
        latitude = self.lat_spin.value()
        longitude = self.lon_spin.value()
        positions = self.ephemeris.planetary_positions(dt)
        houses = self.ephemeris.house_cusps(dt, latitude, longitude)
        vargas = self.varga_calculator.compute({planet: pos.longitude for planet, pos in positions.items()})
        strength = StrengthCalculator(positions, houses, vargas)
        shadbala_df = strength.shadbala()
        bhavabala_df = strength.bhavabala()
        graha_df = positions_dataframe(positions)
        upagraha_df = graha_df[graha_df["Planet"].isin(["Gulika", "Mandi"])]
        chart_positions = {planet: pos.longitude for planet, pos in positions.items()}
        self.chart_canvas.draw_chart(houses, chart_positions)
        self.graha_tab.update_data(graha_df)
        self.upagraha_tab.update_data(upagraha_df)
        yoga_df = self.yoga_detector.detect(houses, chart_positions)
        self.yoga_tab.update_yogas(yoga_df)
        panchang_details = self.panchang.compute(dt, latitude, longitude)
        self.panchang_tab.update_data(self.panchang.to_dataframe(panchang_details))
        moon_lon = positions["Moon"].longitude
        dashas = compute_vimshottari(moon_lon, dt)
        self.dasha_tab.update_data(periods_to_dataframe(dashas))
        self.shadbala_tab.update_data(shadbala_df)
        self.bhavabala_tab.update_data(bhavabala_df)
        self.ashtaka_tab.update_data(pd.DataFrame())
        self.ai_tab.set_location(latitude, longitude)
        self.current_record = KundaliRecord(
            metadata={
                "name": self.name_edit.text(),
                "datetime": dt.isoformat(),
                "latitude": latitude,
                "longitude": longitude,
            },
            planetary_positions=graha_df,
            divisional_positions={name: pd.DataFrame.from_dict(data, orient="index", columns=["Sign"]) for name, data in vargas.items()},
            strengths={"shadbala": shadbala_df.to_dict(orient="records"), "bhavabala": bhavabala_df.to_dict(orient="records")},
        )

    def open_settings(self) -> None:
        dialog = SettingsDialog(self)
        if dialog.exec_():
            self.ephemeris.set_ayanamsa(dialog.ayanamsa.currentText())

    def save_kundali(self) -> None:
        if not hasattr(self, "current_record"):
            QMessageBox.information(self, "Save", "No data to save")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Kundali", filter="JSON Files (*.json)")
        if path:
            save_kundali(self.current_record, path)

    def load_kundali(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Kundali", filter="JSON Files (*.json)")
        if not path:
            return
        record = load_kundali(path)
        self.name_edit.setText(record.metadata.get("name", ""))
        dt = datetime.fromisoformat(record.metadata.get("datetime"))
        self.date_edit.setDate(dt.date())
        self.time_edit.setTime(dt.time())
        self.lat_spin.setValue(record.metadata.get("latitude", 0.0))
        self.lon_spin.setValue(record.metadata.get("longitude", 0.0))
        self.graha_tab.update_data(record.planetary_positions)
        self.shadbala_tab.update_data(pd.DataFrame(record.strengths.get("shadbala", [])))
        self.bhavabala_tab.update_data(pd.DataFrame(record.strengths.get("bhavabala", [])))


def run_app() -> None:
    import sys

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
