#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
核心安装引擎 - 深度实现 Python 和 Node.js 安装
支持CLI/API调用，与UI解耦
"""

import os
import sys
import json
import subprocess
import shutil
import tempfile
import re
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod
from enum import Enum

from .errors import (
    ErrorCode, EasyEnvError, get_logger, 
    AuditLogger, TransactionManager
)
from .security import SecurityVerifier, SecureDownloader, PackageInfo


class InstallMode(Enum):
    """安装模式"""
    USER_ONLY = "user_only"      # 仅当前用户
    SYSTEM_WIDE = "system_wide"  # 系统范围（需要管理员权限）
    DRY_RUN = "dry_run"          # 模拟运行，不实际修改系统


@dataclass
class InstallConfig:
    """安装配置"""
    env_name: str
    version: str
    mode: InstallMode = InstallMode.USER_ONLY
    install_dir: Optional[str] = None
    add_to_path: bool = True
    create_symlinks: bool = True
    mirror: str = "auto"
    verify_checksum: bool = True
    timeout: int = 600  # 安装超时（秒）


@dataclass
class InstallResult:
    """安装结果"""
    success: bool
    env_name: str
    version: str
    install_path: str = ""
    error_code: Optional[ErrorCode] = None
    error_message: str = ""
    duration: float = 0.0
    rollback_performed: bool = False
    audit_records: List[Dict] = field(default_factory=list)


class BaseInstaller(ABC):
    """安装器基类"""
    
    def __init__(self, config: InstallConfig):
        self.config = config
        self.logger = get_logger()
        self.audit = AuditLogger()
        self.verifier = SecurityVerifier()
        self.transaction: Optional[TransactionManager] = None
        self._start_time: float = 0
    
    def install(self, progress_callback: Callable = None) -> InstallResult:
        """
        执行安装流程
        
        Args:
            progress_callback: 进度回调函数 (stage, progress, message)
        """
        self._start_time = datetime.now().timestamp()
        
        # 创建事务
        self.transaction = TransactionManager(
            name=f"{self.config.env_name}_{self.config.version}",
            audit_logger=self.audit
        )
        
        try:
            # 预检查
            self._pre_install_check(progress_callback)
            
            # 准备安装
            download_path = self._prepare_installer(progress_callback)
            
            # 执行安装
            self._execute_install(download_path, progress_callback)
            
            # 后处理
            self._post_install(progress_callback)
            
            # 完成事务
            results = self.transaction.execute()
            
            duration = datetime.now().timestamp() - self._start_time
            
            return InstallResult(
                success=True,
                env_name=self.config.env_name,
                version=self.config.version,
                install_path=self.config.install_dir or "",
                duration=duration,
                audit_records=self.audit.get_operations(10)
            )
            
        except EasyEnvError as e:
            return self._handle_install_failure(e)
        except Exception as e:
            error = EasyEnvError(
                ErrorCode.UNKNOWN_ERROR,
                details=str(e),
                context={"env": self.config.env_name}
            )
            return self._handle_install_failure(error)
    
    def _handle_install_failure(self, error: EasyEnvError) -> InstallResult:
        """处理安装失败"""
        self.logger.error(f"安装失败: {self.config.env_name}", error=error)
        
        duration = datetime.now().timestamp() - self._start_time
        
        return InstallResult(
            success=False,
            env_name=self.config.env_name,
            version=self.config.version,
            error_code=error.error_code,
            error_message=error.error_info.to_user_message(),
            duration=duration,
            rollback_performed=False,
            audit_records=self.audit.get_operations(10)
        )
    
    def _pre_install_check(self, progress_callback=None):
        """安装前检查"""
        self._notify_progress(progress_callback, "precheck", 0, "执行安装前检查...")
        
        # 检查是否已安装
        installed = self._check_existing_installation()
        if installed:
            raise EasyEnvError(
                ErrorCode.INSTALL_ALREADY_EXISTS,
                details=f"{self.config.env_name} {self.config.version} 已安装",
                context={"install_path": installed}
            )
        
        # 检查磁盘空间
        is_sufficient, available = self.verifier.check_disk_space(500)
        if not is_sufficient:
            raise EasyEnvError(
                ErrorCode.DISK_SPACE_INSUFFICIENT,
                details=f"可用空间: {available}MB"
            )
        
        # 检查权限（如果需要系统级安装）
        if self.config.mode == InstallMode.SYSTEM_WIDE:
            self._check_admin_privilege()
        
        self._notify_progress(progress_callback, "precheck", 100, "检查通过")
    
    @abstractmethod
    def _prepare_installer(self, progress_callback=None) -> str:
        """准备安装程序（下载或获取缓存）"""
        pass
    
    @abstractmethod
    def _execute_install(self, installer_path: str, progress_callback=None):
        """执行安装"""
        pass
    
    @abstractmethod
    def _post_install(self, progress_callback=None):
        """安装后处理"""
        pass
    
    @abstractmethod
    def _check_existing_installation(self) -> Optional[str]:
        """检查是否已安装，返回安装路径或None"""
        pass
    
    def _check_admin_privilege(self):
        """检查管理员权限"""
        import ctypes
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if not is_admin:
                raise EasyEnvError(
                    ErrorCode.PERMISSION_DENIED,
                    details="系统级安装需要管理员权限"
                )
        except AttributeError:
            # 非Windows系统
            pass
    
    def _notify_progress(self, callback, stage: str, progress: int, message: str):
        """通知进度"""
        if callback:
            try:
                callback(stage, progress, message)
            except Exception:
                pass
    
    def _get_download_dir(self) -> str:
        """获取下载目录"""
        return os.path.join(os.path.expanduser('~'), '.easyenv', 'downloads')
    
    def _get_install_dir(self) -> str:
        """获取安装目录"""
        if self.config.install_dir:
            return self.config.install_dir
        
        # 根据安装模式选择目录
        if self.config.mode == InstallMode.SYSTEM_WIDE:
            return os.path.join(
                os.environ.get('PROGRAMFILES', 'C:\\Program Files'),
                self.config.env_name
            )
        else:
            return os.path.join(
                os.environ.get('LOCALAPPDATA', os.path.expanduser('~')),
                'Programs',
                self.config.env_name
            )


class PythonInstaller(BaseInstaller):
    """Python 安装器 - 深度实现"""
    
    # Python官方下载源
    DOWNLOAD_TEMPLATE = "https://www.python.org/ftp/python/{version}/python-{version}-amd64.exe"
    
    # 国内镜像
    MIRROR_TEMPLATES = {
        'npmmirror': 'https://registry.npmmirror.com/python-binaries/download/{version}/python-{version}-amd64.exe',
        'huawei': 'https://mirrors.huaweicloud.com/python/{version}/python-{version}-amd64.exe',
    }
    
    def _get_download_url(self) -> str:
        """获取下载URL"""
        version = self.config.version
        
        if self.config.mirror in self.MIRROR_TEMPLATES:
            return self.MIRROR_TEMPLATES[self.config.mirror].format(version=version)
        
        return self.DOWNLOAD_TEMPLATE.format(version=version)
    
    def _check_existing_installation(self) -> Optional[str]:
        """检查Python是否已安装"""
        # 检查注册表
        import winreg
        
        for root in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            try:
                key_path = r"SOFTWARE\Python\PythonCore"
                with winreg.OpenKey(root, key_path) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        version_key = winreg.EnumKey(key, i)
                        if version_key.startswith(self.config.version.split('.')[0]):
                            with winreg.OpenKey(key, f"{version_key}\\InstallPath") as subkey:
                                return winreg.QueryValueEx(subkey, "")[0]
            except (FileNotFoundError, PermissionError):
                pass
        
        # 检查目标目录
        install_dir = self._get_install_dir()
        python_exe = os.path.join(install_dir, 'python.exe')
        if os.path.exists(python_exe):
            return install_dir
        
        return None
    
    def _prepare_installer(self, progress_callback=None) -> str:
        """下载Python安装程序"""
        self._notify_progress(progress_callback, "download", 0, "准备下载Python安装程序...")
        
        download_dir = self._get_download_dir()
        os.makedirs(download_dir, exist_ok=True)
        
        filename = f"python-{self.config.version}-amd64.exe"
        filepath = os.path.join(download_dir, filename)
        
        # 检查缓存
        if os.path.exists(filepath):
            self.logger.info(f"使用缓存的安装程序: {filepath}")
            self._notify_progress(progress_callback, "download", 100, "使用缓存文件")
            return filepath
        
        # 下载
        url = self._get_download_url()
        
        package_info = PackageInfo(
            name="python",
            version=self.config.version,
            url=url
        )
        
        downloader = SecureDownloader(self.verifier)
        
        def download_progress(downloaded, total):
            if total > 0:
                percent = int((downloaded / total) * 100)
                self._notify_progress(progress_callback, "download", percent, 
                                     f"下载中 {percent}%")
        
        success, message = downloader.download_with_verification(
            url, filepath, package_info, download_progress
        )
        
        if not success:
            raise EasyEnvError(ErrorCode.DOWNLOAD_FAILED, details=message)
        
        return filepath
    
    def _execute_install(self, installer_path: str, progress_callback=None):
        """执行Python安装"""
        self._notify_progress(progress_callback, "install", 0, "开始安装Python...")
        
        install_dir = self._get_install_dir()
        
        # Python静默安装参数
        args = [
            installer_path,
            '/quiet',
            f'TargetDir={install_dir}',
            'Shortcuts=0',
            'Include_test=0',
        ]
        
        if self.config.mode == InstallMode.SYSTEM_WIDE:
            args.append('InstallAllUsers=1')
        else:
            args.append('InstallAllUsers=0')
        
        if self.config.add_to_path:
            args.append('PrependPath=1')
        
        # 添加事务操作：记录安装前的PATH
        original_path = os.environ.get('PATH', '')
        
        def backup_path(result=None):
            self.logger.info("备份原始PATH")
            return original_path
        
        def restore_path(original):
            self.logger.info("恢复原始PATH")
            # 恢复PATH环境变量
            self._set_user_path(original)
        
        self.transaction.add_operation(
            "backup_path",
            backup_path,
            restore_path,
            "备份原始PATH环境变量"
        )
        
        # 记录将创建的目录
        def create_dir(result=None):
            os.makedirs(install_dir, exist_ok=True)
            return install_dir
        
        def remove_dir(path):
            if os.path.exists(path):
                shutil.rmtree(path)
        
        self.transaction.add_operation(
            "create_install_dir",
            create_dir,
            remove_dir,
            f"创建安装目录: {install_dir}"
        )
        
        # 执行安装（放在事务执行中）
        self._notify_progress(progress_callback, "install", 10, "正在安装...")
        
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                timeout=self.config.timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            if result.returncode != 0:
                error_output = result.stderr.decode('utf-8', errors='ignore')
                raise EasyEnvError(
                    ErrorCode.INSTALL_FAILED,
                    details=f"安装程序返回错误码 {result.returncode}: {error_output}"
                )
            
            self._notify_progress(progress_callback, "install", 100, "安装完成")
            
        except subprocess.TimeoutExpired:
            raise EasyEnvError(
                ErrorCode.INSTALL_TIMEOUT,
                details=f"安装超时（{self.config.timeout}秒）"
            )
    
    def _post_install(self, progress_callback=None):
        """安装后处理"""
        self._notify_progress(progress_callback, "postprocess", 0, "执行安装后配置...")
        
        install_dir = self._get_install_dir()
        
        # 验证安装
        python_exe = os.path.join(install_dir, 'python.exe')
        if not os.path.exists(python_exe):
            raise EasyEnvError(
                ErrorCode.INSTALL_FAILED,
                details="安装后无法找到Python可执行文件"
            )
        
        # 验证版本
        try:
            result = subprocess.run(
                [python_exe, '--version'],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            version_match = re.search(r'Python (\d+\.\d+\.\d+)', result.stdout + result.stderr)
            if version_match:
                installed_version = version_match.group(1)
                if not installed_version.startswith(self.config.version):
                    self.logger.warning(
                        f"安装版本不匹配: 请求 {self.config.version}, 实际 {installed_version}"
                    )
        except Exception as e:
            self.logger.warning(f"无法验证Python版本: {e}")
        
        # 安装pip（如果没有）
        pip_exe = os.path.join(install_dir, 'Scripts', 'pip.exe')
        if not os.path.exists(pip_exe):
            self.logger.info("正在安装pip...")
            try:
                subprocess.run(
                    [python_exe, '-m', 'ensurepip', '--upgrade'],
                    capture_output=True,
                    timeout=120,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
            except Exception as e:
                self.logger.warning(f"pip安装失败: {e}")
        
        self._notify_progress(progress_callback, "postprocess", 100, "配置完成")
    
    def _set_user_path(self, new_path: str):
        """设置用户PATH环境变量"""
        import winreg
        
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Environment',
                0,
                winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, 'PATH', 0, winreg.REG_EXPAND_SZ, new_path)
        except Exception as e:
            self.logger.warning(f"设置PATH失败: {e}")


class NodeJsInstaller(BaseInstaller):
    """Node.js 安装器 - 深度实现"""
    
    DOWNLOAD_TEMPLATE = "https://nodejs.org/dist/v{version}/node-v{version}-x64.msi"
    MIRROR_TEMPLATES = {
        'npmmirror': 'https://npmmirror.com/mirrors/node/v{version}/node-v{version}-x64.msi',
        'tuna': 'https://mirrors.tuna.tsinghua.edu.cn/nodejs-release/v{version}/node-v{version}-x64.msi',
    }
    
    def _get_download_url(self) -> str:
        """获取下载URL"""
        version = self.config.version
        
        if self.config.mirror in self.MIRROR_TEMPLATES:
            return self.MIRROR_TEMPLATES[self.config.mirror].format(version=version)
        
        return self.DOWNLOAD_TEMPLATE.format(version=version)
    
    def _check_existing_installation(self) -> Optional[str]:
        """检查Node.js是否已安装"""
        # 检查node命令
        try:
            result = subprocess.run(
                ['node', '--version'],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            if result.returncode == 0:
                version = result.stdout.strip().lstrip('v')
                if version.startswith(self.config.version.split('.')[0]):
                    # 检查安装路径
                    node_path = shutil.which('node')
                    if node_path:
                        return os.path.dirname(node_path)
        except Exception:
            pass
        
        # 检查默认安装目录
        default_paths = [
            os.path.join(os.environ.get('PROGRAMFILES', ''), 'nodejs'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'nodejs'),
        ]
        
        for path in default_paths:
            node_exe = os.path.join(path, 'node.exe')
            if os.path.exists(node_exe):
                return path
        
        return None
    
    def _prepare_installer(self, progress_callback=None) -> str:
        """下载Node.js安装程序"""
        self._notify_progress(progress_callback, "download", 0, "准备下载Node.js安装程序...")
        
        download_dir = self._get_download_dir()
        os.makedirs(download_dir, exist_ok=True)
        
        filename = f"node-v{self.config.version}-x64.msi"
        filepath = os.path.join(download_dir, filename)
        
        # 检查缓存
        if os.path.exists(filepath):
            self.logger.info(f"使用缓存的安装程序: {filepath}")
            self._notify_progress(progress_callback, "download", 100, "使用缓存文件")
            return filepath
        
        # 下载
        url = self._get_download_url()
        
        package_info = PackageInfo(
            name="nodejs",
            version=self.config.version,
            url=url
        )
        
        downloader = SecureDownloader(self.verifier)
        
        def download_progress(downloaded, total):
            if total > 0:
                percent = int((downloaded / total) * 100)
                self._notify_progress(progress_callback, "download", percent, 
                                     f"下载中 {percent}%")
        
        success, message = downloader.download_with_verification(
            url, filepath, package_info, download_progress
        )
        
        if not success:
            raise EasyEnvError(ErrorCode.DOWNLOAD_FAILED, details=message)
        
        return filepath
    
    def _execute_install(self, installer_path: str, progress_callback=None):
        """执行Node.js安装"""
        self._notify_progress(progress_callback, "install", 0, "开始安装Node.js...")
        
        install_dir = self._get_install_dir()
        
        # MSI静默安装参数
        args = [
            'msiexec',
            '/i', installer_path,
            f'INSTALLDIR={install_dir}',
            '/quiet',
            '/norestart',
        ]
        
        # 记录事务操作
        original_path = os.environ.get('PATH', '')
        
        def backup_path(result=None):
            self.logger.info("备份原始PATH")
            return original_path
        
        def restore_path(original):
            self.logger.info("恢复原始PATH")
            self._set_user_path(original)
        
        self.transaction.add_operation(
            "backup_path",
            backup_path,
            restore_path,
            "备份原始PATH环境变量"
        )
        
        self._notify_progress(progress_callback, "install", 10, "正在安装...")
        
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                timeout=self.config.timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            if result.returncode not in [0, 3010]:  # 3010 表示需要重启
                error_output = result.stderr.decode('utf-8', errors='ignore')
                raise EasyEnvError(
                    ErrorCode.INSTALL_FAILED,
                    details=f"MSI安装返回错误码 {result.returncode}: {error_output}"
                )
            
            self._notify_progress(progress_callback, "install", 100, "安装完成")
            
        except subprocess.TimeoutExpired:
            raise EasyEnvError(
                ErrorCode.INSTALL_TIMEOUT,
                details=f"安装超时（{self.config.timeout}秒）"
            )
    
    def _post_install(self, progress_callback=None):
        """安装后处理"""
        self._notify_progress(progress_callback, "postprocess", 0, "执行安装后配置...")
        
        install_dir = self._get_install_dir()
        
        # 验证安装
        node_exe = os.path.join(install_dir, 'node.exe')
        if not os.path.exists(node_exe):
            # 尝试在默认位置查找
            default_node = os.path.join(
                os.environ.get('PROGRAMFILES', ''), 'nodejs', 'node.exe'
            )
            if os.path.exists(default_node):
                install_dir = os.path.dirname(default_node)
                node_exe = default_node
            else:
                raise EasyEnvError(
                    ErrorCode.INSTALL_FAILED,
                    details="安装后无法找到Node.js可执行文件"
                )
        
        # 验证版本
        try:
            result = subprocess.run(
                [node_exe, '--version'],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            version = result.stdout.strip().lstrip('v')
            self.logger.info(f"已安装Node.js版本: {version}")
        except Exception as e:
            self.logger.warning(f"无法验证Node.js版本: {e}")
        
        # 配置npm镜像（可选）
        npm_exe = os.path.join(install_dir, 'npm.cmd')
        if os.path.exists(npm_exe):
            try:
                # 设置npm镜像
                subprocess.run(
                    [npm_exe, 'config', 'set', 'registry', 'https://registry.npmmirror.com'],
                    capture_output=True,
                    timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                self.logger.info("已配置npm使用国内镜像")
            except Exception as e:
                self.logger.warning(f"配置npm镜像失败: {e}")
        
        self._notify_progress(progress_callback, "postprocess", 100, "配置完成")
    
    def _set_user_path(self, new_path: str):
        """设置用户PATH环境变量"""
        import winreg
        
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Environment',
                0,
                winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, 'PATH', 0, winreg.REG_EXPAND_SZ, new_path)
        except Exception as e:
            self.logger.warning(f"设置PATH失败: {e}")


class InstallEngine:
    """安装引擎 - 统一入口"""
    
    INSTALLERS = {
        'python': PythonInstaller,
        'nodejs': NodeJsInstaller,
    }
    
    def __init__(self):
        self.logger = get_logger()
        self.audit = AuditLogger()
    
    def get_supported_environments(self) -> List[str]:
        """获取支持的环境列表"""
        return list(self.INSTALLERS.keys())
    
    def install(self, config: InstallConfig, 
                progress_callback: Callable = None) -> InstallResult:
        """
        执行安装
        
        Args:
            config: 安装配置
            progress_callback: 进度回调 (stage, progress, message)
                              stage: precheck, download, install, postprocess
        
        Returns:
            InstallResult
        """
        installer_class = self.INSTALLERS.get(config.env_name)
        
        if not installer_class:
            return InstallResult(
                success=False,
                env_name=config.env_name,
                version=config.version,
                error_code=ErrorCode.INVALID_ARGUMENT,
                error_message=f"不支持的环境: {config.env_name}"
            )
        
        # 记录审计日志
        self.audit.log_operation(
            operation="install_start",
            target=f"{config.env_name}@{config.version}",
            details={"mode": config.mode.value, "mirror": config.mirror},
            success=True
        )
        
        installer = installer_class(config)
        result = installer.install(progress_callback)
        
        # 记录安装结果
        self.audit.log_operation(
            operation="install_complete",
            target=f"{config.env_name}@{config.version}",
            details={
                "success": result.success,
                "install_path": result.install_path,
                "duration": result.duration
            },
            success=result.success
        )
        
        return result
    
    def uninstall(self, env_name: str, version: str = None,
                  progress_callback: Callable = None) -> Tuple[bool, str]:
        """
        卸载环境
        
        Returns:
            (success, message)
        """
        # TODO: 实现卸载逻辑
        return False, "卸载功能尚未实现"
    
    def check_installed(self, env_name: str) -> Tuple[bool, str]:
        """
        检查环境是否已安装
        
        Returns:
            (is_installed, version_or_path)
        """
        config = InstallConfig(env_name=env_name, version="")
        installer_class = self.INSTALLERS.get(env_name)
        
        if not installer_class:
            return False, ""
        
        installer = installer_class(config)
        path = installer._check_existing_installation()
        
        if path:
            return True, path
        return False, ""
