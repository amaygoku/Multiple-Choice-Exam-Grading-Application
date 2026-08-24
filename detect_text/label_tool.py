import os
import sys
import csv
import json
import shutil
import re

# Dynamically import PySide6 or PyQt5
try:
    from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                                   QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                                   QFileDialog, QProgressBar, QGroupBox, QGridLayout,
                                   QDialog, QListWidget, QListWidgetItem, QInputDialog,
                                   QMessageBox, QProgressDialog)
    from PySide6.QtGui import QPixmap, QKeyEvent, QShortcut, QKeySequence, QImage, QPainter
    from PySide6.QtCore import Qt, Signal, QThread
    QT_LIB = "PySide6"
except ImportError:
    try:
        from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                                       QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                                       QFileDialog, QProgressBar, QGroupBox, QGridLayout,
                                       QDialog, QListWidget, QListWidgetItem, QInputDialog,
                                       QMessageBox, QProgressDialog)
        from PyQt5.QtGui import QPixmap, QKeySequence, QShortcut, QImage, QPainter
        from PyQt5.QtCore import Qt, pyqtSignal as Signal, QThread
        QT_LIB = "PyQt5"
    except ImportError:
        print("Please install PySide6 or PyQt5 to run this application: pip install PySide6")
        sys.exit(1)

# Helper config file path
CONFIG_FILE = "label_tool_config.json"

