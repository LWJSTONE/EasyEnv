#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
主窗口UI - 重构版本
支持镜像源配置、环境模板、多版本管理等新功能
"""

import os
import sys
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QComboBox,
    QCheckBox, QScrollArea, QFrame, QGroupBox,
    QMessageBox, QStatusBar, QTabWidget, QTextEdit,
    QSpacerItem, QSizePolicy, QApplication, QDialog,
    QDialogButtonBox, QFormLayout, QLineEdit, QListWidget,
    QListWidgetItem, QSplitter, QMenu, QAction, QToolBar,
    QFileDialog, QRadioButton, QButtonGroup, QSpinBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QFont, QIcon, QColor, QStandardItemModel, QStandardItem

from ..core.version_manager import VersionManager, VersionInfo
from ..core.mirror_manager import MirrorManager
from ..core.downloader import DownloadManager
from ..core.rollback_manager import RollbackManager, InstallStatus
from ..core.template_manager import TemplateManager, EnvironmentTemplate
from ..core.lifecycle_manager import EnvironmentLifecycleManager
from ..core.installer import InstallWorker
from ..utils.privilege import PrivilegeManager, UACPrompt


class SettingsDialog(QDialog):
    """设置对话框"""
    
    def __init__(self, mirror_manager: MirrorManager, parent=None):
        super().__init__(parent)
        self.mirror_manager = mirror_manager
        self.setWindowTitle("设置")
        self.setMinimumSize(500, 400)
        self.setup_ui()
        self.load_settings()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 镜像源设置
        mirror_group = QGroupBox("镜像源设置")
        mirror_layout = QVBoxLayout(mirror_group)
        
        self.mirror_preference = QButtonGroup()
        prefs = [
            ('auto', '自动选择（推荐）'),
            ('official', '使用官方源'),
            ('china', '使用国内镜像'),
        ]
        for i, (value, label) in enumerate(prefs):
            rb = QRadioButton(label)
            self.mirror_preference.addButton(rb, i)
            mirror_layout.addWidget(rb)
        
        # 镜像速度测试
        test_btn = QPushButton("测试镜像速度")
        test_btn.clicked.connect(self.test_mirror_speed)
        mirror_layout.addWidget(test_btn)
        
        self.speed_result = QLabel("")
        mirror_layout.addWidget(self.speed_result)
        
        layout.addWidget(mirror_group)
        
        # 代理设置
        proxy_group = QGroupBox("代理设置")
        proxy_layout = QFormLayout(proxy_group)
        
        self.proxy_enabled = QCheckBox("启用代理")
        proxy_layout.addRow(self.proxy_enabled)
        
        self.http_proxy = QLineEdit()
        self.http_proxy.setPlaceholderText("http://127.0.0.1:7890")
        proxy_layout.addRow("HTTP代理:", self.http_proxy)
        
        self.https_proxy = QLineEdit()
        self.https_proxy.setPlaceholderText("http://127.0.0.1:7890")
        proxy_layout.addRow("HTTPS代理:", self.https_proxy)
        
        layout.addWidget(proxy_group)
        
        # 高级设置
        advanced_group = QGroupBox("高级设置")
        advanced_layout = QFormLayout(advanced_group)
        
        self.retry_count = QSpinBox()
        self.retry_count.setRange(1, 10)
        self.retry_count.setValue(3)
        advanced_layout.addRow("下载重试次数:", self.retry_count)
        
        self.use_multithread = QCheckBox("启用多线程下载")
        self.use_multithread.setChecked(True)
        advanced_layout.addRow(self.use_multithread)
        
        layout.addWidget(advanced_group)
        
        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.save_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def load_settings(self):
        pref = self.mirror_manager.get_preference()
        pref_map = {'auto': 0, 'official': 1, 'china': 2}
        self.mirror_preference.button(pref_map.get(pref, 0)).setChecked(True)
        
        proxy_config = self.mirror_manager.get_proxy_config()
        self.proxy_enabled.setChecked(proxy_config.get('enabled', False))
        self.http_proxy.setText(proxy_config.get('http', ''))
        self.https_proxy.setText(proxy_config.get('https', ''))
        
    def save_and_close(self):
        pref_map = {0: 'auto', 1: 'official', 2: 'china'}
        pref_id = self.mirror_preference.checkedId()
        self.mirror_manager.set_preference(pref_map.get(pref_id, 'auto'))
        
        self.mirror_manager.set_proxy_config(
            enabled=self.proxy_enabled.isChecked(),
            http=self.http_proxy.text(),
            https=self.https_proxy.text()
        )
        self.accept()
        
    def test_mirror_speed(self):
        self.speed_result.setText("正在测试...")
        QApplication.processEvents()
        
        results = self.mirror_manager.test_all_mirrors()
        
        lines = []
        for name, speed in sorted(results.items(), key=lambda x: x[1] if x[1] > 0 else 999999):
            if speed > 0:
                lines.append(f"{name}: {speed:.0f}ms")
            else:
                lines.append(f"{name}: 不可用")
        
        self.speed_result.setText("\n".join(lines))


class TemplateDialog(QDialog):
    """模板选择对话框"""
    
    template_selected = pyqtSignal(str)  # template_name
    
    def __init__(self, template_manager: TemplateManager, parent=None):
        super().__init__(parent)
        self.template_manager = template_manager
        self.setWindowTitle("选择环境模板")
        self.setMinimumSize(600, 500)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 模板列表
        self.template_list = QListWidget()
        templates = self.template_manager.get_template_list()
        
        for t in templates:
            item = QListWidgetItem(f"{t['display_name']} - {t['description']}")
            item.setData(Qt.UserRole, t['name'])
            self.template_list.addItem(item)
        
        self.template_list.itemDoubleClicked.connect(self.select_template)
        layout.addWidget(QLabel("双击选择模板或点击确定按钮:"))
        layout.addWidget(self.template_list)
        
        # 模板详情
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setMaximumHeight(150)
        self.template_list.itemClicked.connect(self.show_detail)
        layout.addWidget(self.detail_text)
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        import_btn = QPushButton("导入模板...")
        import_btn.clicked.connect(self.import_template)
        btn_layout.addWidget(import_btn)
        
        export_btn = QPushButton("导出当前选择...")
        export_btn.clicked.connect(self.export_template)
        btn_layout.addWidget(export_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 确定/取消
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.select_template)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def show_detail(self, item):
        template_name = item.data(Qt.UserRole)
        template = self.template_manager.get_template(template_name)
        
        if template:
            detail = f"名称: {template.name}\n"
            detail += f"描述: {template.description}\n"
            detail += f"作者: {template.author}\n"
            detail += f"环境数量: {len(template.environments)}\n"
            detail += "\n包含环境:\n"
            for env in template.environments:
                detail += f"  - {env.name} {env.version}\n"
            
            self.detail_text.setPlainText(detail)
    
    def select_template(self):
        item = self.template_list.currentItem()
        if item:
            template_name = item.data(Qt.UserRole)
            self.template_selected.emit(template_name)
            self.accept()
    
    def import_template(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择模板文件", "",
            "JSON文件 (*.json);;YAML文件 (*.yaml *.yml)"
        )
        if filepath:
            template = self.template_manager.load_template(filepath)
            if template:
                QMessageBox.information(self, "成功", f"已导入模板: {template.name}")
                self.accept()
            else:
                QMessageBox.warning(self, "错误", "模板文件格式错误")
    
    def export_template(self):
        item = self.template_list.currentItem()
        if not item:
            return
        
        template_name = item.data(Qt.UserRole)
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存模板", "",
            "JSON文件 (*.json);;YAML文件 (*.yaml)"
        )
        if filepath:
            self.template_manager.export_to_file(template_name, filepath)
            QMessageBox.information(self, "成功", "模板已导出")


class EnvironmentCard(QFrame):
    """环境卡片 - 重构版，支持动态版本获取"""
    
    def __init__(self, env_info: dict, version_manager: VersionManager, 
                 mirror_manager: MirrorManager, parent=None):
        super().__init__(parent)
        self.env_info = env_info
        self.env_name = env_info['name']
        self.version_manager = version_manager
        self.mirror_manager = mirror_manager
        self._versions_loaded = False
        self.setup_ui()
        self.load_versions_async()
        
    def setup_ui(self):
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
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        
        # 左侧：图标和名称
        left_layout = QVBoxLayout()
        
        icon_label = QLabel(self.env_info.get('icon', '📦'))
        icon_label.setStyleSheet("font-size: 32px; border: none;")
        icon_label.setAlignment(Qt.AlignCenter)
        
        name_label = QLabel(self.env_info.get('display_name', self.env_name))
        name_label.setStyleSheet("""
            font-size: 16px; font-weight: bold; color: #2c3e50; border: none;
        """)
        
        desc_label = QLabel(self.env_info.get('description', ''))
        desc_label.setStyleSheet("font-size: 11px; color: #7f8c8d; border: none;")
        
        left_layout.addWidget(icon_label)
        left_layout.addWidget(name_label)
        left_layout.addWidget(desc_label)
        left_layout.addStretch()
        
        # 中间：版本选择
        middle_layout = QVBoxLayout()
        
        version_label = QLabel("选择版本:")
        version_label.setStyleSheet("font-size: 12px; color: #34495e; border: none;")
        
        self.version_combo = QComboBox()
        self.version_combo.setMinimumWidth(150)
        
        # 版本加载状态
        self.loading_label = QLabel("正在获取版本...")
        self.loading_label.setStyleSheet("color: #3498db; font-size: 11px;")
        
        # 镜像源选择
        mirror_label = QLabel("镜像源:")
        mirror_label.setStyleSheet("font-size: 12px; color: #34495e; border: none;")
        
        self.mirror_combo = QComboBox()
        self.update_mirror_options()
        
        # 状态显示
        self.status_label = QLabel("检测中...")
        self.status_label.setStyleSheet("""
            font-size: 11px; color: #7f8c8d; border: none;
            padding: 3px 8px; background-color: #f5f5f5; border-radius: 3px;
        """)
        
        middle_layout.addWidget(version_label)
        middle_layout.addWidget(self.version_combo)
        middle_layout.addWidget(self.loading_label)
        middle_layout.addWidget(mirror_label)
        middle_layout.addWidget(self.mirror_combo)
        middle_layout.addSpacing(10)
        middle_layout.addWidget(self.status_label)
        middle_layout.addStretch()
        
        # 右侧：选择框
        right_layout = QVBoxLayout()
        right_layout.setAlignment(Qt.AlignCenter)
        
        self.select_checkbox = QCheckBox("选择安装")
        right_layout.addStretch()
        right_layout.addWidget(self.select_checkbox)
        right_layout.addStretch()
        
        layout.addLayout(left_layout, 1)
        self.add_separator(layout, vertical=True)
        layout.addLayout(middle_layout, 1)
        self.add_separator(layout, vertical=True)
        layout.addLayout(right_layout, 0)
    
    def add_separator(self, layout, vertical=False):
        line = QFrame()
        line.setFrameShape(QFrame.VLine if vertical else QFrame.HLine)
        line.setStyleSheet("background-color: #e0e0e0;")
        layout.addWidget(line)
    
    def load_versions_async(self):
        """异步加载版本列表"""
        import threading
        
        def load():
            success, versions, message = self.version_manager.get_available_versions(
                self.env_name, use_cache=True
            )
            # 在主线程更新UI
            QTimer.singleShot(0, lambda: self.update_versions(versions, success, message))
        
        thread = threading.Thread(target=load, daemon=True)
        thread.start()
    
    def update_versions(self, versions, success, message):
        """更新版本列表"""
        self.loading_label.hide()
        
        if success and versions:
            for v in versions[:15]:  # 最多显示15个版本
                version_text = v.version
                if v.lts:
                    version_text += " (LTS)"
                if v.security_update:
                    version_text += " 🔒"
                self.version_combo.addItem(version_text, v.version)
            self._versions_loaded = True
        else:
            self.version_combo.addItem("获取失败", "latest")
            self.loading_label.setText("版本获取失败")
            self.loading_label.setStyleSheet("color: #e74c3c;")
            self.loading_label.show()
    
    def update_mirror_options(self):
        """更新镜像源选项"""
        mirrors = self.mirror_manager.get_available_mirrors_for_env(self.env_name)
        self.mirror_combo.clear()
        for name, display_name in mirrors:
            self.mirror_combo.addItem(display_name, name)
    
    def get_selected_version(self) -> str:
        return self.version_combo.currentData() or "latest"
    
    def get_selected_mirror(self) -> str:
        return self.mirror_combo.currentData() or "auto"
    
    def is_selected(self) -> bool:
        return self.select_checkbox.isChecked()
    
    def set_status(self, status: str, installed: bool = False):
        self.status_label.setText(status)
        if installed:
            self.status_label.setStyleSheet("""
                font-size: 11px; color: #27ae60; border: none;
                padding: 3px 8px; background-color: #e8f5e9; border-radius: 3px;
            """)
        else:
            self.status_label.setStyleSheet("""
                font-size: 11px; color: #e74c3c; border: none;
                padding: 3px 8px; background-color: #ffebee; border-radius: 3px;
            """)


class MainWindow(QMainWindow):
    """主窗口 - 重构版"""
    
    def __init__(self):
        super().__init__()
        
        # 初始化管理器
        self.version_manager = VersionManager()
        self.mirror_manager = MirrorManager()
        self.download_manager = DownloadManager(self.mirror_manager)
        self.rollback_manager = RollbackManager()
        self.template_manager = TemplateManager()
        self.lifecycle_manager = EnvironmentLifecycleManager()
        
        self.install_worker = None
        self.env_cards = {}
        
        # 检查权限
        self.is_admin = PrivilegeManager.is_admin()
        
        self.setup_ui()
        self.setup_toolbar()
        self.check_installed_environments()
        
        # 如果不是管理员，显示提示
        if not self.is_admin:
            QTimer.singleShot(1000, self.show_admin_prompt)
    
    def setup_ui(self):
        self.setWindowTitle("EasyEnv - Windows开发环境一键部署工具 v2.0")
        self.setMinimumSize(1000, 750)
        self.resize(1100, 800)
        
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f6fa; }
            QGroupBox {
                font-weight: bold; border: 2px solid #3498db;
                border-radius: 8px; margin-top: 10px; padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 15px; padding: 0 5px; color: #2980b9;
            }
            QPushButton {
                background-color: #3498db; color: white; border: none;
                padding: 10px 25px; border-radius: 5px; font-size: 14px; font-weight: bold;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:pressed { background-color: #1f6dad; }
            QPushButton:disabled { background-color: #bdc3c7; }
            QProgressBar {
                border: 1px solid #e0e0e0; border-radius: 5px;
                text-align: center; background-color: #ecf0f1;
            }
            QProgressBar::chunk { background-color: #3498db; border-radius: 4px; }
            QTabWidget::pane {
                border: 1px solid #e0e0e0; border-radius: 5px; background: white;
            }
            QTabBar::tab {
                background: #ecf0f1; padding: 8px 20px; margin-right: 2px;
                border-top-left-radius: 4px; border-top-right-radius: 4px;
            }
            QTabBar::tab:selected { background: #3498db; color: white; }
            QTabBar::tab:hover:!selected { background: #bdc3c7; }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # 顶部标题栏
        self.setup_header(main_layout)
        
        # 选项卡
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget, 1)
        
        self.setup_install_tab()
        self.setup_installed_tab()
        self.setup_template_tab()
        self.setup_log_tab()
        
        # 底部操作栏
        self.setup_footer(main_layout)
        
        # 状态栏
        self.statusBar().showMessage(
            "准备就绪" + (" [管理员模式]" if self.is_admin else " [普通用户模式]")
        )
    
    def setup_toolbar(self):
        toolbar = self.addToolBar("工具栏")
        toolbar.setMovable(False)
        
        # 设置按钮
        settings_action = QAction("⚙️ 设置", self)
        settings_action.triggered.connect(self.show_settings)
        toolbar.addAction(settings_action)
        
        # 刷新按钮
        refresh_action = QAction("🔄 刷新", self)
        refresh_action.triggered.connect(self.check_installed_environments)
        toolbar.addAction(refresh_action)
        
        toolbar.addSeparator()
        
        # 模板按钮
        template_action = QAction("📋 模板", self)
        template_action.triggered.connect(self.show_template_dialog)
        toolbar.addAction(template_action)
        
        toolbar.addSeparator()
        
        # 离线模式
        self.offline_action = QAction("📦 离线模式", self)
        self.offline_action.setCheckable(True)
        toolbar.addAction(self.offline_action)
    
    def setup_header(self, layout):
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2980b9, stop:1 #3498db);
                border-radius: 10px; padding: 15px;
            }
        """)
        header_frame.setFixedHeight(90)
        
        header_layout = QHBoxLayout(header_frame)
        
        title_layout = QVBoxLayout()
        title_label = QLabel("EasyEnv v2.0")
        title_label.setStyleSheet("""
            font-size: 28px; font-weight: bold; color: white; border: none;
        """)
        
        subtitle_label = QLabel("Windows 开发环境一键部署工具 - 支持镜像源、环境模板、多版本管理")
        subtitle_label.setStyleSheet("""
            font-size: 12px; color: rgba(255,255,255,0.8); border: none;
        """)
        
        self.status_indicator = QLabel()
        self.update_admin_status()
        
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)
        title_layout.addWidget(self.status_indicator)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        # 快捷按钮
        btn_layout = QVBoxLayout()
        
        template_btn = QPushButton("📋 使用模板")
        template_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.2);
                color: white; border: 1px solid rgba(255,255,255,0.3);
                padding: 8px 15px; font-size: 12px;
            }
            QPushButton:hover { background-color: rgba(255,255,255,0.3); }
        """)
        template_btn.clicked.connect(self.show_template_dialog)
        
        settings_btn = QPushButton("⚙️ 设置")
        settings_btn.setStyleSheet(template_btn.styleSheet())
        settings_btn.clicked.connect(self.show_settings)
        
        btn_layout.addWidget(template_btn)
        btn_layout.addWidget(settings_btn)
        header_layout.addLayout(btn_layout)
        
        layout.addWidget(header_frame)
    
    def update_admin_status(self):
        if self.is_admin:
            self.status_indicator.setText("✅ 管理员模式")
            self.status_indicator.setStyleSheet("color: #2ecc71; font-size: 11px; border: none;")
        else:
            self.status_indicator.setText("⚠️ 建议以管理员身份运行")
            self.status_indicator.setStyleSheet("color: #f39c12; font-size: 11px; border: none;")
    
    def show_admin_prompt(self):
        reply = QMessageBox.question(
            self, "权限提示",
            "建议以管理员身份运行以获得完整功能。\n\n是否重新以管理员身份运行？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            PrivilegeManager.run_as_admin()
            self.close()
    
    def setup_install_tab(self):
        install_widget = QWidget()
        layout = QVBoxLayout(install_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 提示信息
        info_label = QLabel(
            "💡 提示：版本列表从官方API动态获取，支持选择国内镜像加速下载。\n"
            "   点击卡片左侧复选框选择要安装的环境，然后点击下方"一键安装"按钮。"
        )
        info_label.setStyleSheet("""
            font-size: 12px; color: #34495e; padding: 10px;
            background-color: #e8f4fd; border-radius: 5px;
        """)
        layout.addWidget(info_label)
        
        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea { border: none; background-color: transparent; }
            QScrollBar:vertical {
                border: none; background: #f0f0f0; width: 10px; border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0; border-radius: 5px;
            }
        """)
        
        cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(cards_widget)
        self.cards_layout.setSpacing(10)
        self.cards_layout.setContentsMargins(5, 5, 5, 5)
        
        self.create_environment_cards()
        
        self.cards_layout.addStretch()
        scroll_area.setWidget(cards_widget)
        layout.addWidget(scroll_area)
        
        self.tab_widget.addTab(install_widget, "📦 环境安装")
    
    def setup_installed_tab(self):
        installed_widget = QWidget()
        layout = QVBoxLayout(installed_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 说明
        label = QLabel("已检测到的开发环境（支持多版本管理）:")
        layout.addWidget(label)
        
        # 已安装环境列表
        self.installed_list = QListWidget()
        self.installed_list.setStyleSheet("""
            QListWidget { border: 1px solid #e0e0e0; border-radius: 5px; }
            QListWidget::item { padding: 10px; }
            QListWidget::item:selected { background-color: #3498db; color: white; }
        """)
        self.installed_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.installed_list.customContextMenuRequested.connect(self.show_installed_context_menu)
        layout.addWidget(self.installed_list)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        self.uninstall_btn = QPushButton("🗑️ 卸载选中")
        self.uninstall_btn.clicked.connect(self.uninstall_selected)
        btn_layout.addWidget(self.uninstall_btn)
        
        self.set_active_btn = QPushButton("✅ 设为默认版本")
        self.set_active_btn.clicked.connect(self.set_active_version)
        btn_layout.addWidget(self.set_active_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.tab_widget.addTab(installed_widget, "✅ 已安装环境")
    
    def setup_template_tab(self):
        template_widget = QWidget()
        layout = QVBoxLayout(template_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 模板说明
        info = QLabel(
            "📋 环境模板功能：\n"
            "• 使用预设模板快速配置开发环境\n"
            "• 导入/导出配置文件，实现团队环境统一\n"
            "• 支持自定义安装脚本"
        )
        info.setStyleSheet("padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
        layout.addWidget(info)
        
        # 模板列表
        self.template_list = QListWidget()
        templates = self.template_manager.get_template_list()
        for t in templates:
            item = QListWidgetItem(f"{t['display_name']} - {t['description']}")
            item.setData(Qt.UserRole, t['name'])
            self.template_list.addItem(item)
        layout.addWidget(self.template_list)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        apply_btn = QPushButton("应用模板")
        apply_btn.clicked.connect(self.apply_selected_template)
        btn_layout.addWidget(apply_btn)
        
        import_btn = QPushButton("导入模板")
        import_btn.clicked.connect(self.import_template)
        btn_layout.addWidget(import_btn)
        
        export_btn = QPushButton("导出当前选择")
        export_btn.clicked.connect(self.export_current_as_template)
        btn_layout.addWidget(export_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.tab_widget.addTab(template_widget, "📋 环境模板")
    
    def setup_log_tab(self):
        log_widget = QWidget()
        layout = QVBoxLayout(log_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0; border-radius: 5px; padding: 10px;
                font-family: 'Consolas', 'Courier New'; font-size: 12px;
                background-color: #1e1e1e; color: #d4d4d4;
            }
        """)
        layout.addWidget(self.log_text)
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        clear_btn = QPushButton("清空日志")
        clear_btn.setStyleSheet("background-color: #e74c3c;")
        clear_btn.clicked.connect(self.log_text.clear)
        btn_layout.addWidget(clear_btn)
        
        save_btn = QPushButton("保存日志")
        save_btn.clicked.connect(self.save_log)
        btn_layout.addWidget(save_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.tab_widget.addTab(log_widget, "📋 安装日志")
    
    def setup_footer(self, layout):
        footer_frame = QFrame()
        footer_frame.setStyleSheet("""
            QFrame {
                background-color: white; border: 1px solid #e0e0e0;
                border-radius: 8px; padding: 10px;
            }
        """)
        
        footer_layout = QHBoxLayout(footer_frame)
        
        # 进度
        progress_layout = QVBoxLayout()
        
        self.progress_label = QLabel("准备就绪")
        self.progress_label.setStyleSheet("font-size: 12px; color: #7f8c8d; border: none;")
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(25)
        self.progress_bar.setValue(0)
        
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        
        footer_layout.addLayout(progress_layout, 1)
        
        # 选择统计
        self.selection_label = QLabel("已选择: 0 个环境")
        self.selection_label.setStyleSheet("font-size: 12px; color: #7f8c8d; border: none;")
        footer_layout.addWidget(self.selection_label)
        
        # 全选按钮
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.setFixedWidth(80)
        self.select_all_btn.clicked.connect(self.toggle_select_all)
        footer_layout.addWidget(self.select_all_btn)
        
        # 一键安装按钮
        self.install_btn = QPushButton("🚀 一键安装")
        self.install_btn.setFixedWidth(150)
        self.install_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; font-size: 15px; padding: 12px 30px;
            }
            QPushButton:hover { background-color: #229954; }
        """)
        self.install_btn.clicked.connect(self.start_install)
        footer_layout.addWidget(self.install_btn)
        
        layout.addWidget(footer_frame)
    
    def create_environment_cards(self):
        """创建环境卡片"""
        environments = [
            {'name': 'python', 'display_name': 'Python', 'icon': '🐍', 
             'description': 'Python编程语言环境', 'category': 'language'},
            {'name': 'nodejs', 'display_name': 'Node.js', 'icon': '💚',
             'description': 'JavaScript运行时环境', 'category': 'language'},
            {'name': 'git', 'display_name': 'Git', 'icon': '🔀',
             'description': '分布式版本控制系统', 'category': 'tool'},
            {'name': 'vscode', 'display_name': 'VS Code', 'icon': '💠',
             'description': '轻量级代码编辑器', 'category': 'editor'},
            {'name': 'jdk', 'display_name': 'OpenJDK', 'icon': '☕',
             'description': 'Java开发工具包', 'category': 'language'},
            {'name': 'go', 'display_name': 'Go', 'icon': '🔵',
             'description': 'Go编程语言环境', 'category': 'language'},
            {'name': 'rust', 'display_name': 'Rust', 'icon': '🦀',
             'description': 'Rust编程语言环境', 'category': 'language'},
            {'name': 'cmake', 'display_name': 'CMake', 'icon': '📐',
             'description': '跨平台构建工具', 'category': 'tool'},
            {'name': 'mingw', 'display_name': 'MinGW-w64', 'icon': '⚙️',
             'description': 'GCC编译器环境', 'category': 'tool'},
            {'name': 'docker', 'display_name': 'Docker Desktop', 'icon': '🐳',
             'description': '容器化应用平台', 'category': 'platform'},
        ]
        
        for env in environments:
            card = EnvironmentCard(
                env, self.version_manager, self.mirror_manager
            )
            card.select_checkbox.stateChanged.connect(self.update_selection_count)
            self.env_cards[env['name']] = card
            self.cards_layout.addWidget(card)
    
    def update_selection_count(self):
        count = sum(1 for c in self.env_cards.values() if c.is_selected())
        self.selection_label.setText(f"已选择: {count} 个环境")
    
    def toggle_select_all(self):
        if self.select_all_btn.text() == "全选":
            for card in self.env_cards.values():
                card.select_checkbox.setChecked(True)
            self.select_all_btn.setText("取消")
        else:
            for card in self.env_cards.values():
                card.select_checkbox.setChecked(False)
            self.select_all_btn.setText("全选")
    
    def check_installed_environments(self):
        """检查已安装环境"""
        self.log("正在检测已安装的开发环境...")
        
        detected = self.lifecycle_manager.detect_all_installed()
        
        # 更新卡片状态
        for env_name, installations in detected.items():
            if env_name in self.env_cards:
                if installations:
                    versions = [inst.version for inst in installations]
                    self.env_cards[env_name].set_status(
                        f"已安装: {', '.join(versions)}", installed=True
                    )
                else:
                    self.env_cards[env_name].set_status("未安装", installed=False)
        
        # 更新已安装列表
        self.installed_list.clear()
        for env_name, installations in detected.items():
            for inst in installations:
                item_text = f"{inst.name} {inst.version} ({inst.install_method.value})"
                if inst.is_active:
                    item_text += " ✅ [当前]"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, {
                    'name': inst.name,
                    'version': inst.version,
                    'path': inst.install_path,
                })
                self.installed_list.addItem(item)
        
        total = sum(len(v) for v in detected.values())
        self.log(f"检测完成，共发现 {total} 个已安装环境")
    
    def show_installed_context_menu(self, pos):
        item = self.installed_list.itemAt(pos)
        if not item:
            return
        
        menu = QMenu()
        
        uninstall_action = menu.addAction("🗑️ 卸载")
        activate_action = menu.addAction("✅ 设为默认版本")
        menu.addSeparator()
        open_dir_action = menu.addAction("📁 打开安装目录")
        
        action = menu.exec_(self.installed_list.mapToGlobal(pos))
        
        data = item.data(Qt.UserRole)
        
        if action == uninstall_action:
            self.uninstall_env(data['name'], data['version'])
        elif action == activate_action:
            self.set_version_active(data['name'], data['version'])
        elif action == open_dir_action:
            os.startfile(data['path'])
    
    def uninstall_selected(self):
        item = self.installed_list.currentItem()
        if not item:
            return
        
        data = item.data(Qt.UserRole)
        self.uninstall_env(data['name'], data['version'])
    
    def uninstall_env(self, name: str, version: str):
        reply = QMessageBox.question(
            self, "确认卸载",
            f"确定要卸载 {name} {version} 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success, message = self.lifecycle_manager.uninstall(name, version)
            if success:
                QMessageBox.information(self, "卸载成功", message)
            else:
                QMessageBox.warning(self, "卸载失败", message)
            self.check_installed_environments()
    
    def set_active_version(self):
        item = self.installed_list.currentItem()
        if not item:
            return
        
        data = item.data(Qt.UserRole)
        self.set_version_active(data['name'], data['version'])
    
    def set_version_active(self, name: str, version: str):
        success, message = self.lifecycle_manager.set_active_version(name, version)
        if success:
            QMessageBox.information(self, "成功", message)
            self.check_installed_environments()
        else:
            QMessageBox.warning(self, "失败", message)
    
    def show_settings(self):
        dialog = SettingsDialog(self.mirror_manager, self)
        dialog.exec_()
    
    def show_template_dialog(self):
        dialog = TemplateDialog(self.template_manager, self)
        dialog.template_selected.connect(self.apply_template)
        dialog.exec_()
    
    def apply_template(self, template_name: str):
        template = self.template_manager.get_template(template_name)
        if not template:
            return
        
        # 清除当前选择
        for card in self.env_cards.values():
            card.select_checkbox.setChecked(False)
        
        # 应用模板选择
        for env_spec in template.environments:
            if env_spec.name in self.env_cards:
                card = self.env_cards[env_spec.name]
                card.select_checkbox.setChecked(True)
                # 设置版本
                index = card.version_combo.findData(env_spec.version)
                if index >= 0:
                    card.version_combo.setCurrentIndex(index)
        
        self.log(f"已应用模板: {template.name}")
    
    def apply_selected_template(self):
        item = self.template_list.currentItem()
        if item:
            self.apply_template(item.data(Qt.UserRole))
    
    def import_template(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择模板文件", "",
            "JSON文件 (*.json);;YAML文件 (*.yaml *.yml)"
        )
        if filepath:
            template = self.template_manager.load_template(filepath)
            if template:
                QMessageBox.information(self, "成功", f"已导入模板: {template.name}")
            else:
                QMessageBox.warning(self, "错误", "模板格式错误")
    
    def export_current_as_template(self):
        selections = []
        for env_name, card in self.env_cards.items():
            if card.is_selected():
                selections.append({
                    'name': env_name,
                    'version': card.get_selected_version(),
                })
        
        if not selections:
            QMessageBox.warning(self, "提示", "请先选择要导出的环境")
            return
        
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存模板", "my_template.json",
            "JSON文件 (*.json)"
        )
        
        if filepath:
            template = self.template_manager.create_from_selection(
                "custom", "自定义模板", selections
            )
            self.template_manager.save_template(template, filepath)
            QMessageBox.information(self, "成功", "模板已导出")
    
    def start_install(self):
        """开始安装"""
        selected = []
        for env_name, card in self.env_cards.items():
            if card.is_selected():
                selected.append({
                    'name': env_name,
                    'version': card.get_selected_version(),
                    'mirror': card.get_selected_mirror(),
                })
        
        if not selected:
            QMessageBox.warning(self, "提示", "请至少选择一个开发环境进行安装！")
            return
        
        env_names = ", ".join([s['name'] for s in selected])
        reply = QMessageBox.question(
            self, "确认安装",
            f"即将安装以下环境：\n{env_names}\n\n是否继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        # TODO: 实现新的安装逻辑
        self.log(f"开始安装 {len(selected)} 个环境...")
        QMessageBox.information(
            self, "功能开发中",
            "新版安装器正在集成中，敬请期待！\n"
            "已集成：动态版本获取、镜像源选择、断点续传、安装回滚等功能。"
        )
    
    def log(self, message: str):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def save_log(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存日志", "easyenv_log.txt",
            "文本文件 (*.txt)"
        )
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(self.log_text.toPlainText())
            QMessageBox.information(self, "成功", "日志已保存")
