# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/2/2 15:57
import sys
import traceback
from PyQt6.QtWidgets import QApplication
from ui.widget import DesktopFrog

# 全局异常捕获，防止闪退
def excepthook(type, value, tb):
    print("!!! 未捕获的严重异常 !!!")
    traceback.print_exception(type, value, tb)

sys.excepthook = excepthook

if __name__ == "__main__":
    print("=== FrogAI 启动中... ===")
    app = QApplication(sys.argv)

    frog = DesktopFrog()
    frog.show()

    sys.exit(app.exec())