class OCRDataManager:
    def __init__(self):
        self.directory = ""
        self.image_files = []
        self.labels = {}
        self.csv_path = ""
        self.current_index = -1
        self.last_typed_label = ""

    def load_directory(self, dir_path):
        """Scans directory for images and loads labels.csv if present."""
        self.directory = dir_path
        self.csv_path = os.path.join(dir_path, "labels.csv")
        self.image_files = []
        self.labels = {}
        self.current_index = 0
        
        # Load image list
        valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp')
        try:
            for f in os.listdir(dir_path):
                if f.lower().endswith(valid_extensions):
                    # We keep original filenames
                    self.image_files.append(f)
        except Exception as e:
            print(f"Error scanning directory: {e}")
            return False

        # Natural sort or alphabetical sort
        self.image_files.sort()

        # Load CSV labels
        if os.path.exists(self.csv_path):
            try:
                with open(self.csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    # Skip header if it matches the format
                    header = next(reader, None)
                    if header and header != ["image_name", "label"]:
                        # If no header, process it as a data line
                        if len(header) >= 2:
                            self.labels[header[0]] = header[1]
                    for row in reader:
                        if len(row) >= 2:
                            self.labels[row[0]] = row[1]
            except Exception as e:
                print(f"Error loading CSV: {e}")

        # Scan filenames for labels (e.g. Bảo_1.jpg -> label: Bảo)
        # This acts as a fallback for files already exported/renamed or named manually
        for f in self.image_files:
            if f not in self.labels:
                name, _ = os.path.splitext(f)
                if "_" in name:
                    parts = name.rsplit("_", 1)
                    if len(parts) == 2 and parts[1].isdigit():
                        self.labels[f] = parts[0]

        return len(self.image_files) > 0

    def save_current_label(self, filename, label_text):
        """Saves current label to dictionary and updates the CSV."""
        label_text = label_text.strip()
        self.labels[filename] = label_text
        if label_text:
            self.last_typed_label = label_text
        self.save_csv()

    def save_csv(self):
        """Atomic write to labels.csv to prevent data loss."""
        if not self.directory:
            return
        temp_path = self.csv_path + ".tmp"
        try:
            with open(temp_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["image_name", "label"])
                for img in self.image_files:
                    lbl = self.labels.get(img, "")
                    if lbl:
                        writer.writerow([img, lbl])
            # Atomic replace
            if os.path.exists(self.csv_path):
                os.replace(temp_path, self.csv_path)
            else:
                os.rename(temp_path, self.csv_path)
        except Exception as e:
            print(f"Error saving CSV: {e}")

    def get_stats(self):
        """Returns labeling statistics."""
        total = len(self.image_files)
        labeled = sum(1 for img in self.image_files if self.labels.get(img, "").strip())
        unlabeled = total - labeled
        pct = (labeled / total * 100.0) if total > 0 else 0.0
        return {
            "total": total,
            "labeled": labeled,
            "unlabeled": unlabeled,
            "percentage": pct
        }


class ExportThread(QThread):
    progress = Signal(int, int) # current, total
    finished_export = Signal(int) # total_copied
    error_occurred = Signal(str)
    
    def __init__(self, directory, image_files, labels, export_dir_name="renamed_dataset"):
        super().__init__()
        self.directory = directory
        self.image_files = image_files
        self.labels = labels
        self.export_dir_name = export_dir_name
        
    def run(self):
        try:
            export_path = os.path.join(self.directory, self.export_dir_name)
            os.makedirs(export_path, exist_ok=True)
            
            # Scan existing files in export directory for counters
            counters = {}
            for filename in os.listdir(export_path):
                name, _ = os.path.splitext(filename)
                if "_" in name:
                    parts = name.rsplit("_", 1)
                    if len(parts) == 2 and parts[1].isdigit():
                        lbl = parts[0]
                        num = int(parts[1])
                        if lbl not in counters:
                            counters[lbl] = num
                        else:
                            counters[lbl] = max(counters[lbl], num)
            
            # Convert counters to next index (max + 1)
            for lbl in counters:
                counters[lbl] += 1
                
            # Filter files that have labels
            to_export = []
            for file in self.image_files:
                lbl = self.labels.get(file, "").strip()
                if lbl:
                    to_export.append((file, lbl))
                    
            total = len(to_export)
            copied = 0
            
            for file, lbl in to_export:
                ext = ".jpg"  # Force JPG format
                idx = counters.get(lbl, 1)
                
                # Double-check uniqueness
                target_name = f"{lbl}_{idx}{ext}"
                target_path = os.path.join(export_path, target_name)
                while os.path.exists(target_path):
                    idx += 1
                    target_name = f"{lbl}_{idx}{ext}"
                    target_path = os.path.join(export_path, target_name)
                
                counters[lbl] = idx + 1
                
                # Convert and save as JPG
                src = os.path.join(self.directory, file)
                image = QImage(src)
                if image.isNull():
                    raise Exception(f"Không thể đọc ảnh: {src}")
                
                # Flatten transparent images onto white background
                if image.hasAlphaChannel():
                    background = QImage(image.size(), QImage.Format_RGB32)
                    background.fill(Qt.white)
                    painter = QPainter(background)
                    painter.drawImage(0, 0, image)
                    painter.end()
                    success = background.save(target_path, "JPG", 95)
                else:
                    success = image.save(target_path, "JPG", 95)
                
                if not success:
                    raise Exception(f"Không thể chuyển đổi và lưu ảnh dạng JPG: {target_path}")
                
                copied += 1
                self.progress.emit(copied, total)
                
            self.finished_export.emit(copied)
        except Exception as e:
            self.error_occurred.emit(str(e))


class LabelLineEdit(QLineEdit):
    # Custom signals for keypresses we want to bubble up
    escape_pressed = Signal()
    up_pressed = Signal()
    tab_pressed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self.escape_pressed.emit()
            event.accept()
        elif key == Qt.Key_Up:
            self.up_pressed.emit()
            event.accept()
        elif key == Qt.Key_Tab:
            self.tab_pressed.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


class SearchDialog(QDialog):
    def __init__(self, filenames, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tìm kiếm ảnh")
        self.setMinimumSize(450, 350)
        self.filenames = filenames
        self.selected_filename = None
        
        layout = QVBoxLayout(self)
        
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Nhập tên file cần tìm (Không phân biệt hoa thường)...")
        layout.addWidget(self.search_input)
        
        self.list_widget = QListWidget(self)
        layout.addWidget(self.list_widget)
        
        self.search_input.textChanged.connect(self.filter_list)
        self.list_widget.itemDoubleClicked.connect(self.accept_selection)
        
        # Initial list
        self.filter_list("")
        self.search_input.setFocus()
        
    def filter_list(self, text):
        self.list_widget.clear()
        query = text.lower()
        for name in self.filenames:
            if query in name.lower():
                item = QListWidgetItem(name)
                self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            
    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self.accept_selection()
        elif key == Qt.Key_Down:
            self.list_widget.setFocus()
        elif key == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
            
    def accept_selection(self):
        item = self.list_widget.currentItem()
        if item:
            self.selected_filename = item.text()
            self.accept()


class OCRLabelingApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.data_manager = OCRDataManager()
        self.current_pixmap = None
        
        self.setWindowTitle("OCR Word-Level Labeling Tool")
        self.setMinimumSize(1000, 750)
        
        self.init_ui()
        self.load_settings()
        self.setup_shortcuts()

    def init_ui(self):
        # QSS Premium Dark Theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
            }
            QWidget {
                color: #cdd6f4;
                font-family: 'Segoe UI', 'Outfit', sans-serif;
                font-size: 13px;
            }
            QLabel {
                color: #cdd6f4;
            }
            QLabel#titleLabel {
                font-size: 20px;
                font-weight: bold;
                color: #cba6f7;
            }
            QLabel#imageLabel {
                background-color: #11111b;
                border: 2px solid #313244;
                border-radius: 8px;
            }
            QLabel#filenameLabel {
                font-size: 15px;
                font-weight: bold;
                color: #89b4fa;
            }
            QLabel#indexLabel {
                font-size: 13px;
                color: #a6adc8;
            }
            QLineEdit {
                background-color: #313244;
                color: #cdd6f4;
                border: 2px solid #45475a;
                border-radius: 6px;
                padding: 10px 15px;
                font-size: 18px;
            }
            QLineEdit:focus {
                border: 2px solid #cba6f7;
            }
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45475a;
                border: 1px solid #cba6f7;
            }
            QPushButton:pressed {
                background-color: #585b70;
            }
            QPushButton#exportButton {
                background-color: #a6e3a1;
                color: #11111b;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton#exportButton:hover {
                background-color: #b4befe;
            }
            QProgressBar {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                text-align: center;
                color: #cdd6f4;
                font-weight: bold;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #89b4fa;
                border-radius: 5px;
            }
            QGroupBox {
                border: 1px solid #313244;
                border-radius: 6px;
                margin-top: 15px;
                padding: 10px;
                font-weight: bold;
                color: #bac2de;
            }
        """)

        # Main Widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # ----------------- Top Section (Folder & Stats) -----------------
        top_layout = QHBoxLayout()
        
        self.btn_select_folder = QPushButton("Chọn Thư Mục")
        self.btn_select_folder.clicked.connect(self.select_folder)
        top_layout.addWidget(self.btn_select_folder)
        
        self.lbl_folder_path = QLabel("Chưa chọn thư mục...")
        self.lbl_folder_path.setMinimumWidth(300)
        self.lbl_folder_path.setStyleSheet("color: #a6adc8; font-style: italic;")
        top_layout.addWidget(self.lbl_folder_path)
        
        top_layout.addStretch()

        # Stats Labels
        self.lbl_stat_total = QLabel("Tổng: 0")
        self.lbl_stat_labeled = QLabel("Đã gán nhãn: 0")
        self.lbl_stat_unlabeled = QLabel("Chưa gán nhãn: 0")
        self.lbl_stat_pct = QLabel("Hoàn thành: 0%")
        
        self.lbl_stat_total.setStyleSheet("font-weight: bold;")
        self.lbl_stat_labeled.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        self.lbl_stat_unlabeled.setStyleSheet("color: #f38ba8; font-weight: bold;")
        self.lbl_stat_pct.setStyleSheet("color: #f9e2af; font-weight: bold;")

        top_layout.addWidget(self.lbl_stat_total)
        top_layout.addWidget(self.lbl_stat_labeled)
        top_layout.addWidget(self.lbl_stat_unlabeled)
        top_layout.addWidget(self.lbl_stat_pct)
        
        main_layout.addLayout(top_layout)

        # ----------------- Center Section (Image Display) -----------------
        self.image_label = QLabel("Vui lòng chọn thư mục chứa ảnh để bắt đầu gán nhãn.")
        self.image_label.setObjectName("imageLabel")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(400, 300)
        main_layout.addWidget(self.image_label, stretch=1)

        # Image Info
        info_layout = QHBoxLayout()
        self.lbl_filename = QLabel("")
        self.lbl_filename.setObjectName("filenameLabel")
        info_layout.addWidget(self.lbl_filename)
        
        info_layout.addStretch()
        
        self.lbl_index = QLabel("")
        self.lbl_index.setObjectName("indexLabel")
        info_layout.addWidget(self.lbl_index)
        
        main_layout.addLayout(info_layout)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%v/%m (%p%)")
        main_layout.addWidget(self.progress_bar)

        # ----------------- Input Section -----------------
        input_layout = QHBoxLayout()
        lbl_input_title = QLabel("Label OCR:")
        lbl_input_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #cba6f7;")
        input_layout.addWidget(lbl_input_title)
        
        self.label_input = LabelLineEdit()
        self.label_input.setPlaceholderText("Nhập nội dung text của ảnh rồi nhấn Enter...")
        self.label_input.returnPressed.connect(self.save_and_next)
        self.label_input.escape_pressed.connect(self.save_and_exit)
        self.label_input.up_pressed.connect(self.copy_prev_label)
        self.label_input.tab_pressed.connect(self.copy_last_typed_label)
        input_layout.addWidget(self.label_input)
        
        main_layout.addLayout(input_layout)

        # ----------------- Footer Section (Shortcuts & Export) -----------------
        footer_layout = QHBoxLayout()
        
        # Shortcuts Group
        shortcut_box = QGroupBox("Phím tắt & Hướng dẫn")
        shortcut_layout = QGridLayout(shortcut_box)
        shortcut_layout.setSpacing(8)
        
        shortcut_layout.addWidget(QLabel("<b>Enter:</b> Lưu & Ảnh tiếp theo"), 0, 0)
        shortcut_layout.addWidget(QLabel("<b>Alt + D / D (Unfocused):</b> Lưu & Ảnh tiếp theo"), 0, 1)
        shortcut_layout.addWidget(QLabel("<b>Alt + A / A (Unfocused):</b> Lưu & Ảnh trước đó"), 1, 0)
        shortcut_layout.addWidget(QLabel("<b>Mũi tên lên (Up):</b> Copy nhãn của ảnh trước"), 1, 1)
        shortcut_layout.addWidget(QLabel("<b>Tab:</b> Copy nhãn vừa nhập gần nhất"), 2, 0)
        shortcut_layout.addWidget(QLabel("<b>Ctrl + G:</b> Nhảy tới số thứ tự ảnh"), 2, 1)
        shortcut_layout.addWidget(QLabel("<b>Ctrl + F:</b> Tìm kiếm ảnh theo tên file"), 3, 0)
        shortcut_layout.addWidget(QLabel("<b>Esc:</b> Lưu & Thoát"), 3, 1)
        
        footer_layout.addWidget(shortcut_box, stretch=3)

        # Export Area
        export_layout = QVBoxLayout()
        export_layout.addStretch()
        self.btn_export = QPushButton("Export Rename Dataset")
        self.btn_export.setObjectName("exportButton")
        self.btn_export.clicked.connect(self.run_export)
        export_layout.addWidget(self.btn_export)
        export_layout.addStretch()
        
        footer_layout.addLayout(export_layout, stretch=1)
        
        main_layout.addLayout(footer_layout)

    def setup_shortcuts(self):
        """Prepares global key shortcuts using QShortcut."""
        # Alt+A / Alt+D for navigation (always active)
        self.shortcut_prev = QShortcut(QKeySequence("Alt+A"), self)
        self.shortcut_prev.activated.connect(self.save_and_prev)
        
        self.shortcut_next = QShortcut(QKeySequence("Alt+D"), self)
        self.shortcut_next.activated.connect(self.save_and_next)

        # Ctrl+G to jump to index
        self.shortcut_jump = QShortcut(QKeySequence("Ctrl+G"), self)
        self.shortcut_jump.activated.connect(self.open_jump_dialog)

        # Ctrl+F to search image
        self.shortcut_search = QShortcut(QKeySequence("Ctrl+F"), self)
        self.shortcut_search.activated.connect(self.open_search_dialog)

    def keyPressEvent(self, event):
        """Global key overrides when QLineEdit does NOT have focus."""
        if not self.label_input.hasFocus():
            key = event.key()
            if key == Qt.Key_A:
                self.save_and_prev()
                event.accept()
            elif key == Qt.Key_D or key in (Qt.Key_Return, Qt.Key_Enter):
                self.save_and_next()
                event.accept()
            elif key == Qt.Key_Escape:
                self.save_and_exit()
                event.accept()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        """Dynamically rescale current image when window size changes."""
        super().resizeEvent(event)
        self.update_image_display()

    # ----------------- Settings / Session management -----------------
    def load_settings(self):
        """Loads previous directory and position on launch."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                last_dir = config.get("last_directory", "")
                if last_dir and os.path.exists(last_dir):
                    self.load_folder(last_dir)
                    last_indices = config.get("last_indices", {})
                    idx = last_indices.get(last_dir, 0)
                    if 0 <= idx < len(self.data_manager.image_files):
                        self.jump_to_index(idx)
            except Exception as e:
                print(f"Error loading config: {e}")

    def save_settings(self):
        """Saves current directory and index on exit."""
        config = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception:
                pass
        
        if self.data_manager.directory:
            config["last_directory"] = self.data_manager.directory
            if "last_indices" not in config:
                config["last_indices"] = {}
            config["last_indices"][self.data_manager.directory] = self.data_manager.current_index
            
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    # ----------------- Label Operations & Navigation -----------------
    def select_folder(self):
        """Prompts user to select directory of images."""
        dir_path = QFileDialog.getExistingDirectory(self, "Chọn Thư Mục Ảnh")
        if dir_path:
            self.load_folder(dir_path)

    def load_folder(self, dir_path):
        """Triggers loading of directory."""
        has_images = self.data_manager.load_directory(dir_path)
        if has_images:
            self.lbl_folder_path.setText(dir_path)
            self.jump_to_index(0)
            self.label_input.setFocus()
        else:
            QMessageBox.warning(self, "Cảnh báo", "Thư mục không chứa ảnh hợp lệ (jpg, jpeg, png, bmp)!")

    def jump_to_index(self, idx):
        """Jumps to specified index, loading the image and label."""
        if not self.data_manager.image_files:
            return
        
        # Save current label if any before jumping
        self.save_current_label_state()

        self.data_manager.current_index = max(0, min(idx, len(self.data_manager.image_files) - 1))
        self.load_current_image()
        self.update_stats_display()
        self.label_input.setFocus()

    def load_current_image(self):
        """Renders the image and fills label input."""
        idx = self.data_manager.current_index
        filename = self.data_manager.image_files[idx]
        full_path = os.path.join(self.data_manager.directory, filename)

        self.lbl_filename.setText(filename)
        self.lbl_index.setText(f"[{idx + 1} / {len(self.data_manager.image_files)}]")

        # Display image
        self.current_pixmap = QPixmap(full_path)
        if self.current_pixmap.isNull():
            self.image_label.setText(f"Không thể đọc ảnh:\n{filename}")
        else:
            self.update_image_display()

        # Display old label if exists
        old_label = self.data_manager.labels.get(filename, "")
        self.label_input.setText(old_label)
        self.label_input.selectAll()

    def update_image_display(self):
        """Scales the current pixmap to match container size while keeping aspect ratio."""
        if self.current_pixmap and not self.current_pixmap.isNull():
            size = self.image_label.size()
            w = max(100, size.width() - 10)
            h = max(100, size.height() - 10)
            scaled = self.current_pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled)

    def save_current_label_state(self):
        """Saves current state from QLineEdit to data manager."""
        if not self.data_manager.image_files or self.data_manager.current_index < 0:
            return
        filename = self.data_manager.image_files[self.data_manager.current_index]
        label_text = self.label_input.text()
        self.data_manager.save_current_label(filename, label_text)

    def save_and_next(self):
        """Saves label and advances index."""
        if not self.data_manager.image_files:
            return
        self.save_current_label_state()
        if self.data_manager.current_index < len(self.data_manager.image_files) - 1:
            self.jump_to_index(self.data_manager.current_index + 1)
        else:
            self.update_stats_display()
            QMessageBox.information(self, "Thông tin", "Đã hoàn thành ảnh cuối cùng!")

    def save_and_prev(self):
        """Saves label and goes to previous index."""
        if not self.data_manager.image_files:
            return
        self.save_current_label_state()
        if self.data_manager.current_index > 0:
            self.jump_to_index(self.data_manager.current_index - 1)

    def save_and_exit(self):
        """Saves session and exits."""
        self.save_current_label_state()
        self.save_settings()
        self.close()

    # ----------------- Keyboard Helper Copy Shortcuts -----------------
    def copy_prev_label(self):
        """Copies the label of the previous image into current input."""
        idx = self.data_manager.current_index
        if idx > 0:
            prev_file = self.data_manager.image_files[idx - 1]
            prev_label = self.data_manager.labels.get(prev_file, "")
            self.label_input.setText(prev_label)
            self.label_input.selectAll()

    def copy_last_typed_label(self):
        """Copies the last non-empty label typed in this session."""
        last_lbl = self.data_manager.last_typed_label
        if last_lbl:
            self.label_input.setText(last_lbl)
            self.label_input.selectAll()

    # ----------------- Search & Jump Dialogs -----------------
    def open_jump_dialog(self):
        """Opens Ctrl+G dialog to enter target index."""
        total = len(self.data_manager.image_files)
        if total == 0:
            return
        
        val, ok = QInputDialog.getInt(
            self, "Nhảy tới ảnh", f"Nhập số thứ tự ảnh (1 - {total}):",
            value=self.data_manager.current_index + 1, min=1, max=total
        )
        if ok:
            self.jump_to_index(val - 1)

    def open_search_dialog(self):
        """Opens Ctrl+F dialog to search for filenames."""
        if not self.data_manager.image_files:
            return
        
        dialog = SearchDialog(self.data_manager.image_files, self)
        # Inherit stylesheet
        dialog.setStyleSheet(self.styleSheet())
        if dialog.exec():
            selected = dialog.selected_filename
            if selected:
                idx = self.data_manager.image_files.index(selected)
                self.jump_to_index(idx)

    # ----------------- Update Info Displays -----------------
    def update_stats_display(self):
        """Updates stats widgets with calculation results."""
        stats = self.data_manager.get_stats()
        self.lbl_stat_total.setText(f"Tổng: {stats['total']}")
        self.lbl_stat_labeled.setText(f"Đã gán nhãn: {stats['labeled']}")
        self.lbl_stat_unlabeled.setText(f"Chưa gán nhãn: {stats['unlabeled']}")
        self.lbl_stat_pct.setText(f"Hoàn thành: {stats['percentage']:.1f}%")
        
        self.progress_bar.setMaximum(stats['total'])
        self.progress_bar.setValue(stats['labeled'])

    # ----------------- Export dataset with progress -----------------
    def run_export(self):
        """Validates labels and kicks off the background export task."""
        if not self.data_manager.directory or not self.data_manager.image_files:
            QMessageBox.warning(self, "Cảnh báo", "Không có dữ liệu để xuất!")
            return
            
        stats = self.data_manager.get_stats()
        if stats['labeled'] == 0:
            QMessageBox.information(self, "Thông tin", "Không có ảnh nào đã được gán nhãn để xuất!")
            return
            
        self.export_dialog = QProgressDialog("Đang quét dữ liệu...", "Hủy", 0, stats['labeled'], self)
        self.export_dialog.setWindowTitle("Xuất Dataset")
        self.export_dialog.setWindowModality(Qt.WindowModal)
        self.export_dialog.setAutoClose(True)
        self.export_dialog.setMinimumDuration(0)
        self.export_dialog.setStyleSheet(self.styleSheet())
        
        # Configure and run the background thread
        self.export_thread = ExportThread(
            self.data_manager.directory, 
            self.data_manager.image_files, 
            self.data_manager.labels
        )
        
        self.export_thread.progress.connect(self.on_export_progress)
        self.export_thread.finished_export.connect(self.on_export_finished)
        self.export_thread.error_occurred.connect(self.on_export_error)
        
        # Connect cancel button
        self.export_dialog.canceled.connect(self.export_thread.terminate)
        
        self.export_thread.start()

    def on_export_progress(self, current, total):
        self.export_dialog.setMaximum(total)
        self.export_dialog.setValue(current)
        self.export_dialog.setLabelText(f"Đang sao chép và đổi tên: {current} / {total} ảnh...")

    def on_export_finished(self, total_copied):
        QMessageBox.information(
            self, "Thành công", 
            f"Đã xuất thành công {total_copied} ảnh vào thư mục 'renamed_dataset/'!"
        )

    def on_export_error(self, err_msg):
        QMessageBox.critical(self, "Lỗi", f"Có lỗi xảy ra khi xuất dữ liệu:\n{err_msg}")

    def closeEvent(self, event):
        """Saves current state and configuration on window exit."""
        self.save_current_label_state()
        self.save_settings()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = OCRLabelingApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
