# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/1/27 11:33

import os
import math

from PyQt6.QtWidgets import QWidget, QApplication, QMessageBox
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QColor, QPen, QGuiApplication

from config import IMAGE_NAME, DASHSCOPE_API_KEY
from core.worker import ConversationWorker

class DesktopFrog(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_resources()
        self.setup_window()
        self.setup_logic()


    def setup_resources(self):
        # 定位 assets 文件夹, 寻找蕉绿蛙图片
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.image_path = os.path.join(current_dir, "assets", IMAGE_NAME)
        # 尝试加载图片
        self.original_pixmap = QPixmap(self.image_path)
        # 确认是否加载成功
        self.image_loaded = not self.original_pixmap.isNull()

    def setup_window(self):
        ##### 设置窗口标志，并同时给窗口贴上标签 #####
        ## FramelessWindowHint: 无边框
        ## WindowStaysOnTopHint: 窗口置顶
        ## Tool: 工具窗口
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        ##### 设置背景透明 #####
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        ##### 设定初始大小 #####
        self.resize(260, 260)
        ##### 定位到屏幕右下角 #####
        self.move_to_bottom_right()
        ##### 初始化坐标变量 #####
        self.old_pos = None

    def move_to_bottom_right(self):
        # 1. 获取屏幕的可用几何尺寸（排除任务栏）
        screen_geometry = QGuiApplication.primaryScreen().availableGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()

        # 2. 获取窗口自身的尺寸
        window_width = self.width()
        window_height = self.height()

        # 3. 计算右下角坐标
        # x = 屏幕宽度 - 窗口宽度 - 边距
        # y = 屏幕高度 - 窗口高度 - 边距
        margin = 10  # 留出 10 像素的间距，看起来不那么拥挤
        x = screen_width - window_width - margin
        y = screen_height - window_height - margin

        # 4. 移动窗口
        self.move(x, y)

    def setup_logic(self):
        # 初始状态：闲置/待机
        self.state = "IDLE"
        # 旋转角度
        self.angle = 0
        # 缩放/呼吸频率
        self.pulse = 0.0

        # 颜色定义
        self.colors = {
            "IDLE": QColor(100, 255, 218),      # 闲置时：淡淡的青绿色
            "LISTENING": QColor(0, 191, 255),   # 听话时：深邃的蓝色
            "SPEAKING": QColor(255, 80, 80)     # 说话时：警示或激动的红色
        }

        self.curr_color = QColor(self.colors["IDLE"])

        # 初始化工作线程
        self.worker = ConversationWorker()
        self.worker.sig_state.connect(self.update_state)

        # 动画定时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(20)

    def update_state(self, s):
        self.state = s

    def mousePressEvent(self, event):
        """
        左键点击： * 记录当前位置（为了后面拖拽）。
        逻辑开关： 如果 AI 正在运行，点击它会强制让它“休眠”；如果没运行，会检查 API Key 并“唤醒”它。
        右键点击： 彻底关闭程序，退出系统。
        :param event:
        :return:
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()
            if self.worker.active:
                print("[UI] 停止 -> 休眠")
                self.worker.active = False
                self.state = "IDLE"
            else:
                if "sk-" not in DASHSCOPE_API_KEY:
                    QMessageBox.warning(self, "Config Error", "请在 config.py 中配置 API KEY")
                    return
                print("[UI] 唤醒 -> 启动")
                self.worker.start()
        elif event.button() == Qt.MouseButton.RightButton:
            self.worker.stop()
            QApplication.quit()

    def mouseMoveEvent(self, event):
        """
        计算鼠标移动的偏移量，然后调用 self.move() 让窗口跟着鼠标走。这样你就能把蛙拖到屏幕任何地方。
        :param event:
        :return:
        """
        if self.old_pos:
            self.move(self.pos() + event.globalPosition().toPoint() - self.old_pos)
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def animate(self):
        """
        这个函数被之前的 QTimer 每 20 毫秒调用一次，它是动画平滑的关键。
        :return:
        """
        self.angle = (self.angle + 2) % 360
        target = self.colors.get(self.state, QColor(255, 255, 255))

        # 颜色平滑过渡
        try:
            r = self.curr_color.red() + (target.red() - self.curr_color.red()) * 0.1
            g = self.curr_color.green() + (target.green() - self.curr_color.green()) * 0.1
            b = self.curr_color.blue() + (target.blue() - self.curr_color.blue()) * 0.1
            self.curr_color = QColor(int(r), int(g), int(b))
        except:
            pass

        # 呼吸效果
        self.pulse = (math.sin(self.angle * 0.2) + 1) * 0.1 if self.state == "SPEAKING" else 0
        self.update()

    def paintEvent(self, event):
        """
        这是最核心的视觉函数。每当 update() 被调用，这里面的代码就会重新画一遍窗口。
        第一层：特效光环 (Aura)
        程序会先在头像外圈画一个圆环。
        IDLE (空闲): 画一个虚线圆环，缓慢旋转。
        LISTENING (听话): 额外画一段圆弧（Arc），而且旋转速度更快，看起来像是在“接收信号”。
        第二层：圆形头像 (Avatar)
        圆形裁剪 (setClipPath): 这是最巧妙的地方。它先画一个圆形的“模具”，然后把你的方形图片塞进去，超出圆形的边缘会被自动切掉。这样你的“蕉绿蛙”就变成了一个精致的圆形挂件。
        容错处理: 如果图片加载失败，它会显示一个黑色圆圈并标注 "NO IMG"，保证程序不崩溃。
        :param event:
        :return:
        """
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = self.rect()
            center = QPointF(rect.width() / 2, rect.height() / 2)
            radius = 75 + (self.pulse * 15)

            # 1. 绘制特效
            painter.save()
            painter.translate(center)
            painter.rotate(self.angle if self.state != "IDLE" else self.angle * 0.2)

            pen = QPen(self.curr_color, 3)
            if self.state == "IDLE": pen.setStyle(Qt.PenStyle.DotLine)
            painter.setPen(pen)
            painter.drawEllipse(QPointF(0, 0), radius + 8, radius + 8)

            if self.state == "LISTENING":
                painter.rotate(-self.angle * 2)
                painter.drawArc(QRectF(-radius - 15, -radius - 15, (radius + 15) * 2, (radius + 15) * 2), 0, 120 * 16)
            painter.restore()

            # 2. 绘制头像
            path = QPainterPath()
            path.addEllipse(center, radius, radius)
            painter.setClipPath(path)

            if self.image_loaded:
                painter.drawPixmap(QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2),
                                   self.original_pixmap, QRectF(self.original_pixmap.rect()))
            else:
                painter.setBrush(QColor(30, 30, 30))
                painter.drawRect(rect)
                painter.setPen(Qt.GlobalColor.white)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "NO IMG")
        except Exception:
            pass