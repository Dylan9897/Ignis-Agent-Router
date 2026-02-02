# encoding : utf-8 -*-                            
# @author  : 冬瓜                              
# @mail    : dylan_han@126.com    
# @Time    : 2026/1/27 13:14
import sys
import os
import math
import random
import traceback
from PyQt6.QtWidgets import QApplication, QWidget, QHBoxLayout, QPushButton, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import (QPixmap, QPainter, QPainterPath, QColor, QPen,
                         QBrush, QRadialGradient, QLinearGradient)

# ================= 配置区 =================
IMAGE_NAME = "assets/frog_avatar.png"
ENABLE_TRANSPARENT = True


# =========================================

class Particle:
    """ 粒子类 (来自 Main2，用于说话特效) """

    def __init__(self, x, y, angle, speed, life, color):
        self.x = x
        self.y = y
        self.vx = math.cos(math.radians(angle)) * speed
        self.vy = math.sin(math.radians(angle)) * speed
        self.life = life
        self.max_life = life
        self.color = color
        self.size = random.uniform(2, 4)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        self.size *= 0.95


class DistinctiveFrog(QWidget):
    def __init__(self):
        super().__init__()

        # --- 资源加载 (Main2 的安全加载逻辑) ---
        try:
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            self.image_path = os.path.join(base_path, IMAGE_NAME)
            self.original_pixmap = QPixmap(self.image_path)
            self.image_loaded = not self.original_pixmap.isNull()
        except Exception:
            self.image_loaded = False

        # --- 窗口设置 ---
        flags = Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        if ENABLE_TRANSPARENT:
            flags |= Qt.WindowType.FramelessWindowHint
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(flags)
        self.resize(300, 300)

        # --- 状态与颜色 ---
        self.state = "IDLE"
        # 混合了 Main1 和 Main2 的配色习惯
        self.colors = {
            "IDLE": QColor(200, 255, 255),  # Main1 的青白
            "LISTENING": QColor(0, 191, 255),  # Main1 的深蓝
            "SPEAKING": QColor(255, 80, 80)  # Main2 的烈焰红/橙
        }
        self.current_color = QColor(self.colors["IDLE"])

        # --- 动画参数 ---
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_safe)
        self.timer.start(16)  # 60FPS

        # 独立的角度变量 (为了完美还原 Main1 的手感)
        self.angle_slow = 0  # 给待机用
        self.angle_mid = 0  # 给听用
        self.angle_fast = 0  # 给说用 (Main2逻辑)

        self.audio_jitter = 0  # 模拟音频抖动 (Main2核心)
        self.particles = []  # 粒子容器
        self.old_pos = None

    def animate_safe(self):
        try:
            self.animate()
        except Exception:
            traceback.print_exc()

    def animate(self):
        # 1. 更新角度 (保留 Main1 的多级速度逻辑)
        self.angle_slow = (self.angle_slow + 0.5) % 360
        self.angle_mid = (self.angle_mid + 2.0) % 360
        self.angle_fast = (self.angle_fast + 4.0) % 360  # 基础旋转

        # 2. 颜色平滑过渡 (Main2 的 Lerp 功能)
        target = self.colors.get(self.state, QColor(255, 255, 255))
        self.lerp_color(target, 0.1)

        # 3. 状态特有逻辑
        if self.state == "SPEAKING":
            # --- Main2 的说话逻辑 (抖动+粒子) ---
            # 模拟波形
            base_wave = (math.sin(self.angle_fast * 0.1) + 1) / 2
            noise = random.uniform(-0.2, 0.4)
            self.audio_jitter = max(0.0, min(1.0, base_wave * 0.3 + noise * 0.2))

            # 喷射粒子
            if random.random() < 0.4:
                self.spawn_particle(speed_min=2, speed_max=5, spread=True)
        else:
            # 待机和听模式，不需要剧烈抖动，稍微一点呼吸感即可
            self.audio_jitter = (math.sin(self.angle_slow * 0.1) + 1) / 2 * 0.1

        # 4. 更新粒子 (Main2)
        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.life > 0]

        self.update()

    def lerp_color(self, target, t):
        """ 安全的颜色插值 """
        try:
            r = self.current_color.red() + (target.red() - self.current_color.red()) * t
            g = self.current_color.green() + (target.green() - self.current_color.green()) * t
            b = self.current_color.blue() + (target.blue() - self.current_color.blue()) * t
            self.current_color = QColor(max(0, min(255, int(r))),
                                        max(0, min(255, int(g))),
                                        max(0, min(255, int(b))))
        except Exception:
            self.current_color = QColor(255, 255, 255)

    def spawn_particle(self, speed_min, speed_max, spread=False):
        center = self.rect().center()
        angle = random.randint(0, 360)
        speed = random.uniform(speed_min, speed_max)
        c = QColor(self.current_color)
        c.setAlpha(random.randint(100, 255))

        radius = 70
        start_x = center.x() + math.cos(math.radians(angle)) * radius
        start_y = center.y() + math.sin(math.radians(angle)) * radius

        p = Particle(start_x, start_y, angle if spread else 0, speed, 30, c)
        self.particles.append(p)

    def paintEvent(self, event):
        try:
            self._draw_safe(event)
        except Exception:
            pass

    def _draw_safe(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        center = QPointF(float(rect.center().x()), float(rect.center().y()))
        base_radius = 65

        # --- 1. 绘制粒子 (仅在 Speaking 模式或有残留时显示) ---
        if self.particles:
            painter.save()
            for p in self.particles:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(p.color)
                painter.drawEllipse(QPointF(p.x, p.y), p.size, p.size)
            painter.restore()

        # --- 2. 状态绘制分发 (混合逻辑核心) ---
        if self.state == "IDLE":
            # 使用 Main1 的逻辑
            self.draw_idle_mode_main1(painter, center, base_radius)
        elif self.state == "LISTENING":
            # 使用 Main1 的逻辑
            self.draw_listening_mode_main1(painter, center, base_radius)
        elif self.state == "SPEAKING":
            # 使用 Main2 的逻辑
            self.draw_speaking_mode_main2(painter, center, base_radius)

        # --- 3. 头像绘制 (使用 Main2 的高级质感版本) ---
        # 阴影
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 80))
        painter.drawEllipse(QPointF(center.x() + 4, center.y() + 4), base_radius, base_radius)

        # 图片裁剪
        path = QPainterPath()
        path.addEllipse(center, base_radius, base_radius)
        painter.setClipPath(path)

        if self.image_loaded:
            target_rect = QRectF(center.x() - base_radius, center.y() - base_radius, base_radius * 2, base_radius * 2)
            painter.drawPixmap(target_rect, self.original_pixmap, QRectF(self.original_pixmap.rect()))
        else:
            painter.setBrush(QColor(40, 40, 40))
            painter.drawRect(rect)

        # 玻璃高光 (Main2 特性)
        painter.setClipping(False)
        highlight = QLinearGradient(center.x() - base_radius, center.y() - base_radius,
                                    center.x() + base_radius, center.y() + base_radius)
        highlight.setColorAt(0.0, QColor(255, 255, 255, 120))
        highlight.setColorAt(0.5, QColor(255, 255, 255, 0))
        painter.setBrush(highlight)
        path_hl = QPainterPath()
        path_hl.addEllipse(QRectF(center.x() - base_radius + 5, center.y() - base_radius + 5,
                                  base_radius * 2 - 10, base_radius * 1.5))
        painter.drawPath(path_hl)

        # 边框
        stroke_color = QColor(self.current_color)
        stroke_color.setAlpha(200)
        painter.setPen(QPen(stroke_color, 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, base_radius, base_radius)

    # ================= 融合绘制逻辑 =================

    def draw_idle_mode_main1(self, painter, center, radius):
        """ [来自 Main1] 待机模式：优雅的虚线，极慢旋转 """
        # 注意：这里使用 self.current_color (Main2特性) 来支持颜色过渡，
        # 但绘制逻辑完全是 Main1 的
        color = QColor(self.current_color)

        painter.save()
        painter.translate(center)
        painter.rotate(self.angle_slow)

        # 画两层虚线圈
        pen = QPen(color)
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DotLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)

        painter.setPen(pen)
        r_ring = radius + 10
        painter.drawEllipse(QPointF(0, 0), r_ring, r_ring)

        # 外层更淡的一圈
        color.setAlpha(100)
        pen.setColor(color)
        painter.setPen(pen)
        painter.drawEllipse(QPointF(0, 0), r_ring + 8, r_ring + 8)

        painter.restore()

    def draw_listening_mode_main1(self, painter, center, radius):
        """ [来自 Main1] 听模式：双轨雷达，中速，反向旋转 """
        color = QColor(self.current_color)

        # 1. 外圈：顺时针转
        painter.save()
        painter.translate(center)
        painter.rotate(self.angle_mid)

        pen = QPen(color)
        pen.setWidth(4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        r_out = radius + 12
        # 画两个不对称的弧 (Main1 特征)
        painter.drawArc(QRectF(-r_out, -r_out, r_out * 2, r_out * 2), 0 * 16, 100 * 16)
        painter.drawArc(QRectF(-r_out, -r_out, r_out * 2, r_out * 2), 180 * 16, 100 * 16)
        painter.restore()

        # 2. 内圈：逆时针转
        painter.save()
        painter.translate(center)
        painter.rotate(-self.angle_mid * 1.5)

        pen.setWidth(2)
        color.setAlpha(150)
        pen.setColor(color)
        painter.setPen(pen)

        r_in = radius + 5
        # 画三个小段 (Main1 特征)
        painter.drawArc(QRectF(-r_in, -r_in, r_in * 2, r_in * 2), 0, 60 * 16)
        painter.drawArc(QRectF(-r_in, -r_in, r_in * 2, r_in * 2), 120 * 16, 60 * 16)
        painter.drawArc(QRectF(-r_in, -r_in, r_in * 2, r_in * 2), 240 * 16, 60 * 16)
        painter.restore()

    def draw_speaking_mode_main2(self, painter, center, radius):
        """ [来自 Main2] 说模式：动态波纹 + 抖动 + 粒子 """
        painter.save()
        painter.translate(center)

        # 基础抖动 (Main2 特征)
        scale_base = 1.0 + self.audio_jitter * 0.3
        painter.scale(scale_base, scale_base)

        color = QColor(self.current_color)
        color.setAlpha(100)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)

        # 绘制三层波纹 (Main2 特征)
        for i in range(3):
            r_wave = radius + 5 + (i * 10)
            alpha_calc = int(100 / (i + 1))
            color.setAlpha(max(0, min(255, alpha_calc)))
            painter.setBrush(color)

            # 使用 audio_jitter 让波纹不规则跳动
            jitter_scale = 1.0 + (self.audio_jitter * (0.5 + i * 0.2))
            painter.drawEllipse(QPointF(0, 0), r_wave * jitter_scale, r_wave * jitter_scale)

        # 核心亮圈
        glow_pen = QPen(self.current_color, 4)
        glow_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(glow_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(0, 0), radius + 2, radius + 2)

        painter.restore()

    # --- 鼠标交互 ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def contextMenuEvent(self, event):
        QApplication.quit()


