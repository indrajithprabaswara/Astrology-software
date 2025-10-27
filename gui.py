"""PyQt5 user interface for the astrology application."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional, Sequence

import pandas as pd
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
    QStyle,
    QTableView,
    QTabWidget,
    QTextEdit,
    QTimeEdit,
    QToolTip,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtCore import QAbstractTableModel, QModelIndex, QPoint, QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt5.QtChart import QBarCategoryAxis, QBarSet, QChart, QChartView, QPercentBarSeries
from PyQt5.QtCore import QSortFilterProxyModel, QVariant
from PyQt5.QtWidgets import QHeaderView

from ai import AIPredictor
from dasha import compute_vimshottari, periods_to_dataframe
from ephemeris import EphemerisCalculator, PlanetPosition, positions_dataframe
from panchang import PanchangCalculator
from storage import KundaliRecord, load_kundali, save_kundali
from strength import StrengthCalculator
from varga import VargaCalculator, ZODIAC_SIGNS
from yoga import YogaDetector
from ashtakavarga import AshtakavargaCalculator


PLANET_GLYPHS = {
    "Sun": "\u2609",
    "Moon": "\u263D",
    "Mars": "\u2642",
    "Mercury": "\u263F",
    "Jupiter": "\u2643",
    "Venus": "\u2640",
    "Saturn": "\u2644",
    "Rahu": "\u260A",
    "Ketu": "\u260B",
    "Uranus": "\u26E2",
    "Neptune": "\u2646",
    "Pluto": "\u2647",
}

NAKSHATRA_DATA: Sequence[tuple[str, str]] = (
    ("Ashwini", "Ketu"),
    ("Bharani", "Venus"),
    ("Krittika", "Sun"),
    ("Rohini", "Moon"),
    ("Mrigashira", "Mars"),
    ("Ardra", "Rahu"),
    ("Punarvasu", "Jupiter"),
    ("Pushya", "Saturn"),
    ("Ashlesha", "Mercury"),
    ("Magha", "Ketu"),
    ("Purva Phalguni", "Venus"),
    ("Uttara Phalguni", "Sun"),
    ("Hasta", "Moon"),
    ("Chitra", "Mars"),
    ("Swati", "Rahu"),
    ("Vishakha", "Jupiter"),
    ("Anuradha", "Saturn"),
    ("Jyeshtha", "Mercury"),
    ("Mula", "Ketu"),
    ("Purva Ashadha", "Venus"),
    ("Uttara Ashadha", "Sun"),
    ("Shravana", "Moon"),
    ("Dhanishta", "Mars"),
    ("Shatabhisha", "Rahu"),
    ("Purva Bhadrapada", "Jupiter"),
    ("Uttara Bhadrapada", "Saturn"),
    ("Revati", "Mercury"),
)

SIGN_LORDS = {
    "Aries": "Mars",
    "Taurus": "Venus",
    "Gemini": "Mercury",
    "Cancer": "Moon",
    "Leo": "Sun",
    "Virgo": "Mercury",
    "Libra": "Venus",
    "Scorpio": "Mars",
    "Sagittarius": "Jupiter",
    "Capricorn": "Saturn",
    "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}

EXALTATION_SIGNS = {
    "Sun": ("Aries", 10.0),
    "Moon": ("Taurus", 3.0),
    "Mars": ("Capricorn", 28.0),
    "Mercury": ("Virgo", 15.0),
    "Jupiter": ("Cancer", 5.0),
    "Venus": ("Pisces", 27.0),
    "Saturn": ("Libra", 20.0),
}

DEBILITATION_SIGNS = {
    "Sun": ("Libra", 10.0),
    "Moon": ("Scorpio", 3.0),
    "Mars": ("Cancer", 28.0),
    "Mercury": ("Pisces", 15.0),
    "Jupiter": ("Capricorn", 5.0),
    "Venus": ("Virgo", 27.0),
    "Saturn": ("Aries", 20.0),
}

OWN_SIGNS = {
    "Sun": {"Leo"},
    "Moon": {"Cancer"},
    "Mars": {"Aries", "Scorpio"},
    "Mercury": {"Gemini", "Virgo"},
    "Jupiter": {"Sagittarius", "Pisces"},
    "Venus": {"Taurus", "Libra"},
    "Saturn": {"Capricorn", "Aquarius"},
}


def format_dms(degrees: float) -> str:
    deg = int(degrees)
    minutes_full = (degrees - deg) * 60
    minutes = int(minutes_full)
    seconds = int(round((minutes_full - minutes) * 60))
    if seconds == 60:
        seconds = 0
        minutes += 1
    if minutes == 60:
        minutes = 0
        deg += 1
    return f"{deg:02d}° {minutes:02d}' {seconds:02d}\""


def nakshatra_details(longitude: float) -> tuple[str, int, str]:
    segment = 360.0 / len(NAKSHATRA_DATA)
    index = int(longitude // segment) % len(NAKSHATRA_DATA)
    within = (longitude % segment) / segment
    pada = int(within * 4) + 1
    name, lord = NAKSHATRA_DATA[index]
    return name, pada, lord


def planetary_dignity(planet: str, sign: str, degree_in_sign: float) -> str:
    exalt = EXALTATION_SIGNS.get(planet)
    if exalt and exalt[0] == sign:
        return "Exalted"
    deb = DEBILITATION_SIGNS.get(planet)
    if deb and deb[0] == sign:
        return "Debilitated"
    if planet in OWN_SIGNS and sign in OWN_SIGNS[planet]:
        return "Own Sign"
    lord = SIGN_LORDS.get(sign)
    if lord:
        relation = "Friendly" if lord in OWN_SIGNS.get(planet, set()) else "Neutral"
        return f"{relation} Sign"
    return "Neutral"


class DataFrameModel(QAbstractTableModel):
    """Model adapter that exposes a pandas DataFrame to Qt views."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._frame = pd.DataFrame()

    def set_frame(self, frame: pd.DataFrame) -> None:
        self.beginResetModel()
        self._frame = frame.copy()
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(self._frame.index)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # type: ignore[override]
        if parent.isValid():
            return 0
        return len(self._frame.columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid():
            return QVariant()
        value = self._frame.iat[index.row(), index.column()]
        if role in (Qt.DisplayRole, Qt.EditRole):
            if pd.isna(value):
                return ""
            if isinstance(value, float):
                return f"{value:.4f}"
            return str(value)
        return QVariant()

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):  # type: ignore[override]
        if role != Qt.DisplayRole:
            return QVariant()
        if orientation == Qt.Horizontal:
            try:
                return str(self._frame.columns[section])
            except IndexError:
                return QVariant()
        try:
            return str(self._frame.index[section])
        except IndexError:
            return QVariant()

    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder) -> None:  # type: ignore[override]
        if not 0 <= column < len(self._frame.columns):
            return
        ascending = order == Qt.AscendingOrder
        self.layoutAboutToBeChanged.emit()
        self._frame = self._frame.sort_values(self._frame.columns[column], ascending=ascending)
        self.layoutChanged.emit()


