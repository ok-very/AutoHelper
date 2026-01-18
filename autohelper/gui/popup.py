import os
import threading
import sys
import colorsys
import time
import colorsys
import threading

# Set environment to allow GUI execution
os.environ['QT_API'] = 'pyside6'

# Lazy Imports
QApplication = None
QWidget = None
QVBoxLayout = None
QHBoxLayout = None
QLabel = None
QPushButton = None
QPlainTextEdit = None
QLineEdit = None
QProgressBar = None
QFileDialog = None
QThread = None
Signal = None
Qt = None
QTimer = None
QScreen = None
QColor = None
QTabWidget = None
QListWidget = None
QListWidgetItem = None
QComboBox = None
QMessageBox = None
QFrame = None
QScrollArea = None
QCheckBox = None
QSpinBox = None

QMenu = None
QSystemTrayIcon = None
QAction = None
QStyle = None
QIcon = None
QEvent = None

def _ensure_qt_imported():
    """Import PySide6 modules on demand."""
    global QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit, QLineEdit, QProgressBar, QFileDialog, QThread, Signal, Qt, QTimer, QScreen, QColor, QSystemTrayIcon, QMenu, QAction, QStyle, QIcon, QEvent, QTabWidget, QListWidget, QListWidgetItem, QComboBox, QMessageBox, QFrame, QScrollArea, QCheckBox, QSpinBox
    if QApplication is not None:
        return True

    try:
        from PySide6.QtWidgets import (
            QApplication as _QApplication, QWidget as _QWidget,
            QVBoxLayout as _QVBoxLayout, QHBoxLayout as _QHBoxLayout,
            QLabel as _QLabel, QPushButton as _QPushButton,
            QPlainTextEdit as _QPlainTextEdit, QLineEdit as _QLineEdit,
            QProgressBar as _QProgressBar, QFileDialog as _QFileDialog,
            QSystemTrayIcon as _QSystemTrayIcon, QMenu as _QMenu, QStyle as _QStyle,
            QTabWidget as _QTabWidget, QListWidget as _QListWidget,
            QListWidgetItem as _QListWidgetItem, QComboBox as _QComboBox,
            QMessageBox as _QMessageBox, QFrame as _QFrame,
            QScrollArea as _QScrollArea, QCheckBox as _QCheckBox, QSpinBox as _QSpinBox
        )
        from PySide6.QtCore import QThread as _QThread, Signal as _Signal, Qt as _Qt, QTimer as _QTimer, QEvent as _QEvent
        from PySide6.QtGui import QScreen as _QScreen, QColor as _QColor, QAction as _QAction, QIcon as _QIcon

        # Assign to module-level globals
        QApplication = _QApplication
        QWidget = _QWidget
        QVBoxLayout = _QVBoxLayout
        QHBoxLayout = _QHBoxLayout
        QLabel = _QLabel
        QPushButton = _QPushButton
        QPlainTextEdit = _QPlainTextEdit
        QLineEdit = _QLineEdit
        QProgressBar = _QProgressBar
        QFileDialog = _QFileDialog
        QSystemTrayIcon = _QSystemTrayIcon
        QMenu = _QMenu
        QStyle = _QStyle
        QTabWidget = _QTabWidget
        QListWidget = _QListWidget
        QListWidgetItem = _QListWidgetItem
        QComboBox = _QComboBox
        QMessageBox = _QMessageBox
        QFrame = _QFrame
        QScrollArea = _QScrollArea
        QCheckBox = _QCheckBox
        QSpinBox = _QSpinBox
        QThread = _QThread
        Signal = _Signal
        Qt = _Qt
        QTimer = _QTimer
        QEvent = _QEvent
        QScreen = _QScreen
        QColor = _QColor
        QAction = _QAction
        QIcon = _QIcon

        return True
    except ImportError:
        print("Warning: PySide6 not installed. install with `pip install PySide6`")
        return False

# --- WORKER THREAD ---

class WorkerThread(object): 
    # Placeholder for safe class creation before import
    pass

def get_worker_class():
    if not _ensure_qt_imported(): return object
    
    class Worker(QThread):
        finished = Signal(bool, str) # success, message

        def __init__(self, func, parent=None):
            super().__init__(parent)
            self.func = func

        def run(self):
            try:
                # Artificial delay for UX visibility
                time.sleep(0.5)
                self.func()
                time.sleep(0.5)
                self.finished.emit(True, "Done")
            except Exception as e:
                self.finished.emit(False, str(e))
    return Worker

# --- MAIN WINDOW ---

class ConfigWindow(object):
    pass

