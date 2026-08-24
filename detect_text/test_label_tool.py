import os
import sys
import tempfile
import unittest
import csv
import shutil
from unittest.mock import MagicMock

# 1. Mock PySide6 so the module can be imported without Qt installed
class MockSignal:
    def __init__(self, *args):
        self.listeners = []
    def emit(self, *args):
        for listener in self.listeners:
            listener(*args)
    def connect(self, func):
        self.listeners.append(func)

class MockQThread:
    def __init__(self):
        pass
    def start(self):
        self.run()

class MockQImage:
    Format_RGB32 = 3
    def __init__(self, *args):
        if len(args) > 0 and isinstance(args[0], tuple):
            self._size = args[0]
        else:
            self._size = (100, 100)
    def isNull(self):
        return False
    def hasAlphaChannel(self):
        return False
    def save(self, path, format=None, quality=-1):
        with open(path, 'wb') as f:
            f.write(b"mocked image data")
        return True
    def size(self):
        # Returns a mock size object
        class MockSize:
            def width(self): return 100
            def height(self): return 100
        return MockSize()

class MockQPainter:
    def __init__(self, *args):
        pass
    def drawImage(self, *args):
        pass
    def end(self):
        pass

# Inject mock into sys.modules
mock_qt = MagicMock()
mock_qt.QtCore.QThread = MockQThread
mock_qt.QtCore.Signal = MockSignal
mock_qt.Signal = MockSignal
mock_qt.QThread = MockQThread
mock_qt.QImage = MockQImage
mock_qt.QPainter = MockQPainter
mock_qt.Format_RGB32 = MockQImage.Format_RGB32
mock_qt.white = 3

sys.modules['PySide6'] = mock_qt
sys.modules['PySide6.QtCore'] = mock_qt
sys.modules['PySide6.QtWidgets'] = mock_qt
sys.modules['PySide6.QtGui'] = mock_qt

# Now import the modules to test
from label_tool import OCRDataManager, ExportThread

class TestOCRDataManager(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()
        
        # Create dummy images
        self.dummy_files = [
            "000001.jpg",
            "000002.png",
            "Bảo_2.jpg",      # should auto-extract label "Bảo"
            "Minh_1.png",     # should auto-extract label "Minh"
            "Châu_10.bmp"     # should auto-extract label "Châu"
        ]
        for f in self.dummy_files:
            with open(os.path.join(self.test_dir, f), 'wb') as out:
                out.write(b"dummy data")

    def tearDown(self):
        # Clean up temporary directory
        shutil.rmtree(self.test_dir)

    def test_load_directory_and_auto_extract(self):
        manager = OCRDataManager()
        success = manager.load_directory(self.test_dir)
        self.assertTrue(success)
        
        # Verify images sorted alphabetically
        expected_sort = sorted(self.dummy_files)
        self.assertEqual(manager.image_files, expected_sort)
        
        # Verify auto label extraction
        self.assertEqual(manager.labels.get("Bảo_2.jpg"), "Bảo")
        self.assertEqual(manager.labels.get("Minh_1.png"), "Minh")
        self.assertEqual(manager.labels.get("Châu_10.bmp"), "Châu")
        self.assertNotIn("000001.jpg", manager.labels)

    def test_save_and_load_csv(self):
        manager = OCRDataManager()
        manager.load_directory(self.test_dir)
        
        # Save a new label
        manager.save_current_label("000001.jpg", "Thành")
        
        # Check in memory
        self.assertEqual(manager.labels["000001.jpg"], "Thành")
        self.assertEqual(manager.last_typed_label, "Thành")
        
        # Re-load from another manager instance to verify file persistence
        new_manager = OCRDataManager()
        new_manager.load_directory(self.test_dir)
        
        self.assertEqual(new_manager.labels["000001.jpg"], "Thành")
        # Unicode label should load correctly
        self.assertEqual(new_manager.labels["Bảo_2.jpg"], "Bảo")

    def test_stats(self):
        manager = OCRDataManager()
        manager.load_directory(self.test_dir)
        
        stats = manager.get_stats()
        # 3 are auto-extracted (Bảo_2, Minh_1, Châu_10) out of 5
        self.assertEqual(stats["total"], 5)
        self.assertEqual(stats["labeled"], 3)
        self.assertEqual(stats["unlabeled"], 2)
        self.assertEqual(stats["percentage"], 60.0)

    def test_export_logic(self):
        manager = OCRDataManager()
        manager.load_directory(self.test_dir)
        
        # Label the remaining files
        manager.save_current_label("000001.jpg", "Bảo")
        manager.save_current_label("000002.png", "Bảo")
        
        # Run export using thread logic synchronously
        thread = ExportThread(manager.directory, manager.image_files, manager.labels)
        thread.run()
        
        export_path = os.path.join(self.test_dir, "renamed_dataset")
        self.assertTrue(os.path.exists(export_path))
        
        exported_files = os.listdir(export_path)
        # 5 labeled files should be exported
        self.assertEqual(len(exported_files), 5)
        
        self.assertIn("Bảo_1.jpg", exported_files)
        self.assertIn("Bảo_2.jpg", exported_files)
        self.assertIn("Bảo_3.jpg", exported_files)
        self.assertIn("Minh_1.jpg", exported_files)
        self.assertIn("Châu_1.jpg", exported_files)

if __name__ == "__main__":
    unittest.main()