class ChartWidget(QWidget):
    """Custom widget that renders charts using QPainter."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(500, 500)
        self.chart_style = "North"
        self.positions: Dict[str, float] = {}
        self.houses: Dict[str, float] = {}
        self.planet_details: Dict[str, Dict[str, str]] = {}
        self.house_details: Dict[str, Dict[str, str]] = {}
        self._planet_rects: Dict[str, QRectF] = {}
        self._house_rects: Dict[str, QRectF] = {}
        self.setMouseTracking(True)

    def set_chart_data(
        self,
        positions: Dict[str, float],
        houses: Dict[str, float],
        planet_details: Optional[Dict[str, Dict[str, str]]] = None,
        house_details: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> None:
        self.positions = positions
        self.houses = houses
        self.planet_details = planet_details or {}
        self.house_details = house_details or {}
        self.update()

    def set_chart_style(self, style: str) -> None:
        self.chart_style = style
        self.update()

    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor(248, 249, 255))
        gradient.setColorAt(1.0, QColor(224, 228, 240))
        painter.fillRect(self.rect(), gradient)

        width = self.width()
        height = self.height()
        if self.chart_style == "South":
            self._draw_south_indian_chart(painter, width, height)
        else:
            self._draw_north_indian_chart(painter, width, height)

    # ------------------------------------------------------------------
    def _draw_north_indian_chart(self, painter: QPainter, width: int, height: int) -> None:
        border_pen = QPen(Qt.black, 3)
        inner_pen = QPen(Qt.black, 1)

        padding = 20
        box_size = min(width, height) - 2 * padding
        top_left_x = (width - box_size) / 2
        top_left_y = (height - box_size) / 2

        outer_rect = QRectF(top_left_x, top_left_y, box_size, box_size)
        painter.setPen(border_pen)
        painter.drawRect(outer_rect)

        painter.setPen(inner_pen)
        p1 = outer_rect.topLeft()
        p2 = outer_rect.topRight()
        p3 = outer_rect.bottomLeft()
        p4 = outer_rect.bottomRight()
        center = outer_rect.center()

        painter.drawLine(p1, p4)
        painter.drawLine(p2, p3)

        mid_top = QPointF(center.x(), outer_rect.top())
        mid_bottom = QPointF(center.x(), outer_rect.bottom())
        mid_left = QPointF(outer_rect.left(), center.y())
        mid_right = QPointF(outer_rect.right(), center.y())

        painter.drawLine(mid_top, mid_right)
        painter.drawLine(mid_right, mid_bottom)
        painter.drawLine(mid_bottom, mid_left)
        painter.drawLine(mid_left, mid_top)

        painter.setFont(QFont("Arial", 11))

        house_boxes = self._north_house_rects(outer_rect)
        self._house_rects = house_boxes
        for idx, rect in house_boxes.items():
            fill = QColor(255, 255, 255, 200) if idx % 2 else QColor(230, 236, 248, 190)
            painter.fillRect(rect, fill)
            painter.drawText(rect, Qt.AlignCenter, str(idx))

        painter.setPen(QPen(Qt.darkBlue))
        self._planet_rects = {}
        for planet, longitude in self.positions.items():
            house = self._determine_house(longitude)
            target_rect = house_boxes.get(house)
            if target_rect is None:
                continue
            text = PLANET_GLYPHS.get(planet, planet[:2])
            if self.planet_details.get(planet, {}).get("retrograde") == "Yes":
                text = f"{text}\u211E"
            rect = target_rect.adjusted(0, 10, 0, 0)
            painter.drawText(rect, Qt.AlignTop | Qt.AlignHCenter, text)
            metrics = painter.fontMetrics()
            text_rect = QRectF(
                rect.center().x() - metrics.horizontalAdvance(text) / 2,
                rect.top(),
                metrics.horizontalAdvance(text),
                metrics.height(),
            )
            self._planet_rects[planet] = text_rect

    def _north_house_rects(self, outer_rect: QRectF) -> Dict[int, QRectF]:
        cell_w = outer_rect.width() / 4
        cell_h = outer_rect.height() / 3
        rects: Dict[int, QRectF] = {}
        for house in range(1, 13):
            row = (house - 1) // 4
            col = (house - 1) % 4
            rects[house] = QRectF(
                outer_rect.left() + col * cell_w,
                outer_rect.top() + row * cell_h,
                cell_w,
                cell_h,
            )
        return rects

    def _draw_south_indian_chart(self, painter: QPainter, width: int, height: int) -> None:
        grid_pen = QPen(Qt.black, 2)
        padding = 20
        size = min(width, height) - 2 * padding
        top_left_x = (width - size) / 2
        top_left_y = (height - size) / 2

        painter.setPen(grid_pen)
        painter.drawRect(top_left_x, top_left_y, size, size)

        cell_w = size / 4
        cell_h = size / 4
        for i in range(1, 4):
            painter.drawLine(top_left_x, top_left_y + i * cell_h, top_left_x + size, top_left_y + i * cell_h)
            painter.drawLine(top_left_x + i * cell_w, top_left_y, top_left_x + i * cell_w, top_left_y + size)

        painter.setFont(QFont("Arial", 11))
        house_mapping = self._south_house_rects(top_left_x, top_left_y, cell_w, cell_h)
        self._house_rects = house_mapping
        for idx, rect in house_mapping.items():
            fill = QColor(255, 255, 255, 200) if idx % 2 else QColor(230, 236, 248, 190)
            painter.fillRect(rect, fill)
            painter.drawText(rect, Qt.AlignCenter, str(idx))

        painter.setPen(QPen(Qt.darkBlue))
        self._planet_rects = {}
        for planet, longitude in self.positions.items():
            house = self._determine_house(longitude)
            target_rect = house_mapping.get(house)
            if target_rect is None:
                continue
            text = PLANET_GLYPHS.get(planet, planet[:2])
            if self.planet_details.get(planet, {}).get("retrograde") == "Yes":
                text = f"{text}\u211E"
            rect = target_rect.adjusted(0, 10, 0, 0)
            painter.drawText(rect, Qt.AlignTop | Qt.AlignHCenter, text)
            metrics = painter.fontMetrics()
            text_rect = QRectF(
                rect.center().x() - metrics.horizontalAdvance(text) / 2,
                rect.top(),
                metrics.horizontalAdvance(text),
                metrics.height(),
            )
            self._planet_rects[planet] = text_rect

    def _south_house_rects(self, top_left_x: float, top_left_y: float, cell_w: float, cell_h: float) -> Dict[int, QRectF]:
        rects: Dict[int, QRectF] = {}
        idx = 1
        for row in range(4):
            for col in range(4):
                if idx > 12:
                    break
                rects[idx] = QRectF(top_left_x + col * cell_w, top_left_y + row * cell_h, cell_w, cell_h)
                idx += 1
            if idx > 12:
                break
        return rects

    def _determine_house(self, longitude: float) -> int:
        asc = self.houses.get("House 1", self.houses.get("Asc", 0.0))
        relative = (longitude - asc + 360.0) % 360.0
        return int(relative // 30) + 1

    def mouseMoveEvent(self, event):  # type: ignore[override]
        point: QPoint = event.pos()
        for planet, rect in self._planet_rects.items():
            if rect.contains(point):
                detail = self.planet_details.get(planet)
                if detail:
                    tooltip = (
                        f"<b>{planet}</b><br>"
                        f"Longitude: {detail.get('longitude_dms')}<br>"
                        f"Nakshatra: {detail.get('nakshatra')} Pada {detail.get('pada')}<br>"
                        f"Lord: {detail.get('nakshatra_lord')}<br>"
                        f"Dignity: {detail.get('dignity')}"
                    )
                    QToolTip.showText(event.globalPos(), tooltip, self)
                    return
        for house, rect in self._house_rects.items():
            if rect.contains(point):
                key = str(house)
                detail = self.house_details.get(key) or self.house_details.get(house)
                if detail:
                    tooltip = (
                        f"<b>{house}</b><br>"
                        f"Sign: {detail.get('sign')}<br>"
                        f"Cusp: {detail.get('longitude_dms')}<br>"
                        f"Lord: {detail.get('lord')}"
                    )
                    QToolTip.showText(event.globalPos(), tooltip, self)
                    return
        QToolTip.hideText()
class DataTab(QWidget):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.title = title
        self.layout = QVBoxLayout(self)
        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setEditTriggers(QTableView.NoEditTriggers)
        self.proxy = QSortFilterProxyModel(self)
        self.model = DataFrameModel(self)
        self.proxy.setSourceModel(self.model)
        self.table.setModel(self.proxy)
        self.layout.addWidget(self.table)
        self.placeholder = QLabel("No data available.")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.placeholder)
        self.placeholder.hide()

    def update_data(self, df: pd.DataFrame) -> None:
        if df is None or df.empty:
            self.model.set_frame(pd.DataFrame())
            self.table.hide()
            self.placeholder.show()
        else:
            self.model.set_frame(df.reset_index(drop=True))
            self.table.show()
            self.placeholder.hide()


class ShadbalaChartTab(QWidget):
    """Displays stacked bar chart for Shadbala components."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        layout.addWidget(self.chart_view)

    def update_data(self, shadbala_df: pd.DataFrame) -> None:
        if shadbala_df is None or shadbala_df.empty:
            self.chart_view.setChart(QChart())
            return

        components = ["Sthana", "Dig", "Kala", "Ayana", "Cheshta", "Naisargika", "Drig"]
        series = QPercentBarSeries()
        total_per_row = shadbala_df[components].sum(axis=1)
        for component in components:
            values = shadbala_df[component].tolist()
            percent_values = [value / total if total else 0 for value, total in zip(values, total_per_row)]
            bar_set = QBarSet(component)
            bar_set.append(percent_values)
            series.append(bar_set)

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("Shadbala Component Ratios")
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)

        axis_x = QBarCategoryAxis()
        axis_x.append(shadbala_df["Planet"].tolist())
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = chart.createDefaultAxis()
        axis_y.setRange(0.0, 1.0)
        series.attachAxis(axis_y)

        self.chart_view.setChart(chart)


