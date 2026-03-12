#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
安装器 - 处理下载和安装过程
"""

import os
import sys
import subprocess
import tempfile
import shutil
from typing import List, Dict
from PyQt5.QtCore import QThread, pyqtSignal
import urllib.request
import urllib.error


class InstallWorker(QThread):
    """安装工作线程"""
    
    progress = pyqtSignal(int, int, str, str)  # current, total, env_name, status
    log = pyqtSignal(str)
    finished = pyqtSignal(int, int)  # success_count, fail_count
    
    def __init__(self, selected_envs: List[Dict], env_manager):
        super().__init__()
        self.selected_envs = selected_envs
        self.env_manager = env_manager
        self._is_running = True
        
    def run(self):
        """执行安装"""
        success_count = 0
        fail_count = 0
        total = len(self.selected_envs)
        
        for index, env in enumerate(self.selected_envs, 1):
            if not self._is_running:
                break
                
            env_name = env['name']
            version = env['version']
            display_name = env['info']['display_name']
            
            self.progress.emit(index, total, display_name, "准备下载...")
            self.log.emit(f"开始安装 {display_name} v{version}")
            
            try:
                success = self.install_environment(env_name, version, display_name)
                if success:
                    success_count += 1
                    self.log.emit(f"✅ {display_name} 安装成功！")
                    self.progress.emit(index, total, display_name, "安装完成")
                else:
                    fail_count += 1
                    self.log.emit(f"❌ {display_name} 安装失败")
                    self.progress.emit(index, total, display_name, "安装失败")
            except Exception as e:
                fail_count += 1
                self.log.emit(f"❌ {display_name} 安装出错: {str(e)}")
                self.progress.emit(index, total, display_name, "安装出错")
                
        self.finished.emit(success_count, fail_count)
        
    def install_environment(self, name: str, version: str, display_name: str) -> bool:
        """安装单个环境"""
        try:
            # 获取下载URL
            download_url = self.env_manager.get_download_url(name, version)
            if not download_url:
                self.log.emit(f"无法获取 {display_name} 的下载链接")
                return False
                
            # 下载安装包
            self.progress.emit(0, 100, display_name, "正在下载...")
            installer_path = self.download_installer(download_url, name, version, display_name)
            
            if not installer_path or not os.path.exists(installer_path):
                self.log.emit(f"{display_name} 下载失败")
                return False
                
            # 执行安装
            self.progress.emit(0, 100, display_name, "正在安装...")
            install_args = self.env_manager.get_install_args(name, version)
            success = self.execute_installer(installer_path, install_args, name, display_name)
            
            # 清理安装包
            try:
                if os.path.exists(installer_path):
                    os.remove(installer_path)
                    self.log.emit(f"已清理 {display_name} 安装包")
            except Exception:
                pass
                
            return success
            
        except Exception as e:
            self.log.emit(f"安装 {display_name} 时发生错误: {str(e)}")
            return False
            
    def download_installer(self, url: str, name: str, version: str, display_name: str) -> str:
        """下载安装包"""
        try:
            # 确定文件扩展名
            if url.endswith('.exe'):
                ext = '.exe'
            elif url.endswith('.msi'):
                ext = '.msi'
            elif url.endswith('.zip'):
                ext = '.zip'
            elif url.endswith('.7z'):
                ext = '.7z'
            else:
                ext = '.exe'  # 默认
                
            # 创建下载路径
            filename = f"{name}_{version}{ext}"
            download_path = os.path.join(self.env_manager.download_dir, filename)
            
            # 如果已存在，直接返回
            if os.path.exists(download_path):
                self.log.emit(f"使用已缓存的 {display_name} 安装包")
                return download_path
                
            self.log.emit(f"正在下载 {display_name}...")
            self.log.emit(f"下载地址: {url}")
            
            # 下载文件
            def progress_callback(block_num, block_size, total_size):
                if total_size > 0:
                    downloaded = block_num * block_size
                    percent = min(100, int((downloaded / total_size) * 100))
                    self.progress.emit(0, 100, display_name, f"下载中 {percent}%")
                    
            urllib.request.urlretrieve(url, download_path, progress_callback)
            
            self.log.emit(f"{display_name} 下载完成")
            return download_path
            
        except urllib.error.URLError as e:
            self.log.emit(f"下载失败: 网络错误 - {str(e)}")
            return ""
        except Exception as e:
            self.log.emit(f"下载失败: {str(e)}")
            return ""
            
    def execute_installer(self, installer_path: str, install_args: List[str], name: str, display_name: str) -> bool:
        """执行安装程序"""
        try:
            if not os.path.exists(installer_path):
                self.log.emit(f"安装包不存在: {installer_path}")
                return False
                
            self.log.emit(f"正在安装 {display_name}...")
            self.log.emit(f"安装包路径: {installer_path}")
            self.log.emit(f"安装参数: {' '.join(install_args)}")
            
            # 根据文件类型选择安装方式
            if installer_path.endswith('.msi'):
                # MSI 安装
                cmd = ['msiexec', '/i', installer_path] + install_args
            elif installer_path.endswith('.zip'):
                # ZIP 解压安装
                return self.install_from_zip(installer_path, name, display_name)
            elif installer_path.endswith('.7z'):
                # 7z 解压安装
                return self.install_from_7z(installer_path, name, display_name)
            else:
                # EXE 安装
                cmd = [installer_path] + install_args
                
            # 执行安装命令
            self.log.emit(f"执行安装命令...")
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            # 等待安装完成
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                self.log.emit(f"{display_name} 安装进程完成")
                return True
            else:
                error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "未知错误"
                self.log.emit(f"{display_name} 安装返回非零: {process.returncode}")
                self.log.emit(f"错误信息: {error_msg}")
                return False
                
        except Exception as e:
            self.log.emit(f"执行安装程序时出错: {str(e)}")
            return False
            
    def install_from_zip(self, zip_path: str, name: str, display_name: str) -> bool:
        """从 ZIP 文件安装"""
        try:
            import zipfile
            
            self.log.emit(f"正在解压 {display_name}...")
            
            # 确定安装目录
            install_dir = self.env_manager.get_install_dir(name)
            if not install_dir:
                install_dir = os.path.join(os.environ.get('PROGRAMFILES', ''), name)
                
            # 解压到临时目录
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 检查是否有单一根目录
                namelist = zip_ref.namelist()
                if namelist and namelist[0].endswith('/'):
                    # 解压到父目录
                    extract_dir = os.path.dirname(install_dir)
                else:
                    extract_dir = install_dir
                    
                zip_ref.extractall(extract_dir)
                
            self.log.emit(f"{display_name} 解压完成")
            return True
            
        except Exception as e:
            self.log.emit(f"解压安装失败: {str(e)}")
            return False
            
    def install_from_7z(self, archive_path: str, name: str, display_name: str) -> bool:
        """从 7z 文件安装"""
        try:
            self.log.emit(f"正在解压 {display_name} (需要7-Zip)...")
            
            # 查找 7z
            seven_zip_paths = [
                r"C:\Program Files\7-Zip\7z.exe",
                r"C:\Program Files (x86)\7-Zip\7z.exe",
                "7z"  # 假设在 PATH 中
            ]
            
            seven_zip = None
            for path in seven_zip_paths:
                if os.path.exists(path) or shutil.which(path):
                    seven_zip = path
                    break
                    
            if not seven_zip:
                self.log.emit("未找到 7-Zip，请先安装 7-Zip")
                return False
                
            # 确定安装目录
            install_dir = self.env_manager.get_install_dir(name)
            if not install_dir:
                install_dir = os.path.join(os.environ.get('PROGRAMFILES', ''), name)
                
            # 执行解压
            cmd = [seven_zip, 'x', archive_path, f'-o{os.path.dirname(install_dir)}', '-y']
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                self.log.emit(f"{display_name} 解压完成")
                return True
            else:
                self.log.emit(f"{display_name} 解压失败")
                return False
                
        except Exception as e:
            self.log.emit(f"7z 解压失败: {str(e)}")
            return False
            
    def stop(self):
        """停止安装"""
        self._is_running = False
