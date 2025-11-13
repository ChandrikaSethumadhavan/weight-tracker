from __future__ import annotations

import sys
from datetime import date, datetime

from PyQt6 import QtCore, QtGui, QtWidgets
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from ..config import AppConfig
from ..database import AppRepository
from ..models import DailySnapshot, FoodEntry, FastingSession, WeightEntry, WorkoutEntry
from ..services.asset_manager import AssetManager
from ..services.calorie_service import CalorieAdvisor
from ..services.email_service import EmailService
from ..services.motivation_service import MotivationService
from ..services.reminder_service import ReminderService


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, config: AppConfig, repo: AppRepository) -> None:
        super().__init__()
        self.config = config
        self.repo = repo
        self.asset_manager = AssetManager(config.assets_dir, config.gif_urls)
        self.calorie_advisor = CalorieAdvisor(config.openai_api_key, config.nutrition_api_key)
        self.motivation_service = MotivationService(config.openai_api_key)
        self.email_service = EmailService(config.email)
        self.reminder_service = ReminderService(repo, self.email_service, config.reminder, self)
        self.reminder_service.reminderTriggered.connect(self._show_status)
        self.reminder_service.emailTriggered.connect(self._show_status)
        self.statusBar().showMessage("Ready to cheer on your journey!")
        self._build_ui()
        self.refresh_all()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.setWindowTitle("GlowUp Weight Journey")
        self.resize(1280, 780)
        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        self.dashboard_tab = DashboardTab(
            self.repo,
            self.asset_manager,
            self.motivation_service,
            self.email_service,
            self.config,
            self.config.deficit_goal,
        )
        self.dashboard_tab.sendEmailRequested.connect(self._handle_send_email)

        self.checkin_tab = CheckInTab(self.repo, self.calorie_advisor, self.config)
        self.checkin_tab.dataSaved.connect(self.refresh_all)

        self.progress_tab = ProgressTab(self.repo, self.config)
        self.settings_tab = SettingsTab(self.repo, self.config)
        self.settings_tab.settingsSaved.connect(self._handle_settings_saved)

        self.tabs.addTab(self.dashboard_tab, "Dashboard")
        self.tabs.addTab(self.checkin_tab, "Daily Check-In")
        self.tabs.addTab(self.progress_tab, "Progress & Charts")
        self.tabs.addTab(self.settings_tab, "Settings")

    def refresh_all(self) -> None:
        snapshot = self._build_snapshot()
        self.dashboard_tab.refresh(snapshot)
        self.checkin_tab.refresh_selected_date()
        self.progress_tab.refresh()

    def _build_snapshot(self) -> DailySnapshot:
        today = date.today()
        summary = self.repo.dump_day_summary(today)
        return DailySnapshot(
            entry_date=today,
            weight=summary.get("weight"),
            calories_in=summary.get("calories_in", 0.0),
            calories_out=summary.get("calories_out", 0.0),
            carbs_in=summary.get("carbs_in", 0.0),
            protein_in=summary.get("protein_in", 0.0),
            fat_in=summary.get("fat_in", 0.0),
            streak=summary.get("streak", 0),
            deficit_goal=self.config.deficit_goal,
            mood=summary.get("mood"),
        )

    def _handle_send_email(self, message: str) -> None:
        try:
            self.email_service.send_motivation("Daily pep talk", message)
            self._show_status("Motivation email fired!")
        except Exception as exc:
            self._show_status(f"Email failed: {exc}")

    def _handle_settings_saved(self, overrides: dict) -> None:
        self.config.apply_overrides(overrides)
        self.calorie_advisor = CalorieAdvisor(self.config.openai_api_key, self.config.nutrition_api_key)
        self.motivation_service = MotivationService(self.config.openai_api_key)
        self.email_service = EmailService(self.config.email)
        self.dashboard_tab.update_services(self.motivation_service, self.email_service, self.config, self.config.deficit_goal)
        self.checkin_tab.update_services(self.calorie_advisor, self.config)
        self.progress_tab.update_config(self.config)
        self.reminder_service.deleteLater()
        self.reminder_service = ReminderService(self.repo, self.email_service, self.config.reminder, self)
        self.reminder_service.reminderTriggered.connect(self._show_status)
        self.reminder_service.emailTriggered.connect(self._show_status)
        self._show_status("Settings refreshed.")
        self.refresh_all()

    def _show_status(self, text: str) -> None:
        self.statusBar().showMessage(text, 8000)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.repo.close()
        super().closeEvent(event)