class AshtakavargaTab(QTabWidget):
    def __init__(self) -> None:
        super().__init__()
        self.sav_tab = DataTab("Sarvashtakavarga")
        self.addTab(self.sav_tab, "Sarva")
        self._bav_tabs: Dict[str, DataTab] = {}

    def update_data(self, sav_df: pd.DataFrame, bav: Dict[str, pd.DataFrame]) -> None:
        self.sav_tab.update_data(sav_df.reset_index().rename(columns={"index": "Planet"}))

        existing_keys = set(self._bav_tabs.keys())
        for planet, df in bav.items():
            if planet not in self._bav_tabs:
                tab = DataTab(f"{planet} BAV")
                self._bav_tabs[planet] = tab
                self.addTab(tab, planet)
            else:
                tab = self._bav_tabs[planet]
            tab.update_data(df.reset_index().rename(columns={"index": "Contributor"}))
            existing_keys.discard(planet)

        # Remove tabs that are no longer relevant
        for planet in existing_keys:
            tab = self._bav_tabs.pop(planet)
            index = self.indexOf(tab)
            if index != -1:
                self.removeTab(index)


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
        self.birth_dt: Optional[datetime] = None
        self.birth_moon_lon: Optional[float] = None
        self.birth_ashtakavarga: Optional[pd.DataFrame] = None

    def set_location(self, latitude: float, longitude: float) -> None:
        self.latitude = latitude
        self.longitude = longitude

    def set_birth_context(
        self,
        birth_dt: datetime,
        birth_moon_lon: float,
        birth_ashtakavarga: pd.DataFrame,
    ) -> None:
        self.birth_dt = birth_dt
        self.birth_moon_lon = birth_moon_lon
        self.birth_ashtakavarga = birth_ashtakavarga

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
            self.birth_dt,
            self.birth_moon_lon,
            self.birth_ashtakavarga,
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
        self.varga_details: Dict[str, Dict[str, object]] = {}
        self.chart_style = "North"
        self._current_houses: Dict[str, float] = {}
        self._current_positions: Dict[str, float] = {}
        self._current_planet_details: Dict[str, Dict[str, str]] = {}
        self._current_house_details: Dict[str, Dict[str, str]] = {}
        self._build_ui()
        self._apply_theme()

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
        style = self.style()
        compute_button.setIcon(style.standardIcon(QStyle.SP_MediaPlay))
        settings_button.setIcon(style.standardIcon(QStyle.SP_FileDialogDetailedView))
        save_button.setIcon(style.standardIcon(QStyle.SP_DialogSaveButton))
        load_button.setIcon(style.standardIcon(QStyle.SP_DialogOpenButton))
        button_layout.addWidget(compute_button)
        button_layout.addWidget(settings_button)
        button_layout.addWidget(save_button)
        button_layout.addWidget(load_button)
        layout.addLayout(button_layout)

        self.tabs = QTabWidget()
        self.chart_tab = QWidget()
        chart_layout = QVBoxLayout(self.chart_tab)

        self.varga_combo = QComboBox()
        self.varga_combo.addItems([
            "D1 (Rasi)",
            "D2 (Hora)",
            "D3 (Drekkana)",
            "D4 (Chaturthamsha)",
            "D5 (Panchamsha)",
            "D6 (Shasthamsha)",
            "D7 (Saptamsha)",
            "D8 (Ashtamsha)",
            "D9 (Navamsha)",
            "D10 (Dashamsha)",
            "D11 (Ekadashamsha)",
            "D12 (Dvadashamsha)",
            "D16 (Shodashamsha)",
            "D20 (Vimshamsha)",
            "D24 (Chaturvimshamsha)",
            "D27 (Saptavimshamsha)",
            "D30 (Trimshamsha)",
            "D40 (Chatvarimshamsha)",
            "D45 (Akshavedamsha)",
            "D60 (Shashtamsha)",
        ])
        chart_layout.addWidget(self.varga_combo)

        self.chart_canvas = ChartWidget()
        self.chart_canvas.setObjectName("chartCanvas")
        self.chart_canvas.set_chart_style(self.chart_style)
        chart_layout.addWidget(self.chart_canvas)
        self.varga_combo.currentTextChanged.connect(self.update_chart_view)
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
        self.ashtaka_tab = AshtakavargaTab()
        self.tabs.addTab(self.ashtaka_tab, "Ashtaka Varga")
        self.shadbala_tab = ShadbalaChartTab()
        self.tabs.addTab(self.shadbala_tab, "Shadbala")
        self.bhavabala_tab = DataTab("Bhavabala")
        self.tabs.addTab(self.bhavabala_tab, "Bhavabala")
        self.ishta_tab = DataTab("Ishta/Kashta")
        self.tabs.addTab(self.ishta_tab, "Ishta/Kashta")
        self.ai_tab = AITab(self.ai_predictor)
        self.tabs.addTab(self.ai_tab, "AI Prediction")
        layout.addWidget(self.tabs)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #f4f6fb;
            }
            QWidget {
                font-family: 'Segoe UI';
                font-size: 10pt;
            }
            QGroupBox {
                border: 1px solid #c7d3ef;
                border-radius: 8px;
                margin-top: 10px;
                padding: 12px;
                background-color: rgba(255, 255, 255, 210);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                color: #1c2541;
                font-weight: 600;
            }
            QPushButton {
                background-color: #3d7eff;
                border-radius: 6px;
                color: white;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #315fcc;
            }
            QPushButton:pressed {
                background-color: #264da6;
            }
            QPushButton:disabled {
                background-color: #aebbdc;
                color: #f0f3ff;
            }
            QTabWidget::pane {
                border: 1px solid #c7d3ef;
                border-radius: 8px;
                background: #ffffff;
            }
            QTabBar::tab {
                background: #e2e6f5;
                color: #1c2541;
                padding: 8px 18px;
                margin: 2px;
                border-radius: 6px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                font-weight: 600;
            }
            QTableView {
                background: #ffffff;
                alternate-background-color: #eef2fb;
                gridline-color: #d0d8ea;
                border: none;
            }
            QHeaderView::section {
                background: #dde3f6;
                padding: 6px;
                border: none;
                font-weight: 600;
            }
            #chartCanvas {
                background: transparent;
            }
            """
        )

    # ------------------------------------------------------------------
    def compute_kundali(self) -> None:
        date = self.date_edit.date().toPyDate()
        time = self.time_edit.time().toPyTime()
        dt = datetime.combine(date, time)
        latitude = self.lat_spin.value()
        longitude = self.lon_spin.value()
        positions = self.ephemeris.planetary_positions(dt, latitude, longitude)
        houses = self.ephemeris.house_cusps(dt, latitude, longitude)
        varga_details = self.varga_calculator.compute({planet: pos.longitude for planet, pos in positions.items()})
        varga_summary = {
            division: {planet: placement.sign for planet, placement in placements.items()}
            for division, placements in varga_details.items()
        }
        strength = StrengthCalculator(positions, houses, varga_summary)
        shadbala_df = strength.shadbala()
        bhavabala_df = strength.bhavabala()
        ishta_df = strength.compute_ishta_kashta()
        graha_df = positions_dataframe(positions)
        upagraha_df = graha_df[graha_df["Planet"].isin(["Gulika", "Mandi"])]
        chart_positions = {planet: pos.longitude for planet, pos in positions.items()}
        self.varga_details = varga_details
        self._current_houses = houses
        self._current_positions = chart_positions
        self._current_planet_details = self._planet_details_from_positions(positions)
        self._current_house_details = self._house_details_from_cusps(houses)
        self.chart_canvas.set_chart_style(self.chart_style)
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
        ascendant = houses.get("Asc", houses.get("House 1", 0.0))
        ashtaka_calc = AshtakavargaCalculator(chart_positions, ascendant)
        bav = ashtaka_calc.compute_bhinnashtakavarga()
        sav = ashtaka_calc.compute_sarvashtakavarga(bav)
        self.ashtaka_tab.update_data(sav, bav)
        self.ishta_tab.update_data(ishta_df)
        self.ai_tab.set_location(latitude, longitude)
        self.ai_tab.set_birth_context(dt, moon_lon, sav)
        divisional_frames = {
            name: pd.DataFrame([placement.as_dict() for placement in placements.values()]).set_index("Planet")
            for name, placements in varga_details.items()
        }
        self.current_record = KundaliRecord(
            metadata={
                "name": self.name_edit.text(),
                "datetime": dt.isoformat(),
                "latitude": latitude,
                "longitude": longitude,
            },
            planetary_positions=graha_df,
            divisional_positions=divisional_frames,
            strengths={"shadbala": shadbala_df.to_dict(orient="records"), "bhavabala": bhavabala_df.to_dict(orient="records")},
        )
        self.current_record.divisional_positions = divisional_frames
        self.current_record.metadata["datetime"] = dt.isoformat()
        self.current_record.metadata["latitude"] = latitude
        self.current_record.metadata["longitude"] = longitude
        self.varga_details = varga_details
        self.update_chart_view()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self)
        dialog.ayanamsa.setCurrentText(self.ephemeris.ayanamsa)
        dialog.house_system.setCurrentText(self.ephemeris.house_system)
        dialog.chart_style.setCurrentText(self.chart_style)
        if dialog.exec_():
            self.ephemeris.set_ayanamsa(dialog.ayanamsa.currentText())
            self.ephemeris.set_house_system(dialog.house_system.currentText())
            self.chart_style = dialog.chart_style.currentText()
            self.chart_canvas.set_chart_style(self.chart_style)
            self.compute_kundali()

    def update_chart_view(self) -> None:
        if not hasattr(self, "current_record"):
            return
        houses = getattr(self, "_current_houses", {})
        if not houses:
            return

        varga_name = self.varga_combo.currentText().split(" ")[0]
        chart_positions: Dict[str, float] = {}
        placements = self.varga_details.get(varga_name)
        if placements:
            for planet, placement in placements.items():
                sign = getattr(placement, "sign", None)
                degree = getattr(placement, "degree", None)
                if sign in ZODIAC_SIGNS and degree is not None:
                    chart_positions[planet] = ZODIAC_SIGNS.index(sign) * 30 + degree

        if not chart_positions:
            chart_positions = getattr(self, "_current_positions", {})
            planet_details = getattr(self, "_current_planet_details", {})
        else:
            planet_details = self._planet_details_from_longitudes(chart_positions)

        house_details = getattr(self, "_current_house_details", {})
        self.chart_canvas.set_chart_data(chart_positions, houses, planet_details, house_details)

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
        self.compute_kundali()


    def _planet_detail_entry(self, planet: str, longitude: float, retrograde: bool) -> Dict[str, str]:
        sign_index = int(longitude // 30) % len(ZODIAC_SIGNS)
        sign = ZODIAC_SIGNS[sign_index]
        degree_in_sign = longitude % 30
        nakshatra, pada, lord = nakshatra_details(longitude)
        return {
            "longitude_dms": format_dms(longitude),
            "nakshatra": nakshatra,
            "pada": str(pada),
            "nakshatra_lord": lord,
            "dignity": planetary_dignity(planet, sign, degree_in_sign),
            "retrograde": "Yes" if retrograde else "No",
        }

    def _planet_details_from_positions(self, positions: Dict[str, PlanetPosition]) -> Dict[str, Dict[str, str]]:
        details: Dict[str, Dict[str, str]] = {}
        for planet, data in positions.items():
            details[planet] = self._planet_detail_entry(planet, data.longitude, data.retrograde)
        return details

    def _planet_details_from_longitudes(self, longitudes: Dict[str, float]) -> Dict[str, Dict[str, str]]:
        details: Dict[str, Dict[str, str]] = {}
        for planet, longitude in longitudes.items():
            details[planet] = self._planet_detail_entry(planet, longitude, False)
        return details

    def _house_details_from_cusps(self, houses: Dict[str, float]) -> Dict[str, Dict[str, str]]:
        details: Dict[str, Dict[str, str]] = {}
        for idx in range(1, 13):
            key = f"House {idx}"
            longitude = houses.get(key)
            if longitude is None:
                continue
            sign = ZODIAC_SIGNS[int(longitude // 30) % len(ZODIAC_SIGNS)]
            entry = {
                "sign": sign,
                "longitude_dms": format_dms(longitude),
                "lord": SIGN_LORDS.get(sign, ""),
            }
            details[key] = entry
            details[str(idx)] = entry
        return details


def run_app() -> None:
    import sys

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
