
import sys
import os
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter

def create_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor("red"))
    return QIcon(pixmap)

def main():
    app = QApplication(sys.argv)
    
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("System tray not available")
        sys.exit(1)
        
    tray = QSystemTrayIcon()
    tray.setIcon(create_icon())
    tray.setVisible(True)
    tray.show()
    
    # Wait a bit for it to appear
    import time
    time.sleep(1)
    
    rect = tray.geometry()
    print(f"Tray Geometry: {rect}")
    print(f"Result: {rect.x()}, {rect.y()}, {rect.width()}, {rect.height()}")
    
    if rect.isEmpty():
        print("Geometry is empty/invalid")
    else:
        print("Geometry is valid")

if __name__ == "__main__":
    main()