def get_window_class():
    if not _ensure_qt_imported(): return object

    Worker = get_worker_class()

    class ConfigWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("AutoHelper Service")
            self.resize(300, 500)
            
            # --- STYLING ---
            # Apply Material Theme (Light)
            from qt_material import apply_stylesheet
            try:
                app = QApplication.instance()
                apply_stylesheet(app, theme='light_blue.xml')
            except Exception as e:
                print(f"Theme warning: {e}")

            # Technical / Monospace Styling overrides
            self.setStyleSheet(self.styleSheet() + """
                ConfigWindow {
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 11px;
                }
                QLabel {
                    font-family: 'Consolas', 'Monaco', monospace;
                }
                QLabel#HEADER {
                    font-weight: bold;
                    font-size: 12px;
                }
                QLabel#STAT_KEY {
                    color: #546e7a;
                }
                QLabel#STAT_VAL {
                    font-weight: bold;
                    color: #263238;
                }
                QPushButton {
                    text-transform: uppercase;
                    font-weight: bold;
                    border-radius: 2px;
                }
                QTabWidget::pane {
                    border: 1px solid #cfd8dc;
                    top: -1px; 
                }
                QTabBar::tab {
                    font-family: 'Segoe UI', sans-serif; /* Keep tabs readable */
                    font-size: 11px;
                    padding: 6px 10px;
                }
                QListWidget {
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 10px;
                }
            """)
            
            # Frameless & Top
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
            
            # Data
            from autohelper.config.store import ConfigStore
            self.config_store = ConfigStore()
            self.current_config = self.config_store.load()
            
            # Layout
            self.layout_ui()
            
            # Reposition
            self.align_to_tray()

        def event(self, event):
            if event.type() == QEvent.WindowDeactivate:
                self.hide()
            return super().event(event)
            
        def layout_ui(self):
            main = QVBoxLayout()
            main.setContentsMargins(0,0,0,0)
            main.setSpacing(0)
            
            # --- HEADER ---
            header_frame = QFrame()
            header_frame.setStyleSheet("background-color: #e3f2fd; border-bottom: 1px solid #b0bec5;")
            header_layout = QHBoxLayout(header_frame)
            header_layout.setContentsMargins(10, 8, 10, 8)
            
            self.status_dot = QLabel("●")
            self.status_dot.setStyleSheet("color: #4caf50; font-size: 14px;") # Green
            
            lbl_title = QLabel("AutoHelper Service")
            lbl_title.setObjectName("HEADER")
            
            btn_close = QPushButton("×")
            btn_close.setFixedSize(20, 20)
            btn_close.setFlat(True)
            btn_close.clicked.connect(self.hide)
            
            header_layout.addWidget(self.status_dot)
            header_layout.addWidget(lbl_title)
            header_layout.addStretch()
            header_layout.addWidget(btn_close)
            
            main.addWidget(header_frame)
            
            # --- TABS ---
            self.tabs = QTabWidget()
            
            # Tab 1: Dashboard
            self.tab_dashboard = QWidget()
            self.setup_dashboard_tab()
            self.tabs.addTab(self.tab_dashboard, "Status")
            
            # Tab 2: Roots
            self.tab_roots = QWidget()
            self.setup_roots_tab()
            self.tabs.addTab(self.tab_roots, "Roots")
            
            # Tab 3: Mail
            self.tab_mail = QWidget()
            self.setup_mail_tab()
            self.tabs.addTab(self.tab_mail, "Mail")
            
            # Tab 4: Advanced
            self.tab_advanced = QWidget()
            self.setup_advanced_tab()
            self.tabs.addTab(self.tab_advanced, "Adv.")
            
            main.addWidget(self.tabs)
            
            # --- FOOTER ---
            footer_frame = QFrame()
            footer_frame.setStyleSheet("background-color: #f5f5f5; border-top: 1px solid #e0e0e0;")
            footer_layout = QHBoxLayout(footer_frame)
            footer_layout.setContentsMargins(10, 8, 10, 8)
            
            self.btn_save = QPushButton("Save & Restart")
            self.btn_save.setEnabled(False) # Enable on change
            self.btn_save.clicked.connect(self.save_config)
            
            footer_layout.addWidget(self.btn_save)
            main.addWidget(footer_frame)
            
            self.setLayout(main)

        def setup_dashboard_tab(self):
            layout = QVBoxLayout(self.tab_dashboard)
            layout.setContentsMargins(15, 15, 15, 15)
            layout.setSpacing(15)
            
            # Metrics
            metrics = QFrame()
            metrics.setStyleSheet("background: white; border: 1px solid #eceff1; border-radius: 4px;")
            m_layout = QVBoxLayout(metrics)
            
            def add_stat(key, val):
                row = QHBoxLayout()
                k = QLabel(key)
                k.setObjectName("STAT_KEY")
                v = QLabel(val)
                v.setObjectName("STAT_VAL")
                row.addWidget(k)
                row.addStretch()
                row.addWidget(v)
                m_layout.addLayout(row)
                return v
                
            from autohelper.config import get_settings
            s = get_settings()
            
            add_stat("Service Port:", str(s.port))
            self.lbl_db_stat = add_stat("Database:", "Connected")
            self.lbl_idx_stat = add_stat("Indexed Files:", "...")
            
            layout.addWidget(metrics)
            
            # Actions
            layout.addWidget(QLabel("Index Operations"))
            
            btn_scan = QPushButton("Incremental Rescan")
            btn_scan.clicked.connect(self.start_scan)
            layout.addWidget(btn_scan)
            
            btn_rebuild = QPushButton("Full Ingestion (Rebuild)")
            btn_rebuild.setStyleSheet("color: #d32f2f;") # Red warning text
            btn_rebuild.clicked.connect(self.confirm_rebuild)
            layout.addWidget(btn_rebuild)
            
            self.progress = QProgressBar()
            self.progress.setVisible(False)
            self.progress.setFixedHeight(4)
            layout.addWidget(self.progress)
            
            self.lbl_op_status = QLabel("Ready")
            self.lbl_op_status.setAlignment(Qt.AlignCenter)
            self.lbl_op_status.setStyleSheet("color: #90a4ae;")
            layout.addWidget(self.lbl_op_status)
            
            layout.addStretch()
            
            # Update Stats immediately
            self.refresh_stats()

        def setup_mail_tab(self):
            layout = QVBoxLayout(self.tab_mail)
            layout.setContentsMargins(15, 15, 15, 15)
            layout.setSpacing(10)
            
            # 1. Status Section
            status_grp = QFrame()
            status_grp.setStyleSheet("background: white; border: 1px solid #eceff1; border-radius: 4px;")
            s_layout = QVBoxLayout(status_grp)
            
            self.chk_mail_enabled = QCheckBox("Enable Mail Polling")
            self.chk_mail_enabled.setChecked(self.current_config.get("mail_enabled", False))
            s_layout.addWidget(self.chk_mail_enabled)
            
            row_int = QHBoxLayout()
            row_int.addWidget(QLabel("Poll Interval (s):"))
            self.spin_mail_interval = QSpinBox()
            self.spin_mail_interval.setRange(5, 3600)
            self.spin_mail_interval.setValue(self.current_config.get("mail_poll_interval", 30))
            row_int.addWidget(self.spin_mail_interval)
            s_layout.addLayout(row_int)
            
            layout.addWidget(status_grp)
            
            # 2. AutoArt Connection Section
            context_grp = QFrame()
            context_grp.setStyleSheet("background: white; border: 1px solid #eceff1; border-radius: 4px;")
            c_layout = QVBoxLayout(context_grp)
            
            c_layout.addWidget(QLabel("AutoArt Connection"))
            c_layout.addWidget(QLabel("Connect to AutoArt to access Monday.com data", styleSheet="color: #78909c; font-size: 11px;"))
            
            # Show current connection status
            session_id = self.current_config.get("autoart_session_id", "")
            if session_id:
                self.lbl_context_status = QLabel("✓ Connected to AutoArt")
                self.lbl_context_status.setStyleSheet("color: #4caf50;")
            else:
                self.lbl_context_status = QLabel("Not connected")
                self.lbl_context_status.setStyleSheet("color: #90a4ae; font-style: italic;")
            c_layout.addWidget(self.lbl_context_status)
            
            # Pairing code input
            row_code = QHBoxLayout()
            row_code.addWidget(QLabel("Pairing Code:"))
            self.txt_pairing_code = QLineEdit()
            self.txt_pairing_code.setPlaceholderText("Enter 6-digit code from AutoArt...")
            self.txt_pairing_code.setMaxLength(6)
            row_code.addWidget(self.txt_pairing_code)
            c_layout.addLayout(row_code)
            
            btn_pair = QPushButton("Connect")
            btn_pair.clicked.connect(self.pair_with_autoart)
            c_layout.addWidget(btn_pair)
            
            layout.addWidget(context_grp)
            
            # 3. Ingestion Section
            ingest_grp = QFrame()
            ingest_grp.setStyleSheet("background: white; border: 1px solid #eceff1; border-radius: 4px;")
            i_layout = QVBoxLayout(ingest_grp)
            i_layout.addWidget(QLabel("Manual Ingestion"))
            
            btn_ingest = QPushButton("Ingest PST/OST...")
            btn_ingest.clicked.connect(self.ingest_pst_dialog)
            i_layout.addWidget(btn_ingest)
            
            self.lbl_ingest_status = QLabel("Ready")
            self.lbl_ingest_status.setStyleSheet("color: #90a4ae; font-style: italic;")
            i_layout.addWidget(self.lbl_ingest_status)
            
            layout.addWidget(ingest_grp)
            layout.addStretch()
            
            # Connect change signals to enable save
            self.chk_mail_enabled.stateChanged.connect(lambda: self.btn_save.setEnabled(True))
            self.spin_mail_interval.valueChanged.connect(lambda: self.btn_save.setEnabled(True))
        
        def pair_with_autoart(self):
            """Pair with AutoArt using the 6-digit code."""
            code = self.txt_pairing_code.text().strip()
            if not code or len(code) != 6:
                self.lbl_context_status.setText("Enter 6-digit code")
                self.lbl_context_status.setStyleSheet("color: #ffa000;")
                return
            
            self.lbl_context_status.setText("Pairing...")
            self.lbl_context_status.setStyleSheet("color: #2196f3;")
            QApplication.processEvents()
            
            try:
                from autohelper.modules.context.autoart import AutoArtClient
                from autohelper.config.settings import get_settings
                
                settings = get_settings()
                client = AutoArtClient(api_url=settings.autoart_api_url)
                session_id = client.pair_with_code(code)
                
                if session_id:
                    # Save session ID
                    self.current_config["autoart_session_id"] = session_id
                    self.lbl_context_status.setText("✓ Connected to AutoArt")
                    self.lbl_context_status.setStyleSheet("color: #4caf50;")
                    self.txt_pairing_code.clear()
                    self.btn_save.setEnabled(True)  # Enable save to persist session
                else:
                    self.lbl_context_status.setText("✗ Invalid or expired code")
                    self.lbl_context_status.setStyleSheet("color: #d32f2f;")
            except Exception as e:
                self.lbl_context_status.setText(f"✗ Error: {str(e)[:30]}")
                self.lbl_context_status.setStyleSheet("color: #d32f2f;")

        def ingest_pst_dialog(self):
            path, _ = QFileDialog.getOpenFileName(self, "Select Outlook Data File", "", "Outlook Files (*.pst *.ost)")
            if path:
                self.start_ingestion(path)

        def start_ingestion(self, path):
             self.lbl_ingest_status.setText(f"Ingesting {os.path.basename(path)}...")
             
             self.ingest_result = None
             def _wrapper():
                 # We can't import at top level if Qt not guaranteed, but here is fine
                 from autohelper.modules.mail import MailService
                 self.ingest_result = MailService().ingest_pst(path)
                 
             self.worker = Worker(_wrapper)
             self.worker.finished.connect(lambda s, m: self.on_ingest_finished(s, m))
             self.worker.start()

        def on_ingest_finished(self, success, msg):
            if success and self.ingest_result:
                res = self.ingest_result
                if res.get("success"):
                     self.lbl_ingest_status.setText(f"Done. Processed {res.get('count')} emails.")
                else:
                     self.lbl_ingest_status.setText(f"Error: {res.get('error')}")
            else:
                self.lbl_ingest_status.setText(f"Error: {msg}")

        def setup_roots_tab(self):
            layout = QVBoxLayout(self.tab_roots)
            layout.setContentsMargins(10, 10, 10, 10)
            
            info = QLabel("⚠ Only checked paths are indexed.")
            info.setStyleSheet("color: #ffa000; font-style: italic;")
            layout.addWidget(info)
            
            self.list_roots = QListWidget()
            self.list_roots.setSelectionMode(QListWidget.NoSelection) # Use checkboxes
            
            layout.addWidget(self.list_roots)
            
            # Populate
            for root in self.current_config.get("allowed_roots", []):
                item = QListWidgetItem(root)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                self.list_roots.addItem(item)
                
            btns = QHBoxLayout()
            btn_add = QPushButton("+ Add Path")
            btn_add.clicked.connect(self.add_root)
            
            btn_rem = QPushButton("- Remove Unchecked")
            btn_rem.clicked.connect(self.remove_unchecked_roots)
            
            btns.addWidget(btn_add)
            btns.addWidget(btn_rem)
            layout.addLayout(btns)
            
        def setup_advanced_tab(self):
            layout = QVBoxLayout(self.tab_advanced)
            layout.setContentsMargins(15, 15, 15, 15)
            
            from autohelper.config import get_settings
            s = get_settings()
            
            def add_row(key, val):
                l = QLabel(key)
                l.setStyleSheet("color: #78909c; font-weight: bold;")
                layout.addWidget(l)
                v = QLineEdit(str(val))
                v.setReadOnly(True) # Env vars are read only here
                v.setStyleSheet("background: #fcfcfc; color: #546e7a;")
                layout.addWidget(v)
                
            add_row("Host", s.host)
            add_row("CORS Origins", ",".join(s.cors_origins))
            add_row("DB Path", s.db_path)
            
            layout.addStretch()

        def refresh_stats(self):
            """Refresh database statistics synchronously (fast for local SQLite)."""
            def _check():
                try:
                    from autohelper.db import get_db
                    db = get_db()
                    count = db.execute("SELECT count(*) FROM files").fetchone()[0]
                    return True, count
                except Exception:
                    return False, 0

            success, count = _check()
            if success:
                self.lbl_db_stat.setText("Connected")
                self.lbl_db_stat.setStyleSheet("color: #263238;")
                self.lbl_idx_stat.setText(str(count))
            else:
                self.lbl_db_stat.setText("Error")
                self.lbl_db_stat.setStyleSheet("color: #d32f2f;")


        def add_root(self):
            folder = QFileDialog.getExistingDirectory(self, "Select Root Path")
            if folder:
                # Check duplicates
                for i in range(self.list_roots.count()):
                    if self.list_roots.item(i).text() == folder:
                        return
                
                item = QListWidgetItem(folder)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                self.list_roots.addItem(item)
                self.btn_save.setEnabled(True)

        def remove_unchecked_roots(self):
            for i in range(self.list_roots.count() - 1, -1, -1):
                if self.list_roots.item(i).checkState() == Qt.Unchecked:
                    self.list_roots.takeItem(i)
            self.btn_save.setEnabled(True)
            
        def save_config(self):
            # Gather Roots
            valid_roots = []
            for i in range(self.list_roots.count()):
                item = self.list_roots.item(i)
                if item.checkState() == Qt.Checked:
                    valid_roots.append(item.text())

            # Save - preserve autoart_session_id if previously set via pairing
            new_config = {
                "allowed_roots": valid_roots,
                "excludes": self.current_config.get("excludes", []),
                "mail_enabled": self.chk_mail_enabled.isChecked(),
                "mail_poll_interval": self.spin_mail_interval.value(),
                "autoart_session_id": self.current_config.get("autoart_session_id", ""),
            }
            try:
                self.config_store.save(new_config)
                
                # Feedback
                self.btn_save.setText("Saved (Restart Required)")
                self.btn_save.setEnabled(False)
                
                # We can't easily auto-restart the uvicorn process from here if running as threaded
                # API check: Can we signal re-init?
                from autohelper.config.settings import reset_settings
                reset_settings()
                
                # Reinitialize context service with new token
                try:
                    from autohelper.modules.context.service import get_context_service
                    ctx_svc = get_context_service()
                    ctx_svc.reinit_clients()
                    # Trigger a background refresh
                    ctx_svc.refresh()
                except Exception as e:
                    print(f"Context service reinit warning: {e}")
                
                # Toggle mail service based on new config
                from autohelper.modules.mail import MailService
                from autohelper.config import get_settings
                mail_svc = MailService()
                # Reload settings in the service
                mail_svc.settings = get_settings()
                if new_config["mail_enabled"]:
                    mail_svc.start()
                else:
                    mail_svc.stop()
                
            except Exception as e:
                QMessageBox.critical(self, "Save Error", str(e))

        def start_scan(self):
            self.toggle_busy(True)
            self.lbl_op_status.setText("Scanning...")
            
            def _scan():
                from autohelper.modules.index.service import IndexService
                try:
                    IndexService().rescan()
                except Exception as e:
                    raise e
            
            self.worker = Worker(_scan)
            self.worker.finished.connect(self.on_work_finished)
            self.worker.start()

        def confirm_rebuild(self):
            reply = QMessageBox.question(self, "Confirm Rebuild", 
                                       "Full rebuild will wipe the index and re-scan all files.\nThis may take time. Continue?",
                                       QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.start_rebuild()

        def start_rebuild(self):
            self.toggle_busy(True)
            self.lbl_op_status.setText("Rebuilding...")
            
            def _rebuild():
                from autohelper.modules.index.service import IndexService
                IndexService().rebuild_index()

            self.worker = Worker(_rebuild)
            self.worker.finished.connect(self.on_work_finished)
            self.worker.start()

        def on_work_finished(self, success, msg):
            self.toggle_busy(False)
            if success:
                self.lbl_op_status.setText(msg)
                self.refresh_stats()
            else:
                self.lbl_op_status.setText("Error!")
                QMessageBox.warning(self, "Operation Failed", msg)

        def toggle_busy(self, busy):
            self.progress.setVisible(busy)
            if busy:
                self.progress.setRange(0, 0) # Indeterminate
            else:
                self.progress.setRange(0, 100)

        # ... (Keep existing methods like align_to_tray, update_rainbow if needed, etc)
        # But we previously replaced ConfigWindow. align_to_tray was a method of ConfigWindow.
        # We need to include align_to_tray and move_to_tray_area here as well.
        
        def align_to_tray(self):
            """Position window relative to tray icon and taskbar."""
            target_rect = None
            if hasattr(self, 'tray') and self.tray:
                 target_rect = get_tray_icon_rect(self.tray)
            
            self.move_to_tray_area(target_rect)

        def move_to_tray_area(self, tray_rect):
            """Move window to best position relative to the tray rect."""
            if not tray_rect:
                # Fallback to Cursor
                cursor_pos = self.cursor().pos()
                x = cursor_pos.x() - self.width() // 2
                y = cursor_pos.y() - self.height() - 10
                self.move(x, y)
                return

            taskbar_edge, taskbar_rect = get_taskbar_info()
            
            # Default Center-X
            x = tray_rect.center().x() - (self.width() // 2)
            y = 0
            
            margin = 10
            
            if taskbar_edge == Qt.BottomEdge:
                y = tray_rect.top() - self.height() - margin
            elif taskbar_edge == Qt.TopEdge:
                y = tray_rect.bottom() + margin
            elif taskbar_edge == Qt.LeftEdge:
                x = tray_rect.right() + margin
                y = tray_rect.center().y() - (self.height() // 2)
            elif taskbar_edge == Qt.RightEdge:
                x = tray_rect.left() - self.width() - margin
                y = tray_rect.center().y() - (self.height() // 2)
                
            # Screen Boundary Checks
            screen = QApplication.screenAt(tray_rect.center())
            if not screen: screen = QApplication.primaryScreen()
            geo = screen.availableGeometry()
            
            # Clamp X
            if x < geo.left() + 5: x = geo.left() + 5
            if x + self.width() > geo.right() - 5: x = geo.right() - self.width() - 5
            
            # Clamp Y
            if y < geo.top() + 5: y = geo.top() + 5
            if y + self.height() > geo.bottom() - 5: y = geo.bottom() - self.height() - 5
            
            self.move(x, y)

    return ConfigWindow

# --- TRAY ICON ---

class SystemTray(object):
    pass

def get_tray_class():
    if not _ensure_qt_imported(): return object
    
    from PySide6.QtWidgets import QSystemTrayIcon, QMenu
    from PySide6.QtGui import QAction, QIcon

    class AutoHelperTray(QSystemTrayIcon):
        def __init__(self, app, window):
            super().__init__()
            self.app = app
            self.window = window
            
            self.setToolTip("AutoHelper Indexer")
            
            # Menu
            self.menu = QMenu()
            
            action_show = QAction("Open Settings", self)
            action_show.triggered.connect(self.show_window)
            self.menu.addAction(action_show)
            
            self.menu.addSeparator()
            
            action_quit = QAction("Quit", self)
            action_quit.triggered.connect(self.quit_app)
            self.menu.addAction(action_quit)
            
            self.setContextMenu(self.menu)
            
            # Interaction
            self.activated.connect(self.on_activated)

        def show_window(self):
            self.window.show()
            self.window.raise_()
            self.window.activateWindow()

        def on_activated(self, reason):
            if reason == QSystemTrayIcon.Trigger:
                if self.window.isVisible():
                    self.window.hide()
                else:
                    # Refresh position before showing
                    self.position_window()
                    self.window.show()
                    self.window.raise_()
                    self.window.activateWindow()

        def position_window(self):
            rect = get_tray_icon_rect(self)
            if rect:
                self.window.move_to_tray_area(rect)
            else:
                 # Fallback to cursor
                from PySide6.QtGui import QCursor
                self.window.move_to_tray_area(None)


        def quit_app(self):
            self.hide()
            self.app.quit()

    return AutoHelperTray

def launch_config_popup():
    """Launch the PySide6 configuration popup with System Tray."""
    if not _ensure_qt_imported():
        return

    # Check if we're creating a new app or reusing existing
    existing_app = QApplication.instance()
    app = existing_app or QApplication(sys.argv)

    if not existing_app:
        # Prevent app from exiting when last window closes (we want it in tray)
        app.setQuitOnLastWindowClosed(False)

    Window = get_window_class()
    window = Window()

    # Setup Tray
    Tray = get_tray_class()
    tray = Tray(app, window)
    window.tray = tray

    # Use Smiley Icon
    icon = create_smiley_icon()
    window.setWindowIcon(icon)
    tray.setIcon(icon)
    tray.show()

    # Launch logic: if just --popup, show window immediately
    # And position it
    window.align_to_tray()
    window.show()

    # Run event loop - wrap in sys.exit only if we created the app
    if not existing_app:
        sys.exit(app.exec())
    else:
        app.exec()


# --- WINDOWS TRAY GEOMETRY & ALIGNMENT ---

def get_tray_icon_rect(tray_instance):
    """
    Get the screen rectangle of the tray icon.
    Priority:
    1. QSystemTrayIcon.geometry() (if available/valid)
    2. Win32 Toolbar Scan (Reliable fallback)
    3. None (Fail)
    """
    # 1. Try Qt Geometry (often valid after first click/activation)
    rect = tray_instance.geometry()
    if not rect.isEmpty() and rect.isValid():
        return rect
        
    # 2. Fallback to Win32 Scan
    scan_result = get_tray_location_win32(tray_instance.toolTip())
    if scan_result:
        # scan_result is (center_x, top_y) roughly. 
        # We need a Rect. We'll approximate size as 24x24 standard.
        cx, ty = scan_result
        from PySide6.QtCore import QRect
        # Assume square icon, centered at cx
        width = 24
        height = 24
        return QRect(cx - width//2, ty, width, height)
        
    return None

def get_taskbar_info():
    """
    Determine Taskbar position and size.
    Returns: (edge, rect) where edge is Qt.Edge (Top, Bottom, Left, Right)
    """
    from PySide6.QtGui import QGuiApplication
    
    # We can infer taskbar from the primary screen's available geometry vs full geometry
    screen = QGuiApplication.primaryScreen()
    full_geo = screen.geometry()
    avail_geo = screen.availableGeometry()
    
    # Compare
    if avail_geo.height() < full_geo.height():
        # Top or Bottom
        if avail_geo.top() > full_geo.top():
            return Qt.TopEdge, full_geo.adjusted(0, 0, 0, -avail_geo.height())
        else:
            return Qt.BottomEdge, full_geo.adjusted(0, avail_geo.height(), 0, 0)
            
    elif avail_geo.width() < full_geo.width():
        # Left or Right
        if avail_geo.left() > full_geo.left():
            return Qt.LeftEdge, full_geo.adjusted(0, 0, -avail_geo.width(), 0)
        else:
            return Qt.RightEdge, full_geo.adjusted(avail_geo.width(), 0, 0, 0)
            
    # Default to Bottom if same (auto-hide?)
    return Qt.BottomEdge, QGuiApplication.primaryScreen().geometry()

def win32process_get_pid(hwnd):
    import ctypes
    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value

def read_process_memory(h_process, lp_base_address, lp_buffer, n_size):
    import ctypes
    bytes_read = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.ReadProcessMemory(
        h_process, 
        lp_base_address, 
        lp_buffer, 
        n_size, 
        ctypes.byref(bytes_read)
    )

def get_tray_location_win32(tooltip_text):
    """
    Finds the screen coordinates of the system tray icon with the matching tooltip.
    Returns (center_x, top_y) or None.
    """
    try:
        import win32gui
        import win32con
        import commctrl
        import ctypes
        from ctypes import wintypes
        
        # High-DPI awareness
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
            
        # Define TBBUTTON structure locally
        class TBBUTTON(ctypes.Structure):
            _fields_ = [
                ('iBitmap', ctypes.c_int),
                ('idCommand', ctypes.c_int),
                ('fsState', ctypes.c_ubyte),
                ('fsStyle', ctypes.c_ubyte),
                ('bReserved', ctypes.c_byte * 2),
                ('dwData', ctypes.c_ulonglong),
                ('iString', ctypes.c_longlong),
            ]

        def find_toolbars():
            toolbars = []
            # 1. Main Tray
            h_tray = win32gui.FindWindow("Shell_TrayWnd", None)
            h_notify = win32gui.FindWindowEx(h_tray, 0, "TrayNotifyWnd", None)
            h_pager = win32gui.FindWindowEx(h_notify, 0, "SysPager", None)
            if h_pager:
                toolbars.append(win32gui.FindWindowEx(h_pager, 0, "ToolbarWindow32", None))
            
            # Simple fallback for some Windows versions
            toolbars.append(win32gui.FindWindowEx(h_notify, 0, "ToolbarWindow32", None))

            # 2. Overflow Tray / Hidden Icons via Chevron
            h_over = win32gui.FindWindow("NotifyIconOverflowWindow", None)
            if h_over:
                toolbars.append(win32gui.FindWindowEx(h_over, 0, "ToolbarWindow32", None))
                
            return [h for h in toolbars if h]

        target_toolbars = find_toolbars()
        
        for hwnd_tb in target_toolbars:
            count = win32gui.SendMessage(hwnd_tb, commctrl.TB_BUTTONCOUNT, 0, 0)
            if count <= 0: continue
            
            pid = win32process_get_pid(hwnd_tb)
            h_process = ctypes.windll.kernel32.OpenProcess(
                win32con.PROCESS_ALL_ACCESS, False, pid
            )
            if not h_process: continue
            
            try:
                for i in range(count):
                    # Buffer for TBBUTTON
                    lp_btn = ctypes.windll.kernel32.VirtualAllocEx(
                        h_process, None, ctypes.sizeof(TBBUTTON), win32con.MEM_COMMIT, win32con.PAGE_READWRITE
                    )
                    
                    # Get Button
                    win32gui.SendMessage(hwnd_tb, 0x0417, i, lp_btn) # TB_GETBUTTON
                    
                    button = TBBUTTON()
                    read_process_memory(h_process, lp_btn, ctypes.byref(button), ctypes.sizeof(button))
                    
                    # Get Text
                    txt_len = win32gui.SendMessage(hwnd_tb, 0x044B, button.idCommand, 0) # TB_GETBUTTONTEXTW length
                    if txt_len > 0:
                         # Allocate for text
                         # Note: txt_len is chars, need bytes (wchar = 2 bytes) + null
                         buf_size = (txt_len + 1) * 2
                         lp_txt = ctypes.windll.kernel32.VirtualAllocEx(
                             h_process, None, buf_size, win32con.MEM_COMMIT, win32con.PAGE_READWRITE
                         )
                         
                         win32gui.SendMessage(hwnd_tb, 0x044B, button.idCommand, lp_txt)
                         
                         local_txt = ctypes.create_unicode_buffer(txt_len + 1)
                         read_process_memory(h_process, lp_txt, ctypes.byref(local_txt), buf_size)
                         
                         text = local_txt.value
                         if tooltip_text in text:
                             # Found match! Get Rect.
                             lp_rect = ctypes.windll.kernel32.VirtualAllocEx(
                                 h_process, None, ctypes.sizeof(wintypes.RECT), win32con.MEM_COMMIT, win32con.PAGE_READWRITE
                             )
                             win32gui.SendMessage(hwnd_tb, 0x041D, i, lp_rect) # TB_GETITEMRECT
                             
                             rect = wintypes.RECT()
                             read_process_memory(h_process, lp_rect, ctypes.byref(rect), ctypes.sizeof(rect))
                             
                             # Map to Screen
                             p1 = win32gui.ClientToScreen(hwnd_tb, (rect.left, rect.top))
                             p2 = win32gui.ClientToScreen(hwnd_tb, (rect.right, rect.bottom))
                             
                             ctypes.windll.kernel32.VirtualFreeEx(h_process, lp_btn, 0, win32con.MEM_RELEASE)
                             ctypes.windll.kernel32.VirtualFreeEx(h_process, lp_txt, 0, win32con.MEM_RELEASE)
                             ctypes.windll.kernel32.VirtualFreeEx(h_process, lp_rect, 0, win32con.MEM_RELEASE)
                             
                             center_x = (p1[0] + p2[0]) // 2
                             top_y = p1[1] # Top of icon
                             return center_x, top_y

                         ctypes.windll.kernel32.VirtualFreeEx(h_process, lp_txt, 0, win32con.MEM_RELEASE)
                    
                    ctypes.windll.kernel32.VirtualFreeEx(h_process, lp_btn, 0, win32con.MEM_RELEASE)

            finally:
                ctypes.windll.kernel32.CloseHandle(h_process)
                
    except Exception as e:
        print(f"Tray API error: {e}")
        
    return None

def create_smiley_icon():
    """Draw a simple smiley face icon."""
    if not _ensure_qt_imported(): return None
    
    from PySide6.QtGui import QPixmap, QPainter, QPen, QBrush, QColor
    
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # Yellow Face
    painter.setBrush(QBrush(QColor("#FFCC00")))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(2, 2, size-4, size-4)
    
    # Original "Old Guy" Geometry
    # Eyes (Centers at 16,24 and 48,24)
    painter.setBrush(QBrush(Qt.black))
    painter.drawEllipse(12, 20, 8, 8) # Left (16-4, 24-4)
    painter.drawEllipse(44, 20, 8, 8) # Right (48-4, 24-4)
    
    # Simple Smile (Original Arc)
    # BBox from original: 20, 24, 44, 48 -> x=20, y=24, w=24, h=24
    pen = QPen(Qt.black)
    pen.setWidth(3)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    
    # Qt angles: 1/16th of a degree. Start 0 (3 o'clock), span -180 (clockwise to 9 o'clock)
    painter.drawArc(20, 24, 24, 24, 0 * 16, -180 * 16)
    
    painter.end()
    return QIcon(pixmap)
