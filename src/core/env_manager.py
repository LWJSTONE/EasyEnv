#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
环境管理器 - 管理开发环境的版本信息和下载链接
"""

import os
import sys
import subprocess
import re
from typing import Dict, List, Tuple, Optional


class EnvironmentManager:
    """开发环境管理器"""
    
    # 支持的开发环境配置
    ENVIRONMENTS = {
        'python': {
            'name': 'python',
            'display_name': 'Python',
            'icon': '🐍',
            'description': 'Python编程语言环境',
            'versions': ['3.12.0', '3.11.6', '3.10.13', '3.9.18', '3.8.18'],
            'download_url': 'https://www.python.org/ftp/python/{version}/python-{version}-amd64.exe',
            'install_args': ['/quiet', 'InstallAllUsers=1', 'PrependPath=1', 'Include_test=0'],
            'check_cmd': 'python --version',
            'version_regex': r'Python (\d+\.\d+\.\d+)',
            'env_var': 'PYTHON_VERSION'
        },
        'nodejs': {
            'name': 'nodejs',
            'display_name': 'Node.js',
            'icon': '💚',
            'description': 'JavaScript运行时环境',
            'versions': ['20.10.0', '18.19.0', '20.10.0', '16.20.2', '14.21.3'],
            'download_url': 'https://nodejs.org/dist/v{version}/node-v{version}-x64.msi',
            'install_args': ['/quiet', '/norestart'],
            'check_cmd': 'node --version',
            'version_regex': r'v(\d+\.\d+\.\d+)',
            'env_var': 'NODE_VERSION'
        },
        'git': {
            'name': 'git',
            'display_name': 'Git',
            'icon': '🔀',
            'description': '分布式版本控制系统',
            'versions': ['2.43.0', '2.42.0', '2.41.0', '2.40.0', '2.39.0'],
            'download_url': 'https://github.com/git-for-windows/git/releases/download/v{version}.windows.1/Git-{version}-64-bit.exe',
            'install_args': ['/VERYSILENT', '/NORESTART', '/NOCANCEL', '/SP-'],
            'check_cmd': 'git --version',
            'version_regex': r'git version (\d+\.\d+\.\d+)',
            'env_var': 'GIT_VERSION'
        },
        'vscode': {
            'name': 'vscode',
            'display_name': 'VS Code',
            'icon': '💠',
            'description': '轻量级代码编辑器',
            'versions': ['latest'],
            'download_url': 'https://update.code.visualstudio.com/latest/win32-x64/stable',
            'install_args': ['/VERYSILENT', '/MERGETASKS=!runcode', '/NORESTART'],
            'check_cmd': 'code --version',
            'version_regex': r'(\d+\.\d+\.\d+)',
            'env_var': 'VSCODE_VERSION'
        },
        'jdk': {
            'name': 'jdk',
            'display_name': 'OpenJDK',
            'icon': '☕',
            'description': 'Java开发工具包',
            'versions': ['21', '17', '11', '8'],
            'download_url': 'https://download.java.net/java/GA/jdk{version}/latest/openjdk-{version}_windows-x64_bin.zip',
            'install_args': [],
            'check_cmd': 'java -version',
            'version_regex': r'version "?(\d+\.?\d*\.?\d*)"?',
            'env_var': 'JAVA_VERSION'
        },
        'go': {
            'name': 'go',
            'display_name': 'Go',
            'icon': '🔵',
            'description': 'Go编程语言环境',
            'versions': ['1.21.5', '1.20.12', '1.19.13', '1.18.10'],
            'download_url': 'https://go.dev/dl/go{version}.windows-amd64.msi',
            'install_args': ['/quiet', '/norestart'],
            'check_cmd': 'go version',
            'version_regex': r'go(\d+\.\d+\.\d+)',
            'env_var': 'GO_VERSION'
        },
        'rust': {
            'name': 'rust',
            'display_name': 'Rust',
            'icon': '🦀',
            'description': 'Rust编程语言环境',
            'versions': ['stable', 'beta', 'nightly'],
            'download_url': 'https://win.rustup.rs/x86_64',
            'install_args': ['-y', '--default-toolchain {version}'],
            'check_cmd': 'rustc --version',
            'version_regex': r'rustc (\d+\.\d+\.\d+)',
            'env_var': 'RUST_VERSION'
        },
        'cmake': {
            'name': 'cmake',
            'display_name': 'CMake',
            'icon': '📐',
            'description': '跨平台构建工具',
            'versions': ['3.28.0', '3.27.9', '3.26.6', '3.25.3'],
            'download_url': 'https://github.com/Kitware/CMake/releases/download/v{version}/cmake-{version}-windows-x86_64.msi',
            'install_args': ['/quiet', '/norestart'],
            'check_cmd': 'cmake --version',
            'version_regex': r'cmake version (\d+\.\d+\.\d+)',
            'env_var': 'CMAKE_VERSION'
        },
        'mingw': {
            'name': 'mingw',
            'display_name': 'MinGW-w64',
            'icon': '⚙️',
            'description': 'GCC编译器环境 (Windows)',
            'versions': ['13.2.0', '12.2.0', '11.2.0'],
            'download_url': 'https://github.com/niXman/mingw-builds-binaries/releases/download/{version}-rt_v11-rev1/x86_64-{version}-release-posix-seh-ucrt-rt_v11-rev1.7z',
            'install_args': [],
            'check_cmd': 'gcc --version',
            'version_regex': r'(\d+\.\d+\.\d+)',
            'env_var': 'MINGW_VERSION'
        },
        'docker': {
            'name': 'docker',
            'display_name': 'Docker Desktop',
            'icon': '🐳',
            'description': '容器化应用平台',
            'versions': ['latest'],
            'download_url': 'https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe',
            'install_args': ['install', '--quiet', '--accept-license'],
            'check_cmd': 'docker --version',
            'version_regex': r'Docker version (\d+\.\d+\.\d+)',
            'env_var': 'DOCKER_VERSION'
        }
    }
    
    def __init__(self):
        self.download_dir = os.path.join(os.path.expanduser('~'), '.easyenv', 'downloads')
        os.makedirs(self.download_dir, exist_ok=True)
        
    def get_available_environments(self) -> List[Dict]:
        """获取所有可用的开发环境列表"""
        return [env.copy() for env in self.ENVIRONMENTS.values()]
    
    def get_environment_info(self, name: str) -> Optional[Dict]:
        """获取指定环境的信息"""
        return self.ENVIRONMENTS.get(name, {}).copy()
    
    def get_download_url(self, name: str, version: str) -> Optional[str]:
        """获取下载链接"""
        env_info = self.ENVIRONMENTS.get(name)
        if not env_info:
            return None
            
        url = env_info['download_url']
        if version == 'latest':
            return url
        return url.format(version=version)
    
    def get_install_args(self, name: str, version: str) -> List[str]:
        """获取安装参数"""
        env_info = self.ENVIRONMENTS.get(name)
        if not env_info:
            return []
            
        args = env_info.get('install_args', [])
        return [arg.format(version=version) for arg in args]
    
    def check_installed(self, name: str) -> Tuple[bool, str]:
        """检查环境是否已安装"""
        env_info = self.ENVIRONMENTS.get(name)
        if not env_info:
            return False, ""
            
        try:
            # 尝试执行检查命令
            result = subprocess.run(
                env_info['check_cmd'],
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            # 合并 stdout 和 stderr
            output = result.stdout + result.stderr
            
            if result.returncode == 0 or output:
                # 尝试提取版本号
                match = re.search(env_info['version_regex'], output)
                if match:
                    return True, match.group(1)
                return True, "unknown"
                
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass
            
        return False, ""
    
    def get_install_dir(self, name: str) -> str:
        """获取安装目录"""
        default_dirs = {
            'python': os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Python'),
            'nodejs': os.path.join(os.environ.get('PROGRAMFILES', ''), 'nodejs'),
            'git': os.path.join(os.environ.get('PROGRAMFILES', ''), 'Git'),
            'vscode': os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Microsoft VS Code'),
            'jdk': os.path.join(os.environ.get('PROGRAMFILES', ''), 'Java'),
            'go': os.path.join(os.environ.get('PROGRAMFILES', ''), 'Go'),
            'rust': os.path.join(os.environ.get('USERPROFILE', ''), '.rustup'),
            'cmake': os.path.join(os.environ.get('PROGRAMFILES', ''), 'CMake'),
            'mingw': os.path.join(os.environ.get('PROGRAMFILES', ''), 'mingw64'),
            'docker': os.path.join(os.environ.get('PROGRAMFILES', ''), 'Docker', 'Docker')
        }
        return default_dirs.get(name, '')
