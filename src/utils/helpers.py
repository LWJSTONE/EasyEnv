#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
辅助函数模块
"""

import os
import sys
from datetime import datetime


def get_resource_path(relative_path: str) -> str:
    """获取资源文件的绝对路径（支持PyInstaller打包）"""
    try:
        # PyInstaller 创建的临时目录
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
    return os.path.join(base_path, relative_path)


def get_app_data_dir() -> str:
    """获取应用数据目录"""
    app_data = os.path.join(os.path.expanduser('~'), '.easyenv')
    os.makedirs(app_data, exist_ok=True)
    return app_data


def get_download_dir() -> str:
    """获取下载目录"""
    download_dir = os.path.join(get_app_data_dir(), 'downloads')
    os.makedirs(download_dir, exist_ok=True)
    return download_dir


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def format_duration(seconds: float) -> str:
    """格式化持续时间"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}分钟"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}小时"


def get_current_timestamp() -> str:
    """获取当前时间戳字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_admin_privileges() -> bool:
    """检查是否具有管理员权限"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run_as_admin():
    """以管理员权限重新运行"""
    try:
        import ctypes
        if sys.platform == 'win32':
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, " ".join(sys.argv), None, 1
            )
    except Exception:
        pass


def is_windows() -> bool:
    """检查是否为 Windows 系统"""
    return sys.platform.startswith('win')


def get_system_info() -> dict:
    """获取系统信息"""
    import platform
    
    info = {
        'system': platform.system(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'python_version': platform.python_version(),
    }
    
    if is_windows():
        try:
            import ctypes
            info['is_admin'] = ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            info['is_admin'] = False
            
    return info


def clean_old_downloads(days: int = 30):
    """清理旧的下载文件"""
    download_dir = get_download_dir()
    if not os.path.exists(download_dir):
        return
        
    now = datetime.now()
    for filename in os.listdir(download_dir):
        filepath = os.path.join(download_dir, filename)
        if os.path.isfile(filepath):
            file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            if (now - file_mtime).days > days:
                try:
                    os.remove(filepath)
                except Exception:
                    pass


def create_desktop_shortcut(name: str, target: str, icon: str = None):
    """创建桌面快捷方式"""
    if not is_windows():
        return False
        
    try:
        import win32com.client
        
        desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
        shortcut_path = os.path.join(desktop, f"{name}.lnk")
        
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = target
        if icon:
            shortcut.IconLocation = icon
        shortcut.save()
        
        return True
    except Exception:
        return False


def add_to_path(directory: str) -> bool:
    """将目录添加到系统 PATH"""
    if not is_windows():
        return False
        
    try:
        import winreg
        
        # 打开环境变量注册表键
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Environment',
            0,
            winreg.KEY_READ | winreg.KEY_WRITE
        )
        
        # 获取当前 PATH
        try:
            current_path, _ = winreg.QueryValueEx(key, 'PATH')
        except FileNotFoundError:
            current_path = ''
            
        # 检查是否已存在
        if directory.lower() in current_path.lower():
            winreg.CloseKey(key)
            return True
            
        # 添加新路径
        new_path = f"{current_path};{directory}" if current_path else directory
        winreg.SetValueEx(key, 'PATH', 0, winreg.REG_EXPAND_SZ, new_path)
        winreg.CloseKey(key)
        
        return True
    except Exception:
        return False
