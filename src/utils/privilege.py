#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
权限管理器 - 处理管理员权限检测和提升
"""

import os
import sys
import ctypes
import subprocess
from typing import Tuple


class PrivilegeManager:
    """权限管理器"""
    
    @staticmethod
    def is_admin() -> bool:
        """检查是否具有管理员权限"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            return False
    
    @staticmethod
    def run_as_admin(args: list = None, wait: bool = False) -> Tuple[bool, int]:
        """
        以管理员权限重新运行程序
        
        Args:
            args: 命令行参数
            wait: 是否等待程序结束
            
        Returns:
            (success, return_code)
        """
        try:
            # 获取当前 Python 解释器和脚本路径
            if getattr(sys, 'frozen', False):
                # PyInstaller 打包后的 exe
                executable = sys.executable
                params = ' '.join(args) if args else ''
            else:
                # Python 脚本
                executable = sys.executable
                script = os.path.abspath(sys.argv[0])
                params = f'"{script}"'
                if args:
                    params += ' ' + ' '.join(args)
            
            # 使用 ShellExecuteW 以管理员权限运行
            result = ctypes.windll.shell32.ShellExecuteW(
                None,           # hwnd
                "runas",        # 请求提升权限
                executable,     # 程序路径
                params,         # 参数
                None,           # 工作目录
                1               # SW_SHOWNORMAL
            )
            
            # ShellExecuteW 返回值 > 32 表示成功
            if result > 32:
                return True, 0
            else:
                return False, result
                
        except Exception as e:
            return False, -1
    
    @staticmethod
    def ensure_admin(exit_on_fail: bool = True) -> bool:
        """
        确保以管理员权限运行，否则提升权限重新运行
        
        Args:
            exit_on_fail: 提升权限后是否退出当前进程
            
        Returns:
            是否具有管理员权限
        """
        if PrivilegeManager.is_admin():
            return True
        
        # 尝试提升权限
        success, _ = PrivilegeManager.run_as_admin()
        
        if success:
            if exit_on_fail:
                sys.exit(0)
            return False
        else:
            # 用户拒绝或提升失败
            return False
    
    @staticmethod
    def can_write_to_program_files() -> bool:
        """检查是否可以写入 Program Files"""
        test_path = os.path.join(
            os.environ.get('PROGRAMFILES', 'C:\\Program Files'),
            'easyenv_test_permission'
        )
        try:
            os.makedirs(test_path, exist_ok=True)
            os.rmdir(test_path)
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_recommended_install_dir() -> str:
        """获取推荐的安装目录"""
        if PrivilegeManager.is_admin():
            return os.environ.get('PROGRAMFILES', 'C:\\Program Files')
        else:
            return os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
    
    @staticmethod
    def check_uac_enabled() -> bool:
        """检查 UAC 是否启用"""
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
            ) as key:
                enable_lua, _ = winreg.QueryValueEx(key, "EnableLUA")
                return bool(enable_lua)
        except Exception:
            return True  # 默认假设启用


class UACPrompt:
    """UAC 提示对话框"""
    
    @staticmethod
    def show_prompt(title: str = "需要管理员权限", 
                   message: str = "此操作需要管理员权限才能继续。") -> bool:
        """
        显示 UAC 提示
        
        Returns:
            用户是否同意提升权限
        """
        try:
            # 使用 MessageBox 显示提示
            result = ctypes.windll.user32.MessageBoxW(
                None,
                message,
                title,
                0x00000001 | 0x00000030  # MB_OKCANCEL | MB_ICONWARNING
            )
            return result == 1  # IDOK
        except Exception:
            return True