class ControlPanel(QWidget):
    def __init__(self, agent):
        super().__init__()
        self.agent = agent
        self.setWindowTitle("融合版控制器")
        self.setGeometry(100, 100, 300, 150)
        layout = QVBoxLayout()

        lbl = QLabel("状态 (Main1 + Main2 混合体)")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        btn_layout = QHBoxLayout()

        btn_idle = QPushButton("IDLE")
        btn_idle.setToolTip("Main1: 虚线旋转")
        btn_idle.clicked.connect(lambda: self.agent_set_state("IDLE"))

        btn_listen = QPushButton("LISTEN")
        btn_listen.setToolTip("Main1: 双轨雷达")
        btn_listen.clicked.connect(lambda: self.agent_set_state("LISTENING"))

        btn_speak = QPushButton("SPEAK")
        btn_speak.setToolTip("Main2: 粒子爆发")
        btn_speak.clicked.connect(lambda: self.agent_set_state("SPEAKING"))

        btn_layout.addWidget(btn_idle)
        btn_layout.addWidget(btn_listen)
        btn_layout.addWidget(btn_speak)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def agent_set_state(self, state):
        self.agent.state = state


if __name__ == "__main__":
    app = QApplication(sys.argv)
    frog = DistinctiveFrog()
    frog.show()
    panel = ControlPanel(frog)
    panel.show()
    sys.exit(app.exec())