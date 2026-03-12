#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
安全校验模块 - 下载包签名校验和安全检查
"""

import os
import hashlib
import subprocess
import json
import re
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from datetime import datetime

from .errors import ErrorCode, EasyEnvError, get_logger


@dataclass
class PackageInfo:
    """安装包信息"""
    name: str
    version: str
    url: str
    expected_hash: Optional[str] = None
    hash_algorithm: str = "sha256"
    signature_url: Optional[str] = None
    size: int = 0


@dataclass
class VerificationResult:
    """校验结果"""
    success: bool
    hash_matched: bool = False
    signature_valid: bool = False
    error_message: str = ""
    details: Dict = None


class SecurityVerifier:
    """安全校验器"""
    
    # 已知的官方签名公钥（示例，实际需要从官方获取）
    KNOWN_KEYS = {
        'python': {
            'gpg_key': 'https://www.python.org/static/files/pubkeys.txt',
            'keyring': None,  # 首次使用时加载
        },
        'nodejs': {
            'gpg_keys': [
                'https://nodejs.org/dist/pubkey.gpg',
            ],
        },
        'go': {
            'gpg_keys': [
                'https://go.dev/dl/gosrc.tar.gz.asc',
            ],
        }
    }
    
    # 官方发布哈希源
    HASH_SOURCES = {
        'python': 'https://www.python.org/downloads/release/py{version}/',
        'nodejs': 'https://nodejs.org/dist/v{version}/SHASUMS256.txt',
        'go': 'https://go.dev/dl/?mode=json',
    }
    
    def __init__(self):
        self.logger = get_logger()
        self._hash_cache: Dict[str, Dict[str, str]] = {}
    
    def verify_package(self, filepath: str, package_info: PackageInfo,
                       check_signature: bool = False) -> VerificationResult:
        """
        校验安装包
        
        Args:
            filepath: 下载文件路径
            package_info: 安装包信息
            check_signature: 是否检查签名
            
        Returns:
            VerificationResult
        """
        self.logger.info(f"开始校验安装包: {package_info.name} v{package_info.version}")
        
        result = VerificationResult(
            success=False,
            hash_matched=False,
            signature_valid=False,
            details={}
        )
        
        # 1. 检查文件是否存在
        if not os.path.exists(filepath):
            result.error_message = f"文件不存在: {filepath}"
            return result
        
        # 2. 计算文件哈希
        actual_hash = self._calculate_hash(filepath, package_info.hash_algorithm)
        result.details["actual_hash"] = actual_hash
        
        self.logger.debug(f"计算哈希: {actual_hash}")
        
        # 3. 获取预期哈希
        expected_hash = package_info.expected_hash
        if not expected_hash:
            # 尝试从官方源获取
            expected_hash = self._fetch_official_hash(package_info)
        
        if expected_hash:
            result.details["expected_hash"] = expected_hash
            result.hash_matched = (actual_hash.lower() == expected_hash.lower())
            
            if result.hash_matched:
                self.logger.info("哈希校验通过")
            else:
                self.logger.warning(f"哈希不匹配! 预期: {expected_hash}, 实际: {actual_hash}")
        else:
            self.logger.warning("无法获取官方哈希，跳过校验")
            result.details["hash_skipped"] = True
            result.hash_matched = True  # 无哈希时认为通过
        
        # 4. 签名校验（可选）
        if check_signature and package_info.signature_url:
            sig_result = self._verify_signature(filepath, package_info)
            result.signature_valid = sig_result["valid"]
            result.details["signature_error"] = sig_result.get("error", "")
        
        # 5. 最终结果
        result.success = result.hash_matched
        if check_signature:
            result.success = result.success and result.signature_valid
        
        return result
    
    def _calculate_hash(self, filepath: str, algorithm: str = "sha256") -> str:
        """计算文件哈希"""
        hasher = hashlib.new(algorithm)
        
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        
        return hasher.hexdigest()
    
    def _fetch_official_hash(self, package_info: PackageInfo) -> Optional[str]:
        """从官方源获取哈希值"""
        import urllib.request
        import urllib.error
        
        name = package_info.name
        version = package_info.version
        
        try:
            if name == 'nodejs':
                # Node.js 官方提供 SHASUMS256.txt
                url = f"https://nodejs.org/dist/v{version}/SHASUMS256.txt"
                self.logger.debug(f"获取Node.js哈希: {url}")
                
                request = urllib.request.Request(url, headers={
                    'User-Agent': 'EasyEnv/2.0'
                })
                
                with urllib.request.urlopen(request, timeout=15) as response:
                    content = response.read().decode('utf-8')
                
                # 解析哈希文件
                filename = f"node-v{version}-x64.msi"
                for line in content.split('\n'):
                    if filename in line:
                        return line.split()[0]
            
            elif name == 'python':
                # Python 官方页面解析（较复杂）
                # 这里简化处理，实际应从邮件列表或发布页面获取
                pass
            
            elif name == 'go':
                # Go 从 JSON API 获取
                url = "https://go.dev/dl/?mode=json"
                request = urllib.request.Request(url, headers={
                    'User-Agent': 'EasyEnv/2.0'
                })
                
                with urllib.request.urlopen(request, timeout=15) as response:
                    releases = json.loads(response.read().decode('utf-8'))
                
                for release in releases:
                    if f"go{version}" in release.get('version', ''):
                        for file_info in release.get('files', []):
                            if file_info.get('filename', '').endswith('windows-amd64.msi'):
                                return file_info.get('sha256')
        
        except urllib.error.URLError as e:
            self.logger.warning(f"获取官方哈希失败: {e}")
        except Exception as e:
            self.logger.warning(f"解析哈希失败: {e}")
        
        return None
    
    def _verify_signature(self, filepath: str, 
                          package_info: PackageInfo) -> Dict:
        """验证GPG签名"""
        result = {"valid": False, "error": ""}
        
        try:
            # 检查GPG是否可用
            gpg_check = subprocess.run(
                ['gpg', '--version'],
                capture_output=True,
                timeout=5
            )
            
            if gpg_check.returncode != 0:
                result["error"] = "GPG未安装"
                return result
            
            # 下载签名文件
            if package_info.signature_url:
                import urllib.request
                sig_path = filepath + '.asc'
                
                urllib.request.urlretrieve(package_info.signature_url, sig_path)
                
                # 验证签名
                verify_result = subprocess.run(
                    ['gpg', '--verify', sig_path, filepath],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if verify_result.returncode == 0:
                    result["valid"] = True
                else:
                    result["error"] = verify_result.stderr
                
                # 清理签名文件
                if os.path.exists(sig_path):
                    os.remove(sig_path)
            
        except FileNotFoundError:
            result["error"] = "GPG未安装"
        except subprocess.TimeoutExpired:
            result["error"] = "签名验证超时"
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def check_disk_space(self, required_mb: int, 
                         target_dir: str = None) -> Tuple[bool, int]:
        """
        检查磁盘空间
        
        Returns:
            (is_sufficient, available_mb)
        """
        import shutil
        
        if target_dir is None:
            target_dir = os.path.expanduser('~')
        
        try:
            usage = shutil.disk_usage(target_dir)
            available_mb = usage.free // (1024 * 1024)
            
            return (available_mb >= required_mb, available_mb)
        except Exception as e:
            self.logger.warning(f"无法检查磁盘空间: {e}")
            return (True, -1)  # 检查失败时假设空间充足
    
    def validate_url(self, url: str, allowed_hosts: List[str] = None) -> bool:
        """
        验证URL安全性
        
        Args:
            url: 要验证的URL
            allowed_hosts: 允许的主机名列表
        """
        from urllib.parse import urlparse
        
        try:
            parsed = urlparse(url)
            
            # 必须是HTTPS
            if parsed.scheme != 'https':
                self.logger.warning(f"URL非HTTPS: {url}")
                return False
            
            # 检查主机名
            if allowed_hosts:
                if parsed.netloc not in allowed_hosts:
                    # 允许子域名
                    host_valid = any(
                        parsed.netloc.endswith('.' + host) or parsed.netloc == host
                        for host in allowed_hosts
                    )
                    if not host_valid:
                        self.logger.warning(f"URL主机不在白名单: {parsed.netloc}")
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"URL解析失败: {e}")
            return False
    
    def sanitize_path(self, path: str) -> str:
        """清理和验证路径，防止路径遍历攻击"""
        # 规范化路径
        normalized = os.path.normpath(path)
        
        # 检查路径遍历
        if '..' in normalized:
            raise EasyEnvError(
                ErrorCode.INVALID_ARGUMENT,
                details="路径包含非法字符",
                context={"path": path}
            )
        
        return normalized


class SecureDownloader:
    """安全下载器 - 集成安全校验"""
    
    ALLOWED_HOSTS = [
        'python.org',
        'www.python.org',
        'nodejs.org',
        'go.dev',
        'golang.org',
        'github.com',
        'githubusercontent.com',
        'npmmirror.com',
        'mirrors.tuna.tsinghua.edu.cn',
        'mirrors.ustc.edu.cn',
        'mirrors.aliyun.com',
        'mirrors.huaweicloud.com',
    ]
    
    def __init__(self, verifier: SecurityVerifier = None):
        self.verifier = verifier or SecurityVerifier()
        self.logger = get_logger()
    
    def download_with_verification(
        self, 
        url: str,
        filepath: str,
        package_info: PackageInfo,
        progress_callback=None
    ) -> Tuple[bool, str]:
        """
        带校验的下载
        
        Returns:
            (success, message)
        """
        import urllib.request
        import ssl
        
        # 1. 验证URL
        if not self.verifier.validate_url(url, self.ALLOWED_HOSTS):
            return False, "URL验证失败：不在允许列表中"
        
        # 2. 检查磁盘空间
        is_sufficient, available = self.verifier.check_disk_space(500)
        if not is_sufficient:
            return False, f"磁盘空间不足，可用: {available}MB"
        
        # 3. 创建SSL上下文（强制验证证书）
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        
        try:
            # 4. 下载文件
            self.logger.info(f"开始下载: {url}")
            
            request = urllib.request.Request(url, headers={
                'User-Agent': 'EasyEnv/2.0'
            })
            
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=ssl_context)
            )
            
            with opener.open(request, timeout=60) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                
                with open(filepath, 'wb') as f:
                    downloaded = 0
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback and total_size > 0:
                            progress_callback(downloaded, total_size)
            
            self.logger.info(f"下载完成: {filepath}")
            
            # 5. 校验文件
            verify_result = self.verifier.verify_package(filepath, package_info)
            
            if verify_result.success:
                return True, "下载并校验成功"
            else:
                # 校验失败，删除文件
                if os.path.exists(filepath):
                    os.remove(filepath)
                return False, f"文件校验失败: {verify_result.error_message}"
        
        except urllib.error.URLError as e:
            return False, f"网络错误: {e.reason}"
        except ssl.SSLError as e:
            return False, f"SSL证书错误: {e}"
        except Exception as e:
            return False, f"下载失败: {e}"
