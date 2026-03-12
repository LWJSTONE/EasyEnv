#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
版本管理器 - 动态获取最新版本信息
支持从远程API/JSON获取版本，不再硬编码
"""

import json
import re
import os
import threading
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import urllib.request
import urllib.error


@dataclass
class VersionInfo:
    """版本信息数据类"""
    version: str
    release_date: str = ""
    lts: bool = False
    security_update: bool = False
    download_url: str = ""
    checksum: str = ""
    notes: str = ""


@dataclass
class EnvironmentConfig:
    """环境配置数据类"""
    name: str
    display_name: str
    icon: str
    description: str
    category: str
    official_site: str
    version_api: str  # 获取版本的API地址
    version_parser: str  # 版本解析方式
    mirrors: Dict[str, str] = field(default_factory=dict)  # 镜像源
    install_methods: List[str] = field(default_factory=list)  # 安装方式


class VersionManager:
    """版本管理器 - 动态获取版本信息"""
    
    # 缓存目录
    CACHE_DIR = os.path.join(os.path.expanduser('~'), '.easyenv', 'cache')
    CACHE_EXPIRE_HOURS = 6  # 缓存过期时间（小时）
    
    # 版本API配置
    VERSION_APIS = {
        'python': {
            'url': 'https://endoflife.date/api/python.json',
            'mirror_urls': [
                'https://registry.npmmirror.com/python-version-mirror/versions.json',
            ],
            'parser': 'endoflife',
            'download_template': 'https://www.python.org/ftp/python/{version}/python-{version}-amd64.exe',
        },
        'nodejs': {
            'url': 'https://nodejs.org/dist/index.json',
            'mirror_urls': [
                'https://npmmirror.com/mirrors/node/index.json',
                'https://mirrors.tuna.tsinghua.edu.cn/nodejs-release/index.json',
            ],
            'parser': 'nodejs',
            'download_template': 'https://nodejs.org/dist/v{version}/node-v{version}-x64.msi',
            'download_template_mirror': 'https://npmmirror.com/mirrors/node/v{version}/node-v{version}-x64.msi',
        },
        'go': {
            'url': 'https://go.dev/dl/?mode=json',
            'mirror_urls': [
                'https://golang.google.cn/dl/?mode=json',
                'https://mirrors.ustc.edu.cn/golang/dl/?mode=json',
            ],
            'parser': 'go',
            'download_template': 'https://go.dev/dl/go{version}.windows-amd64.msi',
        },
        'git': {
            'url': 'https://api.github.com/repos/git-for-windows/git/releases/latest',
            'mirror_urls': [],
            'parser': 'github_release',
            'download_template': 'https://github.com/git-for-windows/git/releases/download/v{version}.windows.1/Git-{version}-64-bit.exe',
        },
        'rust': {
            'url': 'https://static.rust-lang.org/dist/channel-rust-stable.toml',
            'mirror_urls': [
                'https://mirrors.tuna.tsinghua.edu.cn/rustup/dist/channel-rust-stable.toml',
            ],
            'parser': 'rust',
            'download_template': 'https://win.rustup.rs/x86_64',
        },
        'jdk': {
            'url': 'https://api.adoptium.net/v3/info/release_names?version_type=lts&release_type=ga&os=windows&architecture=x64',
            'mirror_urls': [],
            'parser': 'adoptium',
            'download_template': 'https://github.com/adoptium/temurin{version}-binaries/releases/download/jdk-{version}/OpenJDK{version}U-jdk_x64_windows_hotspot_{version}.msi',
        },
        'cmake': {
            'url': 'https://api.github.com/repos/Kitware/CMake/releases',
            'mirror_urls': [],
            'parser': 'github_releases',
            'download_template': 'https://github.com/Kitware/CMake/releases/download/v{version}/cmake-{version}-windows-x86_64.msi',
        },
        'docker': {
            'url': 'https://api.github.com/repos/docker/docker-desktop/releases',
            'mirror_urls': [],
            'parser': 'docker',
            'download_template': 'https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe',
        },
        'vscode': {
            'url': 'https://update.code.visualstudio.com/api/releases/stable',
            'mirror_urls': [],
            'parser': 'vscode',
            'download_template': 'https://update.code.visualstudio.com/latest/win32-x64/stable',
        },
        'mingw': {
            'url': 'https://api.github.com/repos/niXman/mingw-builds-binaries/releases',
            'mirror_urls': [],
            'parser': 'mingw',
            'download_template': 'https://github.com/niXman/mingw-builds-binaries/releases/download/{version}/x86_64-{version}-release-posix-seh-ucrt-rt_v11-rev1.7z',
        }
    }
    
    def __init__(self, mirror_preference: str = 'auto'):
        """
        初始化版本管理器
        
        Args:
            mirror_preference: 镜像偏好 ('auto', 'official', 'china', 'custom')
        """
        self.mirror_preference = mirror_preference
        self._cache: Dict[str, List[VersionInfo]] = {}
        self._cache_lock = threading.Lock()
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        
    def get_available_versions(self, env_name: str, use_cache: bool = True) -> Tuple[bool, List[VersionInfo], str]:
        """
        获取可用的版本列表
        
        Args:
            env_name: 环境名称
            use_cache: 是否使用缓存
            
        Returns:
            (success, versions, message)
        """
        # 检查内存缓存
        with self._cache_lock:
            if use_cache and env_name in self._cache:
                return True, self._cache[env_name], "从内存缓存获取"
        
        # 检查文件缓存
        cache_file = os.path.join(self.CACHE_DIR, f'{env_name}_versions.json')
        if use_cache and os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                cache_time = datetime.fromisoformat(cache_data.get('timestamp', '2000-01-01'))
                if datetime.now() - cache_time < timedelta(hours=self.CACHE_EXPIRE_HOURS):
                    versions = [VersionInfo(**v) for v in cache_data.get('versions', [])]
                    with self._cache_lock:
                        self._cache[env_name] = versions
                    return True, versions, "从文件缓存获取"
            except Exception:
                pass
        
        # 从远程API获取
        api_config = self.VERSION_APIS.get(env_name)
        if not api_config:
            return False, [], f"未知的环境: {env_name}"
        
        # 尝试不同的URL
        urls_to_try = [api_config['url']] + api_config.get('mirror_urls', [])
        
        for url in urls_to_try:
            try:
                success, versions, message = self._fetch_versions(env_name, url, api_config)
                if success:
                    # 更新缓存
                    with self._cache_lock:
                        self._cache[env_name] = versions
                    self._save_cache(env_name, versions)
                    return True, versions, message
            except Exception as e:
                continue
        
        # 所有URL都失败，尝试使用回退版本
        fallback_versions = self._get_fallback_versions(env_name)
        if fallback_versions:
            return True, fallback_versions, "使用回退版本（网络不可用）"
        
        return False, [], f"无法获取版本信息，请检查网络连接"
    
    def _fetch_versions(self, env_name: str, url: str, config: dict) -> Tuple[bool, List[VersionInfo], str]:
        """从指定URL获取版本信息"""
        try:
            request = urllib.request.Request(url, headers={
                'User-Agent': 'EasyEnv/1.0',
                'Accept': 'application/json, text/plain, */*'
            })
            
            with urllib.request.urlopen(request, timeout=15) as response:
                data = response.read().decode('utf-8')
                
            parser = config.get('parser', 'default')
            versions = self._parse_versions(env_name, data, parser, config)
            
            return True, versions, f"从 {url} 获取成功"
            
        except urllib.error.URLError as e:
            return False, [], f"网络错误: {str(e)}"
        except Exception as e:
            return False, [], f"解析错误: {str(e)}"
    
    def _parse_versions(self, env_name: str, data: str, parser: str, config: dict) -> List[VersionInfo]:
        """解析版本数据"""
        versions = []
        
        if parser == 'endoflife':
            # endoflife.date API 格式
            items = json.loads(data)
            for item in items[:20]:  # 只取最近20个版本
                versions.append(VersionInfo(
                    version=item.get('latest', item.get('cycle', '')),
                    release_date=item.get('releaseDate', ''),
                    lts=item.get('lts', False),
                ))
                
        elif parser == 'nodejs':
            # Node.js 官方格式
            items = json.loads(data)
            seen_lts = set()
            for item in items[:30]:
                version = item.get('version', '').lstrip('v')
                lts = item.get('lts', False)
                if lts and lts not in seen_lts:
                    seen_lts.add(lts)
                versions.append(VersionInfo(
                    version=version,
                    release_date=item.get('date', ''),
                    lts=bool(lts),
                    security_update=item.get('security', False),
                ))
                
        elif parser == 'go':
            # Go 官方格式
            items = json.loads(data)
            for item in items[:15]:
                version = item.get('version', '').lstrip('go')
                files = item.get('files', [])
                for f in files:
                    if f.get('filename', '').endswith('windows-amd64.msi'):
                        versions.append(VersionInfo(
                            version=version,
                            release_date=item.get('published', '')[:10] if item.get('published') else '',
                        ))
                        break
                        
        elif parser == 'github_release':
            # GitHub单个release
            data = json.loads(data)
            tag = data.get('tag_name', '')
            version = re.search(r'(\d+\.\d+\.\d+)', tag)
            if version:
                versions.append(VersionInfo(
                    version=version.group(1),
                    release_date=data.get('published_at', '')[:10] if data.get('published_at') else '',
                ))
                
        elif parser == 'github_releases':
            # GitHub多个release
            items = json.loads(data)
            for item in items[:20]:
                tag = item.get('tag_name', '')
                version = re.search(r'v?(\d+\.\d+\.\d+)', tag)
                if version:
                    versions.append(VersionInfo(
                        version=version.group(1),
                        release_date=item.get('published_at', '')[:10] if item.get('published_at') else '',
                    ))
                    
        elif parser == 'adoptium':
            # Adoptium JDK API
            data = json.loads(data)
            for release in data.get('releases', [])[:15]:
                version = release.get('release_name', '').replace('jdk-', '')
                versions.append(VersionInfo(
                    version=version.split('.')[0],  # 主版本号
                    notes=release.get('release_name', ''),
                ))
                
        elif parser == 'vscode':
            # VS Code API 返回简单的版本数组
            items = json.loads(data)
            for version in items[:10]:
                versions.append(VersionInfo(version=version))
                
        elif parser == 'docker':
            items = json.loads(data)
            for item in items[:10]:
                tag = item.get('tag_name', '')
                versions.append(VersionInfo(
                    version=tag,
                    release_date=item.get('published_at', '')[:10] if item.get('published_at') else '',
                ))
                
        elif parser == 'mingw':
            items = json.loads(data)
            for item in items[:15]:
                tag = item.get('tag_name', '')
                version_match = re.search(r'(\d+\.\d+\.\d+)', tag)
                if version_match:
                    versions.append(VersionInfo(
                        version=version_match.group(1),
                        notes=tag,
                    ))
                    
        elif parser == 'rust':
            # Rust TOML格式 (简化解析)
            version_match = re.search(r'version\s*=\s*"([^"]+)"', data)
            if version_match:
                versions.append(VersionInfo(version=version_match.group(1)))
        
        # 如果解析失败或结果为空，使用回退版本
        if not versions:
            return self._get_fallback_versions(env_name)
            
        return versions
    
    def _get_fallback_versions(self, env_name: str) -> List[VersionInfo]:
        """获取回退版本（当网络不可用时使用）"""
        fallback = {
            'python': ['3.12.0', '3.11.6', '3.10.13', '3.9.18', '3.8.18'],
            'nodejs': ['20.10.0', '18.19.0', '16.20.2', '14.21.3'],
            'go': ['1.21.5', '1.20.12', '1.19.13'],
            'git': ['2.43.0', '2.42.0', '2.41.0'],
            'rust': ['stable'],
            'jdk': ['21', '17', '11', '8'],
            'cmake': ['3.28.0', '3.27.9', '3.26.6'],
            'docker': ['latest'],
            'vscode': ['latest'],
            'mingw': ['13.2.0', '12.2.0', '11.2.0'],
        }
        
        versions = []
        for v in fallback.get(env_name, []):
            versions.append(VersionInfo(version=v, notes="回退版本"))
        return versions
    
    def _save_cache(self, env_name: str, versions: List[VersionInfo]):
        """保存版本缓存"""
        cache_file = os.path.join(self.CACHE_DIR, f'{env_name}_versions.json')
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'versions': [vars(v) for v in versions]
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def get_download_url(self, env_name: str, version: str, mirror: str = 'auto') -> Tuple[str, str]:
        """
        获取下载URL
        
        Args:
            env_name: 环境名称
            version: 版本号
            mirror: 镜像类型 ('auto', 'official', 'china')
            
        Returns:
            (url, mirror_name)
        """
        config = self.VERSION_APIS.get(env_name, {})
        
        # 根据镜像偏好选择URL模板
        if mirror == 'china' and config.get('download_template_mirror'):
            url = config['download_template_mirror'].format(version=version)
            return url, 'china'
        elif mirror == 'official' or not config.get('download_template_mirror'):
            url = config.get('download_template', '').format(version=version)
            return url, 'official'
        else:
            # auto模式，优先使用国内镜像
            if config.get('download_template_mirror'):
                url = config['download_template_mirror'].format(version=version)
                return url, 'china'
            url = config.get('download_template', '').format(version=version)
            return url, 'official'
    
    def clear_cache(self):
        """清除所有缓存"""
        with self._cache_lock:
            self._cache.clear()
        
        import shutil
        if os.path.exists(self.CACHE_DIR):
            for f in os.listdir(self.CACHE_DIR):
                if f.endswith('_versions.json'):
                    os.remove(os.path.join(self.CACHE_DIR, f))
