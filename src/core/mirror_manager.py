#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
镜像源管理器 - 管理国内镜像源和代理配置
支持自动检测最优镜像、用户自定义镜像
"""

import os
import json
import time
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class MirrorSource:
    """镜像源数据类"""
    name: str
    display_name: str
    base_url: str
    region: str  # 'china', 'global'
    priority: int  # 数字越小优先级越高
    supported_envs: List[str]  # 支持的环境列表
    speed: float = 0.0  # 响应速度(ms)，0表示未测试


class MirrorManager:
    """镜像源管理器"""
    
    # 预定义的镜像源
    MIRROR_SOURCES = {
        'official': MirrorSource(
            name='official',
            display_name='官方源',
            base_url='',
            region='global',
            priority=100,
            supported_envs=['*']
        ),
        'npmmirror': MirrorSource(
            name='npmmirror',
            display_name='淘宝 NPM 镜像',
            base_url='https://npmmirror.com/mirrors',
            region='china',
            priority=1,
            supported_envs=['nodejs', 'python', 'electron']
        ),
        'tuna': MirrorSource(
            name='tuna',
            display_name='清华大学镜像站',
            base_url='https://mirrors.tuna.tsinghua.edu.cn',
            region='china',
            priority=2,
            supported_envs=['nodejs', 'go', 'python', 'rust']
        ),
        'ustc': MirrorSource(
            name='ustc',
            display_name='中科大镜像站',
            base_url='https://mirrors.ustc.edu.cn',
            region='china',
            priority=3,
            supported_envs=['go', 'rust', 'python']
        ),
        'huawei': MirrorSource(
            name='huawei',
            display_name='华为云镜像站',
            base_url='https://mirrors.huaweicloud.com',
            region='china',
            priority=4,
            supported_envs=['python', 'nodejs', 'go', 'jdk']
        ),
        'aliyun': MirrorSource(
            name='aliyun',
            display_name='阿里云镜像站',
            base_url='https://mirrors.aliyun.com',
            region='china',
            priority=5,
            supported_envs=['python', 'go', 'rust']
        ),
    }
    
    # 环境对应的镜像路径模板
    ENV_MIRROR_PATHS = {
        'python': {
            'npmmirror': 'https://registry.npmmirror.com/python-binaries/download/{version}/python-{version}-amd64.exe',
            'huawei': 'https://mirrors.huaweicloud.com/python/{version}/python-{version}-amd64.exe',
            'aliyun': 'https://mirrors.aliyun.com/python/{version}/python-{version}-amd64.exe',
        },
        'nodejs': {
            'npmmirror': 'https://npmmirror.com/mirrors/node/v{version}/node-v{version}-x64.msi',
            'tuna': 'https://mirrors.tuna.tsinghua.edu.cn/nodejs-release/v{version}/node-v{version}-x64.msi',
            'huawei': 'https://mirrors.huaweicloud.com/nodejs/v{version}/node-v{version}-x64.msi',
        },
        'go': {
            'tuna': 'https://mirrors.tuna.tsinghua.edu.cn/golang/go{version}.windows-amd64.msi',
            'ustc': 'https://mirrors.ustc.edu.cn/golang/go{version}.windows-amd64.msi',
            'huawei': 'https://mirrors.huaweicloud.com/golang/go{version}.windows-amd64.msi',
        },
        'rust': {
            'tuna': 'https://mirrors.tuna.tsinghua.edu.cn/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe',
            'ustc': 'https://mirrors.ustc.edu.cn/rust-static/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe',
        },
        'jdk': {
            'huawei': 'https://mirrors.huaweicloud.com/openjdk/{version}/openjdk-{version}_windows-x64_bin.zip',
        },
    }
    
    def __init__(self):
        self.config_file = os.path.join(
            os.path.expanduser('~'), '.easyenv', 'mirror_config.json'
        )
        self._config = self._load_config()
        self._speed_cache: Dict[str, float] = {}
        
    def _load_config(self) -> dict:
        """加载配置"""
        default_config = {
            'preference': 'auto',  # 'auto', 'official', 'china', 'custom'
            'custom_mirrors': {},
            'proxy': {
                'enabled': False,
                'http': '',
                'https': '',
            },
            'test_timeout': 5,  # 测试超时(秒)
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    default_config.update(loaded)
            except Exception:
                pass
                
        return default_config
    
    def _save_config(self):
        """保存配置"""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)
    
    def get_preference(self) -> str:
        """获取当前镜像偏好设置"""
        return self._config.get('preference', 'auto')
    
    def set_preference(self, preference: str):
        """设置镜像偏好"""
        if preference in ['auto', 'official', 'china', 'custom']:
            self._config['preference'] = preference
            self._save_config()
    
    def get_proxy_config(self) -> dict:
        """获取代理配置"""
        return self._config.get('proxy', {
            'enabled': False,
            'http': '',
            'https': '',
        })
    
    def set_proxy_config(self, enabled: bool, http: str = '', https: str = ''):
        """设置代理配置"""
        self._config['proxy'] = {
            'enabled': enabled,
            'http': http,
            'https': https or http,
        }
        self._save_config()
    
    def get_proxy_handler(self) -> Optional[urllib.request.ProxyHandler]:
        """获取代理处理器"""
        proxy_config = self.get_proxy_config()
        if not proxy_config.get('enabled'):
            return None
            
        proxies = {}
        if proxy_config.get('http'):
            proxies['http'] = proxy_config['http']
        if proxy_config.get('https'):
            proxies['https'] = proxy_config['https']
            
        if proxies:
            return urllib.request.ProxyHandler(proxies)
        return None
    
    def test_mirror_speed(self, mirror_name: str) -> float:
        """测试镜像源速度"""
        mirror = self.MIRROR_SOURCES.get(mirror_name)
        if not mirror:
            return -1
            
        test_url = None
        if mirror.base_url:
            test_url = f"{mirror.base_url}/"
        else:
            # 官方源使用一个已知存在的URL
            test_url = "https://www.python.org/ftp/python/"
        
        try:
            start_time = time.time()
            
            # 添加代理支持
            opener = urllib.request.build_opener()
            proxy_handler = self.get_proxy_handler()
            if proxy_handler:
                opener = urllib.request.build_opener(proxy_handler)
            
            request = urllib.request.Request(test_url, headers={
                'User-Agent': 'EasyEnv/1.0 Speed Test'
            })
            
            response = opener.open(request, timeout=self._config.get('test_timeout', 5))
            response.read(1024)  # 读取1KB数据
            
            elapsed = (time.time() - start_time) * 1000  # 转换为毫秒
            self._speed_cache[mirror_name] = elapsed
            return elapsed
            
        except Exception:
            return -1
    
    def test_all_mirrors(self) -> Dict[str, float]:
        """测试所有镜像源速度"""
        results = {}
        for name in self.MIRROR_SOURCES:
            results[name] = self.test_mirror_speed(name)
        return results
    
    def get_best_mirror(self, env_name: str) -> Tuple[str, MirrorSource]:
        """
        获取最佳镜像源
        
        Returns:
            (mirror_name, MirrorSource)
        """
        preference = self.get_preference()
        
        if preference == 'official':
            return 'official', self.MIRROR_SOURCES['official']
        
        if preference == 'custom':
            custom = self._config.get('custom_mirrors', {}).get(env_name)
            if custom:
                return custom, self.MIRROR_SOURCES.get(custom, self.MIRROR_SOURCES['official'])
        
        # auto模式：根据环境找到最快的镜像
        available_mirrors = []
        for name, mirror in self.MIRROR_SOURCES.items():
            if name == 'official':
                continue
            if '*' in mirror.supported_envs or env_name in mirror.supported_envs:
                available_mirrors.append((name, mirror))
        
        if not available_mirrors:
            return 'official', self.MIRROR_SOURCES['official']
        
        # 按优先级和速度排序
        def sort_key(item):
            name, mirror = item
            speed = self._speed_cache.get(name, mirror.priority * 100)
            return speed if speed > 0 else mirror.priority * 100
        
        available_mirrors.sort(key=sort_key)
        best_name, best_mirror = available_mirrors[0]
        return best_name, best_mirror
    
    def get_download_url(self, env_name: str, version: str) -> Tuple[str, str, str]:
        """
        获取下载URL
        
        Args:
            env_name: 环境名称
            version: 版本号
            
        Returns:
            (url, mirror_name, mirror_display_name)
        """
        mirror_name, mirror = self.get_best_mirror(env_name)
        
        # 检查是否有专门的镜像路径
        env_mirrors = self.ENV_MIRROR_PATHS.get(env_name, {})
        if mirror_name in env_mirrors:
            url = env_mirrors[mirror_name].format(version=version)
            return url, mirror_name, mirror.display_name
        
        # 没有专门的镜像路径，使用官方源
        return '', 'official', '官方源'
    
    def get_available_mirrors_for_env(self, env_name: str) -> List[Tuple[str, str]]:
        """
        获取环境可用的镜像源列表
        
        Returns:
            [(mirror_name, display_name), ...]
        """
        result = [('official', '官方源')]
        
        for name, mirror in self.MIRROR_SOURCES.items():
            if name == 'official':
                continue
            if '*' in mirror.supported_envs or env_name in mirror.supported_envs:
                result.append((name, mirror.display_name))
        
        return result
    
    def add_custom_mirror(self, name: str, url_template: str, envs: List[str] = None):
        """添加自定义镜像源"""
        if 'custom_mirrors' not in self._config:
            self._config['custom_mirrors'] = {}
        
        self._config['custom_mirrors'][name] = {
            'url_template': url_template,
            'envs': envs or ['*']
        }
        self._save_config()
    
    def remove_custom_mirror(self, name: str):
        """移除自定义镜像源"""
        if name in self._config.get('custom_mirrors', {}):
            del self._config['custom_mirrors'][name]
            self._save_config()