# ----------------------------------------------------------------------
class DashboardTab(QtWidgets.QWidget):
    sendEmailRequested = QtCore.pyqtSignal(str)

    def __init__(
        self,
        repo: AppRepository,
        asset_manager: AssetManager,
        motivation_service: MotivationService,
        email_service: EmailService,
        config: AppConfig,
        deficit_goal: int,
    ) -> None:
        super().__init__()
        self.repo = repo
        self.asset_manager = asset_manager
        self.motivation_service = motivation_service
        self.email_service = email_service
        self.config = config
        self.deficit_goal = deficit_goal
        self._current_message = ""
        self.macro_targets = {
            "carbs": round(self.config.target_calories * 0.5 / 4),
            "protein": round(self.config.target_calories * 0.25 / 4),
            "fat": round(self.config.target_calories * 0.25 / 9),
        }
        self.active_fast: FastingSession | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        hero_layout = QtWidgets.QHBoxLayout()

        self.mascot_label = QtWidgets.QLabel()
        self.mascot_label.setMinimumSize(280, 260)
        self.mascot_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.mascot_label.setScaledContents(True)
        self.mascot_label.setStyleSheet("background-color:#15172a; border-radius:18px;")
        self._movie = None
        self._set_mascot_visual()
        hero_layout.addWidget(self.mascot_label, 1)

        self.summary_frame = QtWidgets.QFrame()
        self.summary_frame.setStyleSheet(
            "QFrame {background-color:#1e2137; border-radius:18px; padding:16px;} "
            "QLabel {color:#f8f8f2; font-size:15px;}"
        )
        summary_layout = QtWidgets.QGridLayout(self.summary_frame)
        self.stat_labels = {
            "start": QtWidgets.QLabel("-- kg"),
            "today": QtWidgets.QLabel("-- kg"),
            "net": QtWidgets.QLabel("-- kcal"),
            "remaining": QtWidgets.QLabel("-- kcal"),
            "streak": QtWidgets.QLabel("-- days"),
        }
        summary_layout.addWidget(QtWidgets.QLabel("Start"), 0, 0)
        summary_layout.addWidget(self.stat_labels["start"], 0, 1)
        summary_layout.addWidget(QtWidgets.QLabel("Today"), 1, 0)
        summary_layout.addWidget(self.stat_labels["today"], 1, 1)
        summary_layout.addWidget(QtWidgets.QLabel("Net"), 2, 0)
        summary_layout.addWidget(self.stat_labels["net"], 2, 1)
        summary_layout.addWidget(QtWidgets.QLabel("Remaining"), 3, 0)
        summary_layout.addWidget(self.stat_labels["remaining"], 3, 1)
        summary_layout.addWidget(QtWidgets.QLabel("Streak"), 4, 0)
        summary_layout.addWidget(self.stat_labels["streak"], 4, 1)
        hero_layout.addWidget(self.summary_frame, 2)

        layout.addLayout(hero_layout)

        widget_grid = QtWidgets.QGridLayout()

        self.macro_frame = QtWidgets.QGroupBox("Macro radar")
        self.macro_frame.setStyleSheet("QGroupBox {color:#fdfdfd; font-size:16px;}")
        macro_layout = QtWidgets.QFormLayout(self.macro_frame)
        self.carb_bar = self._build_progress_bar("#24e8a5")
        self.protein_bar = self._build_progress_bar("#82e0ff")
        self.fat_bar = self._build_progress_bar("#ffb347")
        macro_layout.addRow("Carbs", self.carb_bar)
        macro_layout.addRow("Protein", self.protein_bar)
        macro_layout.addRow("Fat", self.fat_bar)

        self.meal_frame = QtWidgets.QGroupBox("Meals today")
        self.meal_frame.setStyleSheet("QGroupBox {color:#fdfdfd; font-size:16px;}")
        meal_layout = QtWidgets.QVBoxLayout(self.meal_frame)
        self.meal_list = QtWidgets.QTreeWidget()
        self.meal_list.setHeaderLabels(["Meal", "Calories", "Carbs", "Protein", "Fat"])
        self.meal_list.setStyleSheet("QTreeWidget {background-color:#15172a; color:#fdfdfd;}")
        meal_layout.addWidget(self.meal_list)

        self.fasting_frame = QtWidgets.QGroupBox("Fasting tracker")
        self.fasting_frame.setStyleSheet("QGroupBox {color:#fdfdfd; font-size:16px;}")
        fasting_layout = QtWidgets.QVBoxLayout(self.fasting_frame)
        self.fast_status_label = QtWidgets.QLabel("Not fasting")
        self.fast_timer_label = QtWidgets.QLabel("00:00:00")
        self.fast_timer_label.setStyleSheet("font-size:24px; font-weight:bold;")
        button_row = QtWidgets.QHBoxLayout()
        self.fast_toggle_btn = QtWidgets.QPushButton("Start fasting")
        self.fast_toggle_btn.clicked.connect(self._toggle_fasting)
        button_row.addWidget(self.fast_toggle_btn)
        button_row.addStretch(1)
        self.fast_history_list = QtWidgets.QListWidget()
        self.fast_history_list.setMaximumHeight(120)
        fasting_layout.addWidget(self.fast_status_label)
        fasting_layout.addWidget(self.fast_timer_label)
        fasting_layout.addLayout(button_row)
        fasting_layout.addWidget(QtWidgets.QLabel("Last fasts"))
        fasting_layout.addWidget(self.fast_history_list)
        self.fast_timer = QtCore.QTimer(self)
        self.fast_timer.setInterval(1000)
        self.fast_timer.timeout.connect(self._update_fasting_clock)

        widget_grid.addWidget(self.macro_frame, 0, 0, 1, 2)
        widget_grid.addWidget(self.fasting_frame, 0, 2)
        widget_grid.addWidget(self.meal_frame, 1, 0, 1, 3)

        layout.addLayout(widget_grid)

        self.motivation_box = QtWidgets.QTextEdit()
        self.motivation_box.setReadOnly(True)
        self.motivation_box.setStyleSheet(
            "font-size:16px; background-color:#1c1f2f; color:#f8f8f2; "
            "border:1px solid #ffb347; border-radius:10px;"
        )
        layout.addWidget(self.motivation_box)

        button_bar = QtWidgets.QHBoxLayout()
        self.refresh_button = QtWidgets.QPushButton("New motivation")
        self.refresh_button.clicked.connect(self._handle_refresh)
        self.email_button = QtWidgets.QPushButton("Send pep email")
        self.email_button.clicked.connect(self._handle_email)
        self.email_button.setEnabled(self.email_service.is_configured)
        button_bar.addWidget(self.refresh_button)
        button_bar.addWidget(self.email_button)
        button_bar.addStretch(1)
        layout.addLayout(button_bar)

    def _build_progress_bar(self, color: str) -> QtWidgets.QProgressBar:
        bar = QtWidgets.QProgressBar()
        bar.setRange(0, 100)
        bar.setFormat("%p%")
        bar.setStyleSheet(
            f"QProgressBar {{background-color:#0f111d; border-radius:6px;}} "
            f"QProgressBar::chunk {{background-color:{color}; border-radius:6px;}}"
        )
        return bar

    def refresh(self, snapshot: DailySnapshot) -> None:
        start_weight = self.repo.get_starting_weight() or snapshot.weight or 0
        self.stat_labels["start"].setText(f"{start_weight:.1f} kg" if start_weight else "--")
        if snapshot.weight:
            self.stat_labels["today"].setText(f"{snapshot.weight:.1f} kg")
        else:
            self.stat_labels["today"].setText("Log it")
        self.stat_labels["net"].setText(f"{snapshot.net:.0f} kcal")
        remaining = self.config.target_calories - snapshot.calories_in
        self.stat_labels["remaining"].setText(f"{remaining:.0f} kcal")
        self.stat_labels["streak"].setText(f"{snapshot.streak} days")
        self._current_message = self.motivation_service.pep_talk(snapshot)
        self.motivation_box.setText(self._current_message)
        self._update_macro_bars(snapshot)
        self._populate_meal_list(snapshot.entry_date)
        self._sync_fasting_state()

    def _handle_refresh(self) -> None:
        snapshot = DailySnapshot(
            date.today(),
            self.repo.get_latest_weight(),
            0,
            0,
            0,
            0,
            0,
            self.repo.get_streak(),
            self.deficit_goal,
        )
        self._current_message = self.motivation_service.pep_talk(snapshot)
        self.motivation_box.setText(self._current_message)

    def _handle_email(self) -> None:
        if not self.email_service.is_configured:
            QtWidgets.QMessageBox.information(self, "Missing email config", "Update SMTP settings first.")
            return
        self.sendEmailRequested.emit(self._current_message or "Keep pushing! You got this.")

    def _set_mascot_visual(self) -> None:
        self._movie = self.asset_manager.random_movie()
        if self._movie:
            self.mascot_label.setMovie(self._movie)
        else:
            placeholder = self.asset_manager.placeholder_pixmap()
            if placeholder:
                self.mascot_label.setPixmap(placeholder)
            else:
                self.mascot_label.setText("Add a mascot GIF in Settings")

    def _update_macro_bars(self, snapshot: DailySnapshot) -> None:
        def pct(value, target):
            if target <= 0:
                return 0
            return max(0, min(100, int((value / target) * 100)))

        self.carb_bar.setValue(pct(snapshot.carbs_in, self.macro_targets["carbs"]))
        self.protein_bar.setValue(pct(snapshot.protein_in, self.macro_targets["protein"]))
        self.fat_bar.setValue(pct(snapshot.fat_in, self.macro_targets["fat"]))

    def _populate_meal_list(self, entry_date: date) -> None:
        self.meal_list.clear()
        rows = self.repo.get_meal_breakdown(entry_date)
        for row in rows:
            node = QtWidgets.QTreeWidgetItem(
                [
                    row["meal_type"].title(),
                    f"{row['calories']:.0f} kcal",
                    f"{row['carbs']:.0f} g",
                    f"{row['protein']:.0f} g",
                    f"{row['fat']:.0f} g",
                ]
            )
            self.meal_list.addTopLevelItem(node)

    def _toggle_fasting(self) -> None:
        if self.active_fast:
            self.repo.complete_fasting(datetime.utcnow())
            self.active_fast = None
            self.fast_timer.stop()
            self.fast_status_label.setText("Fast completed")
        else:
            self.repo.start_fasting(datetime.utcnow())
            self.fast_status_label.setText("Fasting...")
        self._sync_fasting_state()

    def _sync_fasting_state(self) -> None:
        self.active_fast = self.repo.get_active_fast()
        if self.active_fast:
            self.fast_toggle_btn.setText("End fasting")
            self.fast_status_label.setText("Fasting in progress")
            self.fast_timer.start()
            self._update_fasting_clock()
        else:
            self.fast_toggle_btn.setText("Start fasting")
            self.fast_status_label.setText("Not fasting")
            self.fast_timer.stop()
            self.fast_timer_label.setText("00:00:00")
        self._refresh_fast_history()

    def _update_fasting_clock(self) -> None:
        if not self.active_fast or not self.active_fast.start_time:
            self.fast_timer_label.setText("00:00:00")
            return
        elapsed = datetime.utcnow() - self.active_fast.start_time
        total_seconds = int(elapsed.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.fast_timer_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    def _refresh_fast_history(self) -> None:
        self.fast_history_list.clear()
        for session in self.repo.get_recent_fasts():
            duration = session.duration()
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            start_label = session.start_time.strftime("%d %b %H:%M") if session.start_time else "?"
            self.fast_history_list.addItem(f"{start_label} · {hours}h {minutes}m")

    def update_services(
        self,
        motivation_service: MotivationService,
        email_service: EmailService,
        config: AppConfig,
        deficit_goal: int,
    ) -> None:
        self.motivation_service = motivation_service
        self.email_service = email_service
        self.config = config
        self.deficit_goal = deficit_goal
        self.email_button.setEnabled(self.email_service.is_configured)
        self.macro_targets = {
            "carbs": round(self.config.target_calories * 0.5 / 4),
            "protein": round(self.config.target_calories * 0.25 / 4),
            "fat": round(self.config.target_calories * 0.25 / 9),
        }
        self._set_mascot_visual()


# ----------------------------------------------------------------------
class CheckInTab(QtWidgets.QWidget):
    dataSaved = QtCore.pyqtSignal()

    def __init__(
        self,
        repo: AppRepository,
        calorie_advisor: CalorieAdvisor,
        config: AppConfig,
    ):
        super().__init__()
        self.repo = repo
        self.calorie_advisor = calorie_advisor
        self.config = config
        self._pending_food_source = "manual"
        self._build_ui()
        self.refresh_selected_date()

    def _build_ui(self) -> None:
        main_layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QGridLayout()
        self.date_edit = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.dateChanged.connect(lambda _: self.refresh_selected_date())
        self.weight_spin = QtWidgets.QDoubleSpinBox()
        self.weight_spin.setRange(20, 250)
        self.weight_spin.setSuffix(" kg")
        self.mood_box = QtWidgets.QComboBox()
        self.mood_box.addItems(["Balanced :)", "Pumped!", "Tired", "Off day"])
        self.save_weight_btn = QtWidgets.QPushButton("Save weight")
        self.save_weight_btn.clicked.connect(self._handle_save_weight)

        form.addWidget(QtWidgets.QLabel("Date"), 0, 0)
        form.addWidget(self.date_edit, 0, 1)
        form.addWidget(QtWidgets.QLabel("Weight"), 1, 0)
        form.addWidget(self.weight_spin, 1, 1)
        form.addWidget(QtWidgets.QLabel("Mood"), 2, 0)
        form.addWidget(self.mood_box, 2, 1)
        form.addWidget(self.save_weight_btn, 3, 0, 1, 2)
        main_layout.addLayout(form)

        # Food inputs
        food_box = QtWidgets.QGroupBox("Today's fuel")
        food_layout = QtWidgets.QGridLayout(food_box)
        self.food_input = QtWidgets.QLineEdit()
        self.food_calorie_spin = QtWidgets.QDoubleSpinBox()
        self.food_calorie_spin.setRange(0, 3000)
        self.food_calorie_spin.setSuffix(" kcal")
        self.meal_type_box = QtWidgets.QComboBox()
        self.meal_type_box.addItems(["Breakfast", "Lunch", "Dinner", "Snack"])
        self.carb_spin = QtWidgets.QDoubleSpinBox()
        self.carb_spin.setRange(0, 500)
        self.carb_spin.setSuffix(" g")
        self.protein_spin = QtWidgets.QDoubleSpinBox()
        self.protein_spin.setRange(0, 300)
        self.protein_spin.setSuffix(" g")
        self.fat_spin = QtWidgets.QDoubleSpinBox()
        self.fat_spin.setRange(0, 200)
        self.fat_spin.setSuffix(" g")
        self.food_auto_btn = QtWidgets.QPushButton("Auto estimate (GPT/API)")
        self.food_auto_btn.clicked.connect(self._handle_auto_estimate)
        self.food_add_btn = QtWidgets.QPushButton("Add meal log")
        self.food_add_btn.clicked.connect(self._handle_add_food)
        self.food_delete_btn = QtWidgets.QPushButton("Delete selected meal")
        self.food_delete_btn.clicked.connect(self._handle_delete_food)
        self.food_filter_box = QtWidgets.QComboBox()
        self.food_filter_box.addItems(["All", "Breakfast", "Lunch", "Dinner", "Snack"])
        self.food_filter_box.currentIndexChanged.connect(self._load_food_table)
        self.food_table = QtWidgets.QTableWidget(0, 7)
        self.food_table.setHorizontalHeaderLabels(
            ["Meal", "Food", "Calories", "Carbs", "Protein", "Fat", "Source"]
        )
        self.food_table.horizontalHeader().setStretchLastSection(True)
        self.food_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.food_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.food_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.food_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

        macro_grid = QtWidgets.QHBoxLayout()
        macro_grid.addWidget(QtWidgets.QLabel("Carbs"))
        macro_grid.addWidget(self.carb_spin)
        macro_grid.addWidget(QtWidgets.QLabel("Protein"))
        macro_grid.addWidget(self.protein_spin)
        macro_grid.addWidget(QtWidgets.QLabel("Fat"))
        macro_grid.addWidget(self.fat_spin)

        food_layout.addWidget(QtWidgets.QLabel("Description"), 0, 0)
        food_layout.addWidget(self.food_input, 0, 1, 1, 2)
        food_layout.addWidget(QtWidgets.QLabel("Meal"), 1, 0)
        food_layout.addWidget(self.meal_type_box, 1, 1)
        food_layout.addWidget(QtWidgets.QLabel("Calories"), 2, 0)
        food_layout.addWidget(self.food_calorie_spin, 2, 1)
        food_layout.addWidget(self.food_auto_btn, 2, 2)
        food_layout.addLayout(macro_grid, 3, 0, 1, 3)
        food_layout.addWidget(self.food_add_btn, 4, 2)
        food_layout.addWidget(self.food_delete_btn, 4, 1)
        food_layout.addWidget(QtWidgets.QLabel("View meals"), 5, 0)
        food_layout.addWidget(self.food_filter_box, 5, 1)
        food_layout.addWidget(self.food_table, 6, 0, 1, 3)

        # Workout box
        workout_box = QtWidgets.QGroupBox("Workouts")
        workout_layout = QtWidgets.QGridLayout(workout_box)
        self.workout_input = QtWidgets.QLineEdit()
        self.workout_calorie_spin = QtWidgets.QDoubleSpinBox()
        self.workout_calorie_spin.setRange(0, 2000)
        self.workout_calorie_spin.setSuffix(" kcal burned")
        self.workout_add_btn = QtWidgets.QPushButton("Add workout")
        self.workout_add_btn.clicked.connect(self._handle_add_workout)
        self.workout_table = QtWidgets.QTableWidget(0, 3)
        self.workout_table.setHorizontalHeaderLabels(["Workout", "Calories", "Duration"])
        self.workout_table.horizontalHeader().setStretchLastSection(True)
        self.workout_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.workout_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.workout_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.workout_delete_btn = QtWidgets.QPushButton("Delete selected workout")
        self.workout_delete_btn.clicked.connect(self._handle_delete_workout)

        workout_layout.addWidget(QtWidgets.QLabel("Description"), 0, 0)
        workout_layout.addWidget(self.workout_input, 0, 1, 1, 2)
        workout_layout.addWidget(QtWidgets.QLabel("Calories burnt"), 1, 0)
        workout_layout.addWidget(self.workout_calorie_spin, 1, 1)
        workout_layout.addWidget(self.workout_add_btn, 1, 2)
        workout_layout.addWidget(self.workout_delete_btn, 2, 2)
        workout_layout.addWidget(self.workout_table, 3, 0, 1, 3)

        self.summary_label = QtWidgets.QLabel()
        self.summary_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.summary_label.setStyleSheet("font-size: 15px; font-weight: bold; padding: 8px;")

        main_layout.addWidget(food_box)
        main_layout.addWidget(workout_box)
        main_layout.addWidget(self.summary_label)

    def refresh_selected_date(self) -> None:
        selected = self.date_edit.date().toPyDate()
        weight = self.repo.get_weight(selected)
        if weight:
            self.weight_spin.setValue(weight)
        self._load_food_table()
        self._load_workout_table()
        self._update_summary()

    def _handle_save_weight(self) -> None:
        entry = WeightEntry(
            entry_date=self.date_edit.date().toPyDate(),
            weight=self.weight_spin.value(),
            mood=self.mood_box.currentText(),
        )
        self.repo.upsert_weight(entry)
        if entry.entry_date == date.today():
            self.repo.bump_streak(entry.entry_date)
        self.summary_label.setText("Weight saved! Keep up the streak.")
        self.dataSaved.emit()

    def _handle_add_food(self) -> None:
        description = self.food_input.text().strip()
        if not description:
            QtWidgets.QMessageBox.warning(self, "Missing info", "Describe the food first.")
            return
        entry = FoodEntry(
            entry_date=self.date_edit.date().toPyDate(),
            description=description,
            calories=self.food_calorie_spin.value(),
            meal_type=self.meal_type_box.currentText().lower(),
            carbs=self.carb_spin.value(),
            protein=self.protein_spin.value(),
            fat=self.fat_spin.value(),
            source=self._pending_food_source,
        )
        self.repo.log_food(entry)
        self.food_input.clear()
        self.food_calorie_spin.setValue(0)
        self._pending_food_source = "manual"
        self.carb_spin.setValue(0)
        self.protein_spin.setValue(0)
        self.fat_spin.setValue(0)
        self._load_food_table()
        self._update_summary()
        self.dataSaved.emit()

    def _handle_delete_food(self) -> None:
        entry_id = self._selected_entry_id(self.food_table)
        if entry_id is None:
            QtWidgets.QMessageBox.information(self, "Select a row", "Choose a food entry to delete.")
            return
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Delete food entry",
            "Remove the selected food entry?",
            QtWidgets.QMessageBox.StandardButton.Yes,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.repo.delete_food_entry(entry_id)
        self._load_food_table()
        self._update_summary()
        self.dataSaved.emit()

    def _handle_add_workout(self) -> None:
        description = self.workout_input.text().strip()
        if not description:
            QtWidgets.QMessageBox.warning(self, "Missing info", "Describe the workout first.")
            return
        entry = WorkoutEntry(
            entry_date=self.date_edit.date().toPyDate(),
            description=description,
            calories_burned=self.workout_calorie_spin.value(),
            duration_minutes=None,
        )
        self.repo.log_workout(entry)
        self.workout_input.clear()
        self.workout_calorie_spin.setValue(0)
        self._load_workout_table()
        self._update_summary()
        self.dataSaved.emit()

    def _handle_delete_workout(self) -> None:
        entry_id = self._selected_entry_id(self.workout_table)
        if entry_id is None:
            QtWidgets.QMessageBox.information(self, "Select a row", "Choose a workout entry to delete.")
            return
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Delete workout entry",
            "Remove the selected workout entry?",
            QtWidgets.QMessageBox.StandardButton.Yes,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.repo.delete_workout_entry(entry_id)
        self._load_workout_table()
        self._update_summary()
        self.dataSaved.emit()

    def _handle_auto_estimate(self) -> None:
        description = self.food_input.text().strip()
        if not description:
            QtWidgets.QMessageBox.warning(self, "Describe food", "Type what you ate first.")
            return
        try:
            estimate = self.calorie_advisor.estimate(description)
            self.food_calorie_spin.setValue(round(estimate.calories, 1))
            self._pending_food_source = estimate.source
            note = f"\n{estimate.note}" if estimate.note else ""
            self.carb_spin.setValue(round(estimate.carbs, 1))
            self.protein_spin.setValue(round(estimate.protein, 1))
            self.fat_spin.setValue(round(estimate.fat, 1))
            QtWidgets.QToolTip.showText(
                QtGui.QCursor.pos(),
                f"{estimate.source} estimate: {estimate.calories:.0f} kcal{note}",
                self.food_auto_btn,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Estimation failed", str(exc))

    def _load_food_table(self) -> None:
        rows = self.repo.get_food_for_date(self.date_edit.date().toPyDate())
        filter_label = self.food_filter_box.currentText().lower()
        filtered = []
        for row in rows:
            if filter_label != "all" and row["meal_type"].lower() != filter_label:
                continue
            filtered.append(row)
        self.food_table.setRowCount(len(filtered))
        for row_index, row in enumerate(filtered):
            meal_item = QtWidgets.QTableWidgetItem(row["meal_type"].title())
            desc_item = QtWidgets.QTableWidgetItem(row["description"])
            desc_item.setData(QtCore.Qt.ItemDataRole.UserRole, row["id"])
            self.food_table.setItem(row_index, 0, meal_item)
            self.food_table.setItem(row_index, 1, desc_item)
            self.food_table.setItem(row_index, 2, QtWidgets.QTableWidgetItem(f"{row['calories']:.0f}"))
            self.food_table.setItem(row_index, 3, QtWidgets.QTableWidgetItem(f"{row['carbs']:.0f}g"))
            self.food_table.setItem(row_index, 4, QtWidgets.QTableWidgetItem(f"{row['protein']:.0f}g"))
            self.food_table.setItem(row_index, 5, QtWidgets.QTableWidgetItem(f"{row['fat']:.0f}g"))
            source = row["source"] or ""
            if "(" in source:
                source = source.split("(", 1)[0].strip()
            self.food_table.setItem(row_index, 6, QtWidgets.QTableWidgetItem(source or "manual"))

    def _load_workout_table(self) -> None:
        rows = self.repo.get_workouts_for_date(self.date_edit.date().toPyDate())
        self.workout_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            desc_item = QtWidgets.QTableWidgetItem(row["description"])
            desc_item.setData(QtCore.Qt.ItemDataRole.UserRole, row["id"])
            self.workout_table.setItem(row_index, 0, desc_item)
            self.workout_table.setItem(row_index, 1, QtWidgets.QTableWidgetItem(f"{row['calories_burned']:.0f}"))
            duration = f"{row['duration_minutes']:.0f} min" if row["duration_minutes"] else "-"
            self.workout_table.setItem(row_index, 2, QtWidgets.QTableWidgetItem(duration))

    def _update_summary(self) -> None:
        totals = self.repo.get_daily_totals(self.date_edit.date().toPyDate())
        net = totals["calories_in"] - totals["calories_out"]
        if net > self.config.deficit_goal:
            text = f"Net {net:.0f} kcal. Eat {net - self.config.deficit_goal:.0f} kcal less or burn more."
            color = "#ff6b6b"
        else:
            text = f"Great deficit! Net {net:.0f} kcal. You're ahead by {self.config.deficit_goal - net:.0f}."
            color = "#2ecc71"
        if totals["calories_in"] > 1000 and totals["calories_out"] == 0:
            text += " Workout flag is still empty - go move!"
        self.summary_label.setStyleSheet(f"font-size: 15px; font-weight: bold; padding:8px; background:{color}33;")
        macro_line = (
            f"Carbs {totals['carbs_in']:.0f}g | Protein {totals['protein_in']:.0f}g | Fat {totals['fat_in']:.0f}g"
        )
        self.summary_label.setText(f"{text}\n{macro_line}")

    def update_services(self, advisor: CalorieAdvisor, config: AppConfig) -> None:
        self.calorie_advisor = advisor
        self.config = config

    def _selected_entry_id(self, table: QtWidgets.QTableWidget) -> int | None:
        selection = table.selectionModel()
        if not selection:
            return None
        rows = selection.selectedRows()
        if not rows:
            return None
        row_index = rows[0].row()
        for column in range(table.columnCount()):
            item = table.item(row_index, column)
            if not item:
                continue
            value = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
        return None


# ----------------------------------------------------------------------
class ProgressTab(QtWidgets.QWidget):
    def __init__(self, repo: AppRepository, config: AppConfig) -> None:
        super().__init__()
        self.repo = repo
        self.config = config
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        self.canvas = FigureCanvas(Figure(figsize=(6, 5)))
        self.canvas.figure.patch.set_facecolor("#10121a")
        self.ax_weight = self.canvas.figure.add_subplot(211)
        self.ax_calories = self.canvas.figure.add_subplot(212)
        for ax in (self.ax_weight, self.ax_calories):
            ax.set_facecolor("#161a2b")
            ax.tick_params(colors="#f5f6fa")
            ax.spines["bottom"].set_color("#444")
            ax.spines["left"].set_color("#444")
            ax.title.set_color("#f5f6fa")
        layout.addWidget(self.canvas)

    def refresh(self) -> None:
        weight_rows = self.repo.get_weight_history(30)
        calorie_rows = self.repo.get_recent_calorie_windows(14)

        self.ax_weight.clear()
        self.ax_weight.set_facecolor("#161a2b")
        self.ax_weight.tick_params(colors="#f5f6fa")
        self.ax_weight.spines["bottom"].set_color("#444")
        self.ax_weight.spines["left"].set_color("#444")
        if weight_rows:
            dates = [row["entry_date"] for row in weight_rows]
            weights = [row["weight"] for row in weight_rows]
            x = list(range(len(dates)))
            self.ax_weight.plot(x, weights, color="#7ed6df", linewidth=2.5, marker="o")
            self.ax_weight.fill_between(x, weights, color="#7ed6df", alpha=0.2)
            self.ax_weight.set_ylabel("Weight (kg)", color="#f5f6fa")
            self.ax_weight.set_xticks(x)
            self.ax_weight.set_xticklabels(dates, rotation=30, ha="right")
            self.ax_weight.set_title("Weight Trend", fontsize=12)
        else:
            self.ax_weight.text(0.5, 0.5, "Log weight to unlock this chart.", ha="center")

        self.ax_calories.clear()
        self.ax_calories.set_facecolor("#161a2b")
        self.ax_calories.tick_params(colors="#f5f6fa")
        self.ax_calories.spines["bottom"].set_color("#444")
        self.ax_calories.spines["left"].set_color("#444")
        if calorie_rows:
            dates = [row["entry_date"] for row in calorie_rows]
            calories_in = [row["calories_in"] for row in calorie_rows]
            calories_out = [row["calories_out"] for row in calorie_rows]
            x = list(range(len(dates)))
            self.ax_calories.plot(x, calories_in, label="Calories in", color="#ff7675", linewidth=2.5)
            self.ax_calories.plot(x, calories_out, label="Calories burned", color="#00cec9", linewidth=2.5)
            self.ax_calories.fill_between(x, calories_in, color="#ff7675", alpha=0.15)
            self.ax_calories.fill_between(x, calories_out, color="#00cec9", alpha=0.15)
            self.ax_calories.axhline(
                self.config.target_calories,
                color="#ffeaa7",
                linestyle="--",
                label="Target intake",
                linewidth=1.5,
            )
            self.ax_calories.legend()
            self.ax_calories.set_xticks(x)
            self.ax_calories.set_xticklabels(dates, rotation=30, ha="right")
            self.ax_calories.set_title("Calories vs Burn", fontsize=12)
            self.ax_calories.set_ylabel("Calories", color="#f5f6fa")
        else:
            self.ax_calories.text(0.5, 0.5, "Add food/workout entries to see calorie trends.", ha="center")

        self.canvas.draw_idle()

    def update_config(self, config: AppConfig) -> None:
        self.config = config


# ----------------------------------------------------------------------
class SettingsTab(QtWidgets.QWidget):
    settingsSaved = QtCore.pyqtSignal(dict)

    def __init__(self, repo: AppRepository, config: AppConfig) -> None:
        super().__init__()
        self.repo = repo
        self.config = config
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QtWidgets.QFormLayout(self)
        meta = self.repo.get_meta_bulk()

        self.target_spin = QtWidgets.QSpinBox()
        self.target_spin.setRange(800, 3500)
        self.target_spin.setValue(int(meta.get("target_calories", self.config.target_calories)))

        self.deficit_spin = QtWidgets.QSpinBox()
        self.deficit_spin.setRange(100, 2000)
        self.deficit_spin.setValue(int(meta.get("deficit_goal", self.config.deficit_goal)))

        self.reminder_time = QtWidgets.QTimeEdit()
        reminder = meta.get("reminder_time")
        qtime = QtCore.QTime.fromString(reminder, "HH:mm") if reminder else QtCore.QTime(8, 0)
        self.reminder_time.setTime(qtime)

        self.smtp_host = QtWidgets.QLineEdit(meta.get("email_smtp_host", self.config.email.smtp_host or ""))
        self.smtp_port = QtWidgets.QSpinBox()
        self.smtp_port.setRange(1, 65535)
        self.smtp_port.setValue(int(meta.get("email_smtp_port", self.config.email.smtp_port)))
        self.smtp_user = QtWidgets.QLineEdit(meta.get("email_username", self.config.email.username or ""))
        self.smtp_pass = QtWidgets.QLineEdit(meta.get("email_password", self.config.email.password or ""))
        self.smtp_pass.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.smtp_sender = QtWidgets.QLineEdit(meta.get("email_sender", self.config.email.sender or ""))
        self.smtp_recipient = QtWidgets.QLineEdit(meta.get("email_recipient", self.config.email.recipient or ""))

        self.openai_key = QtWidgets.QLineEdit(meta.get("openai_api_key", self.config.openai_api_key or ""))
        self.nutrition_key = QtWidgets.QLineEdit(meta.get("nutrition_api_key", self.config.nutrition_api_key or ""))

        self.save_button = QtWidgets.QPushButton("Save settings")
        self.save_button.clicked.connect(self._handle_save)

        layout.addRow("Target calories", self.target_spin)
        layout.addRow("Deficit goal", self.deficit_spin)
        layout.addRow("Reminder time", self.reminder_time)
        layout.addRow(QtWidgets.QLabel("SMTP host"), self.smtp_host)
        layout.addRow("SMTP port", self.smtp_port)
        layout.addRow("SMTP user", self.smtp_user)
        layout.addRow("SMTP password", self.smtp_pass)
        layout.addRow("Sender email", self.smtp_sender)
        layout.addRow("Recipient email", self.smtp_recipient)
        layout.addRow("OpenAI API key", self.openai_key)
        layout.addRow("Nutrition API key", self.nutrition_key)
        layout.addRow(self.save_button)

    def _handle_save(self) -> None:
        payload = {
            "target_calories": str(self.target_spin.value()),
            "deficit_goal": str(self.deficit_spin.value()),
            "reminder_time": self.reminder_time.time().toString("HH:mm"),
            "email_smtp_host": self.smtp_host.text(),
            "email_smtp_port": str(self.smtp_port.value()),
            "email_username": self.smtp_user.text(),
            "email_password": self.smtp_pass.text(),
            "email_sender": self.smtp_sender.text(),
            "email_recipient": self.smtp_recipient.text(),
            "openai_api_key": self.openai_key.text(),
            "nutrition_api_key": self.nutrition_key.text(),
        }
        self.repo.set_meta_bulk(payload)
        QtWidgets.QMessageBox.information(self, "Saved", "Settings updated.")
        self.settingsSaved.emit(payload)


# ----------------------------------------------------------------------
def launch_app():
    from ..config import load_config
    from ..database import AppRepository

    config = load_config()
    repo = AppRepository(config.db_path)
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow(config, repo)
    window.show()
    app.exec()
