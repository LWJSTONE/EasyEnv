#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
环境生命周期管理器 - 卸载、升级、多版本管理
"""

import os
import sys
import re
import subprocess
import shutil
import winreg
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class InstallMethod(Enum):
    """安装方式"""
    OFFICIAL = "official"  # 官方安装包
    PYENV = "pyenv"        # pyenv-win
    NVM = "nvm"            # nvm-windows
    RUSTUP = "rustup"      # rustup
    SDKMAN = "sdkman"      # sdkman (WSL)
    MANUAL = "manual"      # 手动安装


@dataclass
class InstalledEnvironment:
    """已安装环境信息"""
    name: str
    version: str
    install_path: str
    install_method: InstallMethod
    install_date: str = ""
    size: int = 0
    is_active: bool = True  # 是否是当前激活版本


class EnvironmentLifecycleManager:
    """环境生命周期管理器"""
    
    def __init__(self):
        self._detected_envs: Dict[str, List[InstalledEnvironment]] = {}
        
    def detect_all_installed(self) -> Dict[str, List[InstalledEnvironment]]:
        """检测所有已安装的开发环境"""
        self._detected_envs = {
            'python': self._detect_python_installations(),
            'nodejs': self._detect_nodejs_installations(),
            'git': self._detect_git_installations(),
            'jdk': self._detect_jdk_installations(),
            'go': self._detect_go_installations(),
            'rust': self._detect_rust_installations(),
            'vscode': self._detect_vscode_installations(),
            'cmake': self._detect_cmake_installations(),
            'docker': self._detect_docker_installations(),
        }
        return self._detected_envs
    
    def _detect_python_installations(self) -> List[InstalledEnvironment]:
        """检测 Python 安装"""
        installations = []
        
        # 检查 pyenv-win
        pyenv_root = os.environ.get('PYENV_ROOT', 
            os.path.join(os.path.expanduser('~'), '.pyenv', 'pyenv-win'))
        if os.path.exists(pyenv_root):
            versions_dir = os.path.join(pyenv_root, 'versions')
            if os.path.exists(versions_dir):
                for version in os.listdir(versions_dir):
                    version_path = os.path.join(versions_dir, version)
                    if os.path.exists(os.path.join(version_path, 'python.exe')):
                        installations.append(InstalledEnvironment(
                            name='python',
                            version=version,
                            install_path=version_path,
                            install_method=InstallMethod.PYENV,
                        ))
        
        # 检查官方安装
        program_files = os.environ.get('LOCALAPPDATA', '')
        python_dir = os.path.join(program_files, 'Programs', 'Python')
        if os.path.exists(python_dir):
            for item in os.listdir(python_dir):
                if item.startswith('Python'):
                    version_match = re.search(r'Python(\d+)(\d+)?', item)
                    if version_match:
                        version = f"{version_match.group(1)}.{version_match.group(2) or '0'}"
                        installations.append(InstalledEnvironment(
                            name='python',
                            version=version,
                            install_path=os.path.join(python_dir, item),
                            install_method=InstallMethod.OFFICIAL,
                        ))
        
        # 通过命令行检测当前激活版本
        try:
            result = subprocess.run(
                ['python', '--version'],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                version = re.search(r'Python (\d+\.\d+\.\d+)', result.stdout or result.stderr)
                if version:
                    for inst in installations:
                        if inst.version.startswith(f"{version.group(1).rsplit('.', 1)[0]}"):
                            inst.is_active = True
        except Exception:
            pass
        
        return installations
    
    def _detect_nodejs_installations(self) -> List[InstalledEnvironment]:
        """检测 Node.js 安装"""
        installations = []
        
        # 检查 nvm-windows
        nvm_home = os.environ.get('NVM_HOME', '')
        if nvm_home and os.path.exists(nvm_home):
            for item in os.listdir(nvm_home):
                if re.match(r'v?\d+\.\d+\.\d+', item):
                    node_path = os.path.join(nvm_home, item)
                    if os.path.exists(os.path.join(node_path, 'node.exe')):
                        installations.append(InstalledEnvironment(
                            name='nodejs',
                            version=item.lstrip('v'),
                            install_path=node_path,
                            install_method=InstallMethod.NVM,
                        ))
        
        # 检查官方安装
        program_files = os.environ.get('PROGRAMFILES', '')
        nodejs_dir = os.path.join(program_files, 'nodejs')
        if os.path.exists(nodejs_dir):
            try:
                result = subprocess.run(
                    [os.path.join(nodejs_dir, 'node.exe'), '--version'],
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode == 0:
                    version = result.stdout.strip().lstrip('v')
                    installations.append(InstalledEnvironment(
                        name='nodejs',
                        version=version,
                        install_path=nodejs_dir,
                        install_method=InstallMethod.OFFICIAL,
                    ))
            except Exception:
                pass
        
        return installations
    
    def _detect_git_installations(self) -> List[InstalledEnvironment]:
        """检测 Git 安装"""
        installations = []
        
        for base_path in [
            os.environ.get('PROGRAMFILES', ''),
            os.environ.get('PROGRAMFILES(X86)', ''),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs'),
        ]:
            if not base_path:
                continue
            git_dir = os.path.join(base_path, 'Git')
            if os.path.exists(git_dir):
                try:
                    result = subprocess.run(
                        [os.path.join(git_dir, 'bin', 'git.exe'), '--version'],
                        capture_output=True,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    if result.returncode == 0:
                        version = re.search(r'git version (\d+\.\d+\.\d+)', result.stdout)
                        if version:
                            installations.append(InstalledEnvironment(
                                name='git',
                                version=version.group(1),
                                install_path=git_dir,
                                install_method=InstallMethod.OFFICIAL,
                            ))
                except Exception:
                    pass
        
        return installations
    
    def _detect_jdk_installations(self) -> List[InstalledEnvironment]:
        """检测 JDK 安装"""
        installations = []
        
        # 检查 JAVA_HOME
        java_home = os.environ.get('JAVA_HOME', '')
        if java_home and os.path.exists(java_home):
            try:
                result = subprocess.run(
                    [os.path.join(java_home, 'bin', 'java.exe'), '-version'],
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                version = re.search(r'version "?(\d+\.?\d*\.?\d*)"?', result.stderr or result.stdout)
                if version:
                    installations.append(InstalledEnvironment(
                        name='jdk',
                        version=version.group(1),
                        install_path=java_home,
                        install_method=InstallMethod.OFFICIAL,
                        is_active=True,
                    ))
            except Exception:
                pass
        
        # 检查 Program Files 中的 JDK
        for base_path in [
            os.environ.get('PROGRAMFILES', ''),
            os.environ.get('PROGRAMFILES(X86)', ''),
        ]:
            if not base_path:
                continue
            java_base = os.path.join(base_path, 'Java')
            if os.path.exists(java_base):
                for item in os.listdir(java_base):
                    jdk_path = os.path.join(java_base, item)
                    if os.path.exists(os.path.join(jdk_path, 'bin', 'java.exe')):
                        # 排除已检测的 JAVA_HOME
                        if jdk_path != java_home:
                            installations.append(InstalledEnvironment(
                                name='jdk',
                                version=item.replace('jdk', '').replace('jre', ''),
                                install_path=jdk_path,
                                install_method=InstallMethod.OFFICIAL,
                                is_active=False,
                            ))
        
        return installations
    
    def _detect_go_installations(self) -> List[InstalledEnvironment]:
        """检测 Go 安装"""
        installations = []
        
        goroot = os.environ.get('GOROOT', '')
        if not goroot:
            goroot = os.path.join(os.environ.get('PROGRAMFILES', ''), 'Go')
        
        if os.path.exists(goroot):
            try:
                result = subprocess.run(
                    [os.path.join(goroot, 'bin', 'go.exe'), 'version'],
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                version = re.search(r'go(\d+\.\d+\.\d+)', result.stdout)
                if version:
                    installations.append(InstalledEnvironment(
                        name='go',
                        version=version.group(1),
                        install_path=goroot,
                        install_method=InstallMethod.OFFICIAL,
                    ))
            except Exception:
                pass
        
        return installations
    
    def _detect_rust_installations(self) -> List[InstalledEnvironment]:
        """检测 Rust 安装"""
        installations = []
        
        rustup_home = os.environ.get('RUSTUP_HOME', 
            os.path.join(os.path.expanduser('~'), '.rustup'))
        
        if os.path.exists(rustup_home):
            toolchains_dir = os.path.join(rustup_home, 'toolchains')
            if os.path.exists(toolchains_dir):
                for toolchain in os.listdir(toolchains_dir):
                    installations.append(InstalledEnvironment(
                        name='rust',
                        version=toolchain.split('-')[0] if '-' in toolchain else toolchain,
                        install_path=os.path.join(toolchains_dir, toolchain),
                        install_method=InstallMethod.RUSTUP,
                    ))
        
        return installations
    
    def _detect_vscode_installations(self) -> List[InstalledEnvironment]:
        """检测 VS Code 安装"""
        installations = []
        
        for base_path in [
            os.environ.get('LOCALAPPDATA', ''),
            os.environ.get('PROGRAMFILES', ''),
        ]:
            if not base_path:
                continue
            vscode_dir = os.path.join(base_path, 'Programs', 'Microsoft VS Code')
            if os.path.exists(vscode_dir):
                try:
                    result = subprocess.run(
                        [os.path.join(vscode_dir, 'Code.exe'), '--version'],
                        capture_output=True,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    if result.returncode == 0:
                        version = result.stdout.strip().split('\n')[0]
                        installations.append(InstalledEnvironment(
                            name='vscode',
                            version=version,
                            install_path=vscode_dir,
                            install_method=InstallMethod.OFFICIAL,
                        ))
                except Exception:
                    pass
        
        return installations
    
    def _detect_cmake_installations(self) -> List[InstalledEnvironment]:
        """检测 CMake 安装"""
        installations = []
        
        for base_path in [
            os.environ.get('PROGRAMFILES', ''),
            os.environ.get('PROGRAMFILES(X86)', ''),
        ]:
            if not base_path:
                continue
            cmake_base = os.path.join(base_path, 'CMake')
            if os.path.exists(cmake_base):
                for item in os.listdir(cmake_base):
                    cmake_path = os.path.join(cmake_base, item, 'bin', 'cmake.exe')
                    if os.path.exists(cmake_path):
                        try:
                            result = subprocess.run(
                                [cmake_path, '--version'],
                                capture_output=True,
                                text=True,
                                creationflags=subprocess.CREATE_NO_WINDOW
                            )
                            version = re.search(r'cmake version (\d+\.\d+\.\d+)', result.stdout)
                            if version:
                                installations.append(InstalledEnvironment(
                                    name='cmake',
                                    version=version.group(1),
                                    install_path=os.path.join(cmake_base, item),
                                    install_method=InstallMethod.OFFICIAL,
                                ))
                        except Exception:
                            pass
        
        return installations
    
    def _detect_docker_installations(self) -> List[InstalledEnvironment]:
        """检测 Docker 安装"""
        installations = []
        
        docker_path = os.path.join(
            os.environ.get('PROGRAMFILES', ''), 
            'Docker', 'Docker', 'Docker Desktop.exe'
        )
        
        if os.path.exists(docker_path):
            try:
                result = subprocess.run(
                    ['docker', '--version'],
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                version = re.search(r'Docker version (\d+\.\d+\.\d+)', result.stdout)
                if version:
                    installations.append(InstalledEnvironment(
                        name='docker',
                        version=version.group(1),
                        install_path=os.path.dirname(docker_path),
                        install_method=InstallMethod.OFFICIAL,
                    ))
            except Exception:
                pass
        
        return installations
    
    def uninstall(self, env_name: str, version: str = None, 
                  remove_data: bool = False) -> Tuple[bool, str]:
        """
        卸载环境
        
        Args:
            env_name: 环境名称
            version: 版本号（不指定则卸载所有版本）
            remove_data: 是否删除用户数据
            
        Returns:
            (success, message)
        """
        detected = self._detected_envs.get(env_name, [])
        
        to_uninstall = []
        for inst in detected:
            if version is None or inst.version == version or inst.version.startswith(version):
                to_uninstall.append(inst)
        
        if not to_uninstall:
            return False, f"未找到 {env_name} {version or '任何版本'} 的安装"
        
        results = []
        for inst in to_uninstall:
            success, msg = self._uninstall_single(inst, remove_data)
            results.append((inst.version, success, msg))
        
        all_success = all(r[1] for r in results)
        message = "\n".join([
            f"版本 {r[0]}: {'成功' if r[1] else '失败'} - {r[2]}" 
            for r in results
        ])
        
        return all_success, message
    
    def _uninstall_single(self, inst: InstalledEnvironment, 
                         remove_data: bool) -> Tuple[bool, str]:
        """卸载单个安装"""
        # 首先尝试找到卸载程序
        uninstaller = self._find_uninstaller(inst)
        
        if uninstaller:
            try:
                result = subprocess.run(
                    uninstaller,
                    shell=True,
                    capture_output=True,
                    timeout=600,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode == 0:
                    return True, "卸载程序执行成功"
            except Exception as e:
                pass
        
        # 如果没有卸载程序或卸载失败，手动删除
        try:
            if os.path.exists(inst.install_path):
                shutil.rmtree(inst.install_path)
            
            # 从 PATH 中移除
            self._remove_from_path(inst.install_path)
            
            return True, f"已删除 {inst.install_path}"
        except Exception as e:
            return False, str(e)
    
    def _find_uninstaller(self, inst: InstalledEnvironment) -> Optional[str]:
        """查找卸载程序"""
        # 检查安装目录中的卸载程序
        uninstall_files = ['uninstall.exe', 'unins000.exe', 'uninstall']
        for f in uninstall_files:
            uninstaller = os.path.join(inst.install_path, f)
            if os.path.exists(uninstaller):
                return f'"{uninstaller}" /S'
        
        # 从注册表查找
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
            ) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    subkey_name = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, subkey_name) as subkey:
                        try:
                            display_name = winreg.QueryValueEx(subkey, 'DisplayName')[0]
                            if inst.name.lower() in display_name.lower():
                                uninstall_cmd = winreg.QueryValueEx(subkey, 'UninstallString')[0]
                                return uninstall_cmd
                        except Exception:
                            pass
        except Exception:
            pass
        
        return None
    
    def _remove_from_path(self, path_to_remove: str):
        """从 PATH 环境变量中移除路径"""
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Environment',
                0,
                winreg.KEY_READ | winreg.KEY_WRITE
            ) as key:
                current_path, _ = winreg.QueryValueEx(key, 'PATH')
                paths = current_path.split(';')
                filtered_paths = [
                    p for p in paths 
                    if path_to_remove.lower() not in p.lower()
                ]
                new_path = ';'.join(filtered_paths)
                winreg.SetValueEx(key, 'PATH', 0, winreg.REG_EXPAND_SZ, new_path)
        except Exception:
            pass
    
    def set_active_version(self, env_name: str, version: str) -> Tuple[bool, str]:
        """设置激活版本（用于多版本管理）"""
        detected = self._detected_envs.get(env_name, [])
        
        target = None
        for inst in detected:
            if inst.version == version or inst.version.startswith(version):
                target = inst
                break
        
        if not target:
            return False, f"未找到版本 {version}"
        
        # 更新 PATH
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Environment',
                0,
                winreg.KEY_READ | winreg.KEY_WRITE
            ) as key:
                current_path, _ = winreg.QueryValueEx(key, 'PATH')
                
                # 移除该环境所有版本的路径
                paths = current_path.split(';')
                filtered_paths = []
                for p in paths:
                    keep = True
                    for inst in detected:
                        if inst.install_path.lower() in p.lower():
                            keep = False
                            break
                    if keep:
                        filtered_paths.append(p)
                
                # 添加目标版本的路径
                bin_path = os.path.join(target.install_path, 'bin')
                if not os.path.exists(bin_path):
                    bin_path = target.install_path
                
                new_path = bin_path + ';' + ';'.join(filtered_paths)
                winreg.SetValueEx(key, 'PATH', 0, winreg.REG_EXPAND_SZ, new_path)
                
                # 更新环境变量
                env_var_map = {
                    'python': 'PYTHONHOME',
                    'nodejs': 'NODE_PATH',
                    'jdk': 'JAVA_HOME',
                    'go': 'GOROOT',
                    'rust': 'RUSTUP_HOME',
                }
                
                if env_name in env_var_map:
                    winreg.SetValueEx(
                        key, env_var_map[env_name], 0, 
                        winreg.REG_SZ, target.install_path
                    )
                
                return True, f"已激活版本 {version}"
                
        except Exception as e:
            return False, str(e)
    
    def get_installed_versions(self, env_name: str) -> List[InstalledEnvironment]:
        """获取指定环境的所有已安装版本"""
        return self._detected_envs.get(env_name, [])
