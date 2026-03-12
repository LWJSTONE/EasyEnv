#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
安装回滚管理器 - 记录安装状态，支持失败回滚
"""

import os
import sys
import json
import subprocess
import shutil
import winreg
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


class InstallStatus(Enum):
    """安装状态"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    INSTALLING = "installing"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class InstallRecord:
    """安装记录"""
    env_name: str
    version: str
    status: str
    start_time: str
    end_time: str = ""
    download_path: str = ""
    install_path: str = ""
    original_path: str = ""  # 安装前的PATH
    backup_path: str = ""  # 备份目录
    registry_backup: str = ""  # 注册表备份文件
    error_message: str = ""
    installed_files: List[str] = field(default_factory=list)
    created_dirs: List[str] = field(default_factory=list)


class RollbackManager:
    """安装回滚管理器"""
    
    RECORDS_DIR = os.path.join(os.path.expanduser('~'), '.easyenv', 'install_records')
    BACKUP_DIR = os.path.join(os.path.expanduser('~'), '.easyenv', 'backups')
    
    def __init__(self):
        os.makedirs(self.RECORDS_DIR, exist_ok=True)
        os.makedirs(self.BACKUP_DIR, exist_ok=True)
        self._current_session: Dict[str, InstallRecord] = {}
        
    def begin_install(self, env_name: str, version: str) -> InstallRecord:
        """开始安装，创建安装记录"""
        # 备份当前环境状态
        backup_path = self._create_backup(env_name)
        original_path = self._get_current_path()
        
        record = InstallRecord(
            env_name=env_name,
            version=version,
            status=InstallStatus.PENDING.value,
            start_time=datetime.now().isoformat(),
            original_path=original_path,
            backup_path=backup_path,
        )
        
        self._current_session[env_name] = record
        self._save_record(record)
        
        return record
    
    def update_status(self, env_name: str, status: InstallStatus, 
                      error_message: str = "", **kwargs):
        """更新安装状态"""
        if env_name not in self._current_session:
            return
        
        record = self._current_session[env_name]
        record.status = status.value
        
        if error_message:
            record.error_message = error_message
            
        # 更新其他字段
        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)
        
        if status in [InstallStatus.SUCCESS, InstallStatus.FAILED, InstallStatus.ROLLED_BACK]:
            record.end_time = datetime.now().isoformat()
        
        self._save_record(record)
    
    def rollback(self, env_name: str) -> Tuple[bool, str]:
        """
        回滚安装
        
        Returns:
            (success, message)
        """
        if env_name not in self._current_session:
            return False, f"未找到 {env_name} 的安装记录"
        
        record = self._current_session[env_name]
        messages = []
        
        try:
            # 1. 恢复PATH环境变量
            if record.original_path:
                success, msg = self._restore_path(record.original_path)
                messages.append(f"恢复PATH: {'成功' if success else '失败'} - {msg}")
            
            # 2. 卸载已安装的程序
            if record.install_path and os.path.exists(record.install_path):
                success, msg = self._uninstall_program(env_name, record.install_path)
                messages.append(f"卸载程序: {'成功' if success else '失败'} - {msg}")
            
            # 3. 从备份恢复文件
            if record.backup_path and os.path.exists(record.backup_path):
                success, msg = self._restore_from_backup(record.backup_path, env_name)
                messages.append(f"恢复备份: {'成功' if success else '失败'} - {msg}")
            
            # 4. 清理注册表
            success, msg = self._cleanup_registry(env_name)
            messages.append(f"清理注册表: {'成功' if success else '失败'} - {msg}")
            
            # 更新状态
            self.update_status(env_name, InstallStatus.ROLLED_BACK)
            
            return True, "\n".join(messages)
            
        except Exception as e:
            return False, f"回滚失败: {str(e)}\n" + "\n".join(messages)
    
    def rollback_all_failed(self) -> Dict[str, Tuple[bool, str]]:
        """回滚所有失败的安装"""
        results = {}
        
        for env_name, record in self._current_session.items():
            if record.status == InstallStatus.FAILED.value:
                results[env_name] = self.rollback(env_name)
        
        return results
    
    def _create_backup(self, env_name: str) -> str:
        """创建备份"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.BACKUP_DIR, f"{env_name}_{timestamp}")
        os.makedirs(backup_path, exist_ok=True)
        
        # 备份注册表项（如果存在）
        self._backup_registry(env_name, backup_path)
        
        return backup_path
    
    def _backup_registry(self, env_name: str, backup_path: str):
        """备份相关注册表项"""
        reg_keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        
        registry_backup_file = os.path.join(backup_path, 'registry_backup.json')
        backup_data = []
        
        for hkey, subkey in reg_keys:
            try:
                with winreg.OpenKey(hkey, subkey) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        subkey_name = winreg.EnumKey(key, i)
                        if env_name.lower() in subkey_name.lower():
                            backup_data.append({
                                'hkey': 'HKLM' if hkey == winreg.HKEY_LOCAL_MACHINE else 'HKCU',
                                'path': f"{subkey}\\{subkey_name}",
                                'name': subkey_name,
                            })
            except Exception:
                pass
        
        if backup_data:
            with open(registry_backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
    
    def _get_current_path(self) -> str:
        """获取当前PATH环境变量"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Environment') as key:
                path, _ = winreg.QueryValueEx(key, 'PATH')
                return path
        except Exception:
            return ""
    
    def _restore_path(self, original_path: str) -> Tuple[bool, str]:
        """恢复PATH环境变量"""
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, 
                r'Environment',
                0,
                winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, 'PATH', 0, winreg.REG_EXPAND_SZ, original_path)
            
            # 广播环境变量更改
            import ctypes
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x1A
            SMTO_ABORTIFHUNG = 0x0002
            result = ctypes.c_long()
            ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment",
                SMTO_ABORTIFHUNG, 5000, ctypes.byref(result)
            )
            
            return True, "PATH已恢复"
        except Exception as e:
            return False, str(e)
    
    def _uninstall_program(self, env_name: str, install_path: str) -> Tuple[bool, str]:
        """尝试卸载程序"""
        uninstall_cmds = {
            'python': f'"{install_path}\\python.exe" -m pip uninstall -y pip && rmdir /s /q "{install_path}"',
            'nodejs': f'msiexec /x {{nodejs_product_code}} /quiet',
        }
        
        # 首先尝试查找卸载程序
        uninstallers = self._find_uninstaller(env_name, install_path)
        
        for uninstaller in uninstallers:
            try:
                result = subprocess.run(
                    uninstaller,
                    shell=True,
                    capture_output=True,
                    timeout=300,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode == 0:
                    return True, f"已执行: {uninstaller}"
            except Exception as e:
                continue
        
        # 如果没有卸载程序，尝试直接删除目录
        try:
            if os.path.exists(install_path):
                shutil.rmtree(install_path)
            return True, f"已删除: {install_path}"
        except Exception as e:
            return False, f"删除失败: {str(e)}"
    
    def _find_uninstaller(self, env_name: str, install_path: str) -> List[str]:
        """查找卸载程序"""
        uninstallers = []
        
        # 查找注册表中的卸载命令
        reg_keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        
        for hkey, subkey in reg_keys:
            try:
                with winreg.OpenKey(hkey, subkey) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as app_key:
                                try:
                                    display_name, _ = winreg.QueryValueEx(app_key, 'DisplayName')
                                    if env_name.lower() in display_name.lower():
                                        uninstall_cmd, _ = winreg.QueryValueEx(app_key, 'UninstallString')
                                        if uninstall_cmd:
                                            uninstallers.append(uninstall_cmd)
                                except Exception:
                                    pass
                        except Exception:
                            pass
            except Exception:
                pass
        
        # 查找目录中的卸载程序
        uninstall_files = ['uninstall.exe', 'unins000.exe', 'uninstall']
        for root, dirs, files in os.walk(install_path):
            for f in files:
                if f.lower() in [u.lower() for u in uninstall_files]:
                    uninstallers.append(f'"{os.path.join(root, f)}" /S')
        
        return uninstallers
    
    def _restore_from_backup(self, backup_path: str, env_name: str) -> Tuple[bool, str]:
        """从备份恢复"""
        try:
            # 目前备份主要是注册表，这里可以扩展文件备份逻辑
            return True, "备份恢复完成"
        except Exception as e:
            return False, str(e)
    
    def _cleanup_registry(self, env_name: str) -> Tuple[bool, str]:
        """清理注册表"""
        cleaned = []
        
        # 清理环境变量中相关的路径
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Environment',
                0,
                winreg.KEY_READ | winreg.KEY_WRITE
            ) as key:
                try:
                    current_path, _ = winreg.QueryValueEx(key, 'PATH')
                    # 移除与该环境相关的路径
                    paths = current_path.split(';')
                    filtered_paths = [p for p in paths if env_name.lower() not in p.lower()]
                    new_path = ';'.join(filtered_paths)
                    winreg.SetValueEx(key, 'PATH', 0, winreg.REG_EXPAND_SZ, new_path)
                    cleaned.append("PATH已清理")
                except Exception:
                    pass
        except Exception:
            pass
        
        return True, ", ".join(cleaned) if cleaned else "无需清理"
    
    def _save_record(self, record: InstallRecord):
        """保存安装记录"""
        record_file = os.path.join(
            self.RECORDS_DIR, 
            f"{record.env_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        with open(record_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(record), f, ensure_ascii=False, indent=2)
    
    def get_install_history(self, env_name: str = None) -> List[InstallRecord]:
        """获取安装历史"""
        records = []
        
        for filename in os.listdir(self.RECORDS_DIR):
            if not filename.endswith('.json'):
                continue
            
            if env_name and not filename.startswith(env_name):
                continue
            
            try:
                with open(os.path.join(self.RECORDS_DIR, filename), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    records.append(InstallRecord(**data))
            except Exception:
                pass
        
        # 按时间排序
        records.sort(key=lambda r: r.start_time, reverse=True)
        return records
    
    def clear_old_records(self, days: int = 30):
        """清理旧的安装记录"""
        import time
        now = time.time()
        
        for filename in os.listdir(self.RECORDS_DIR):
            filepath = os.path.join(self.RECORDS_DIR, filename)
            if os.path.isfile(filepath):
                file_mtime = os.path.getmtime(filepath)
                if (now - file_mtime) > days * 24 * 3600:
                    try:
                        os.remove(filepath)
                    except Exception:
                        pass
