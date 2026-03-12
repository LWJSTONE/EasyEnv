#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
主窗口UI设计 - 现代简洁的界面风格
"""

import os
import sys
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QComboBox,
    QCheckBox, QScrollArea, QFrame, QGroupBox,
    QMessageBox, QStatusBar, QTabWidget, QTextEdit,
    QSpacerItem, QSizePolicy, QApplication
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon, QColor, QPalette, QLinearGradient, QPainter

from ..core.env_manager import EnvironmentManager
from ..core.installer import InstallWorker
from ..utils.helpers import get_resource_path


class GradientFrame(QFrame):
    """渐变背景框架"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(41, 128, 185))
        gradient.setColorAt(1, QColor(44, 62, 80))
        painter.fillRect(self.rect(), gradient)


class EnvironmentCard(QFrame):
    """环境卡片组件 - 单个开发环境的显示和操作"""
    
    install_clicked = pyqtSignal(str, str)  # env_name, version
    
    def __init__(self, env_info, parent=None):
        super().__init__(parent)
        self.env_info = env_info
        self.env_name = env_info['name']
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI布局"""
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setStyleSheet("""
            EnvironmentCard {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px;
            }
            EnvironmentCard:hover {
                border: 2px solid #3498db;
            }
            QLabel {
                color: #2c3e50;
            }
            QComboBox {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 5px 10px;
                background: white;
                min-width: 120px;
            }
            QComboBox:hover {
                border: 1px solid #3498db;
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(15)
        
        # 左侧：图标和名称
        left_layout = QVBoxLayout()
        left_layout.setSpacing(5)
        
        # 环境图标（使用emoji或文字代替）
        icon_label = QLabel(self.env_info.get('icon', '📦'))
        icon_label.setStyleSheet("font-size: 32px; border: none;")
        icon_label.setAlignment(Qt.AlignCenter)
        
        # 环境名称
        name_label = QLabel(self.env_info['display_name'])
        name_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #2c3e50;
            border: none;
        """)
        
        # 环境描述
        desc_label = QLabel(self.env_info.get('description', ''))
        desc_label.setStyleSheet("""
            font-size: 11px;
            color: #7f8c8d;
            border: none;
        """)
        
        left_layout.addWidget(icon_label)
        left_layout.addWidget(name_label)
        left_layout.addWidget(desc_label)
        left_layout.addStretch()
        
        # 中间：版本选择
        middle_layout = QVBoxLayout()
        middle_layout.setSpacing(5)
        
        version_label = QLabel("选择版本:")
        version_label.setStyleSheet("font-size: 12px; color: #34495e; border: none;")
        
        self.version_combo = QComboBox()
        self.version_combo.addItems(self.env_info.get('versions', ['latest']))
        
        # 状态显示
        self.status_label = QLabel("未安装")
        self.status_label.setStyleSheet("""
            font-size: 11px;
            color: #e74c3c;
            border: none;
            padding: 3px 8px;
            background-color: #ffebee;
            border-radius: 3px;
        """)
        
        middle_layout.addWidget(version_label)
        middle_layout.addWidget(self.version_combo)
        middle_layout.addSpacing(10)
        middle_layout.addWidget(self.status_label)
        middle_layout.addStretch()
        
        # 右侧：选择框
        right_layout = QVBoxLayout()
        right_layout.setAlignment(Qt.AlignCenter)
        
        self.select_checkbox = QCheckBox("选择安装")
        self.select_checkbox.setStyleSheet("""
            QCheckBox {
                font-size: 12px;
            }
            QCheckBox::indicator:checked {
                background-color: #3498db;
                border: 1px solid #2980b9;
                border-radius: 3px;
            }
        """)
        
        right_layout.addStretch()
        right_layout.addWidget(self.select_checkbox)
        right_layout.addStretch()
        
        layout.addLayout(left_layout, 1)
        add_line(layout, vertical=True)
        layout.addLayout(middle_layout, 1)
        add_line(layout, vertical=True)
        layout.addLayout(right_layout, 0)
        
    def get_selected_version(self):
        """获取选中的版本"""
        return self.version_combo.currentText()
    
    def is_selected(self):
        """是否被选中安装"""
        return self.select_checkbox.isChecked()
    
    def set_status(self, status, installed=False):
        """设置安装状态"""
        self.status_label.setText(status)
        if installed:
            self.status_label.setStyleSheet("""
                font-size: 11px;
                color: #27ae60;
                border: none;
                padding: 3px 8px;
                background-color: #e8f5e9;
                border-radius: 3px;
            """)
        else:
            self.status_label.setStyleSheet("""
                font-size: 11px;
                color: #e74c3c;
                border: none;
                padding: 3px 8px;
                background-color: #ffebee;
                border-radius: 3px;
            """)


def add_line(layout, vertical=False):
    """添加分隔线"""
    line = QFrame()
    if vertical:
        line.setFrameShape(QFrame.VLine)
    else:
        line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("background-color: #e0e0e0;")
    layout.addWidget(line)


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.env_manager = EnvironmentManager()
        self.install_worker = None
        self.env_cards = {}
        self.setup_ui()
        self.check_installed_environments()
        
    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("EasyEnv - Windows开发环境一键部署工具")
        self.setMinimumSize(900, 700)
        self.resize(1000, 750)
        
        # 设置窗口样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f6fa;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
                color: #2980b9;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 10px 25px;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1f6dad;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
            QProgressBar {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                text-align: center;
                background-color: #ecf0f1;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 4px;
            }
            QTabWidget::pane {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                background: white;
            }
            QTabBar::tab {
                background: #ecf0f1;
                padding: 8px 20px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #3498db;
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background: #bdc3c7;
            }
        """)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # 顶部标题栏
        self.setup_header(main_layout)
        
        # 创建选项卡
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget, 1)
        
        # 环境安装选项卡
        self.setup_install_tab()
        
        # 已安装环境选项卡
        self.setup_installed_tab()
        
        # 日志选项卡
        self.setup_log_tab()
        
        # 底部操作栏
        self.setup_footer(main_layout)
        
        # 状态栏
        self.statusBar().showMessage("准备就绪")
        
    def setup_header(self, layout):
        """设置顶部标题栏"""
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2980b9, stop:1 #3498db);
                border-radius: 10px;
                padding: 15px;
            }
        """)
        header_frame.setFixedHeight(80)
        
        header_layout = QHBoxLayout(header_frame)
        
        # 标题
        title_layout = QVBoxLayout()
        title_label = QLabel("EasyEnv")
        title_label.setStyleSheet("""
            font-size: 28px;
            font-weight: bold;
            color: white;
            border: none;
        """)
        
        subtitle_label = QLabel("Windows 开发环境一键部署工具 v1.0.0")
        subtitle_label.setStyleSheet("""
            font-size: 13px;
            color: rgba(255,255,255,0.8);
            border: none;
        """)
        
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        # 快捷操作
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.refresh_btn = QPushButton("🔄 刷新状态")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.2);
                color: white;
                border: 1px solid rgba(255,255,255,0.3);
                padding: 8px 15px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.3);
            }
        """)
        self.refresh_btn.clicked.connect(self.check_installed_environments)
        
        btn_layout.addWidget(self.refresh_btn)
        header_layout.addLayout(btn_layout)
        
        layout.addWidget(header_frame)
        
    def setup_install_tab(self):
        """设置安装选项卡"""
        install_widget = QWidget()
        layout = QVBoxLayout(install_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 说明文字
        info_label = QLabel("请选择需要安装的开发环境，然后点击"一键安装"按钮")
        info_label.setStyleSheet("""
            font-size: 13px;
            color: #7f8c8d;
            padding: 10px;
            background-color: #ecf0f1;
            border-radius: 5px;
        """)
        layout.addWidget(info_label)
        
        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a0a0a0;
            }
        """)
        
        # 环境卡片容器
        cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(cards_widget)
        self.cards_layout.setSpacing(10)
        self.cards_layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建环境卡片
        self.create_environment_cards()
        
        self.cards_layout.addStretch()
        scroll_area.setWidget(cards_widget)
        layout.addWidget(scroll_area)
        
        self.tab_widget.addTab(install_widget, "📦 环境安装")
        
    def setup_installed_tab(self):
        """设置已安装环境选项卡"""
        installed_widget = QWidget()
        layout = QVBoxLayout(installed_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 已安装环境列表
        self.installed_text = QTextEdit()
        self.installed_text.setReadOnly(True)
        self.installed_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                padding: 10px;
                font-family: 'Consolas', 'Microsoft YaHei UI';
                font-size: 12px;
            }
        """)
        layout.addWidget(self.installed_text)
        
        self.tab_widget.addTab(installed_widget, "✅ 已安装环境")
        
    def setup_log_tab(self):
        """设置日志选项卡"""
        log_widget = QWidget()
        layout = QVBoxLayout(log_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                padding: 10px;
                font-family: 'Consolas', 'Courier New';
                font-size: 12px;
                background-color: #1e1e1e;
                color: #d4d4d4;
            }
        """)
        layout.addWidget(self.log_text)
        
        # 清空日志按钮
        clear_btn = QPushButton("清空日志")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                max-width: 120px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        clear_btn.clicked.connect(self.log_text.clear)
        layout.addWidget(clear_btn, alignment=Qt.AlignRight)
        
        self.tab_widget.addTab(log_widget, "📋 安装日志")
        
    def setup_footer(self, layout):
        """设置底部操作栏"""
        footer_frame = QFrame()
        footer_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        
        footer_layout = QHBoxLayout(footer_frame)
        
        # 进度条
        progress_layout = QVBoxLayout()
        
        self.progress_label = QLabel("准备就绪")
        self.progress_label.setStyleSheet("font-size: 12px; color: #7f8c8d; border: none;")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(25)
        self.progress_bar.setValue(0)
        
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        
        footer_layout.addLayout(progress_layout, 1)
        
        # 全选按钮
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.setFixedWidth(80)
        self.select_all_btn.clicked.connect(self.select_all)
        
        footer_layout.addWidget(self.select_all_btn)
        
        # 一键安装按钮
        self.install_btn = QPushButton("🚀 一键安装")
        self.install_btn.setFixedWidth(150)
        self.install_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                font-size: 15px;
                padding: 12px 30px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        self.install_btn.clicked.connect(self.start_install)
        
        footer_layout.addWidget(self.install_btn)
        
        layout.addWidget(footer_frame)
        
    def create_environment_cards(self):
        """创建环境卡片"""
        environments = self.env_manager.get_available_environments()
        
        for env in environments:
            card = EnvironmentCard(env)
            self.env_cards[env['name']] = card
            self.cards_layout.addWidget(card)
            
    def check_installed_environments(self):
        """检查已安装的环境"""
        self.log("正在检查已安装的环境...")
        installed_list = []
        
        for env_name, card in self.env_cards.items():
            is_installed, version = self.env_manager.check_installed(env_name)
            if is_installed:
                card.set_status(f"已安装 v{version}", installed=True)
                installed_list.append(f"✅ {card.env_info['display_name']} - v{version}")
            else:
                card.set_status("未安装", installed=False)
                
        # 更新已安装环境列表
        if installed_list:
            self.installed_text.setPlainText("\n\n".join(installed_list))
        else:
            self.installed_text.setPlainText("暂未检测到已安装的开发环境")
            
        self.log(f"检查完成，共检测到 {len(installed_list)} 个已安装环境")
        
    def select_all(self):
        """全选/取消全选"""
        if self.select_all_btn.text() == "全选":
            for card in self.env_cards.values():
                card.select_checkbox.setChecked(True)
            self.select_all_btn.setText("取消")
        else:
            for card in self.env_cards.values():
                card.select_checkbox.setChecked(False)
            self.select_all_btn.setText("全选")
            
    def start_install(self):
        """开始安装"""
        # 获取选中的环境
        selected = []
        for env_name, card in self.env_cards.items():
            if card.is_selected():
                selected.append({
                    'name': env_name,
                    'version': card.get_selected_version(),
                    'info': card.env_info
                })
                
        if not selected:
            QMessageBox.warning(self, "提示", "请至少选择一个开发环境进行安装！")
            return
            
        # 确认安装
        env_names = ", ".join([e['info']['display_name'] for e in selected])
        reply = QMessageBox.question(
            self, "确认安装",
            f"即将安装以下环境：\n{env_names}\n\n是否继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
            
        # 禁用按钮
        self.install_btn.setEnabled(False)
        self.install_btn.setText("安装中...")
        self.refresh_btn.setEnabled(False)
        
        # 创建安装线程
        self.install_worker = InstallWorker(selected, self.env_manager)
        self.install_worker.progress.connect(self.on_install_progress)
        self.install_worker.log.connect(self.log)
        self.install_worker.finished.connect(self.on_install_finished)
        self.install_worker.start()
        
    def on_install_progress(self, current, total, env_name, status):
        """安装进度更新"""
        progress = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(progress)
        self.progress_label.setText(f"正在安装 {env_name}: {status}")
        self.statusBar().showMessage(f"安装进度: {current}/{total}")
        
    def on_install_finished(self, success_count, fail_count):
        """安装完成"""
        self.install_btn.setEnabled(True)
        self.install_btn.setText("🚀 一键安装")
        self.refresh_btn.setEnabled(True)
        self.progress_bar.setValue(100 if success_count > 0 else 0)
        
        if fail_count == 0:
            self.progress_label.setText(f"安装完成！成功安装 {success_count} 个环境")
            QMessageBox.information(self, "安装完成", f"成功安装 {success_count} 个开发环境！")
        else:
            self.progress_label.setText(f"安装完成：成功 {success_count}，失败 {fail_count}")
            QMessageBox.warning(self, "安装完成", 
                f"安装完成\n成功: {success_count}\n失败: {fail_count}\n\n请查看日志了解详情")
            
        # 刷新已安装状态
        self.check_installed_environments()
        
    def log(self, message):
        """添加日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        # 滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
