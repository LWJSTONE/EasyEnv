#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
高级下载器 - 支持重试、断点续传、多线程下载
"""

import os
import sys
import time
import hashlib
import threading
import urllib.request
import urllib.error
from typing import Callable, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt5.QtCore import QThread, pyqtSignal


@dataclass
class DownloadProgress:
    """下载进度数据"""
    total_size: int = 0
    downloaded: int = 0
    speed: float = 0.0  # KB/s
    percentage: int = 0
    status: str = "准备中"


class DownloadWorker(QThread):
    """下载工作线程"""
    
    progress = pyqtSignal(int, int, float, str)  # downloaded, total, speed, status
    finished = pyqtSignal(bool, str, str)  # success, filepath, message
    log = pyqtSignal(str)
    
    # 下载配置
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # 秒
    CHUNK_SIZE = 1024 * 1024  # 1MB
    TIMEOUT = 30  # 秒
    
    def __init__(self, url: str, filepath: str, mirror_manager=None, 
                 expected_checksum: str = None, use_multithread: bool = True):
        super().__init__()
        self.url = url
        self.filepath = filepath
        self.mirror_manager = mirror_manager
        self.expected_checksum = expected_checksum
        self.use_multithread = use_multithread
        self._is_running = True
        self._pause = False
        
    def run(self):
        """执行下载"""
        self.log.emit(f"开始下载: {self.url}")
        
        # 检查是否支持断点续传
        supports_range = self._check_range_support()
        
        # 检查是否有未完成的下载
        temp_filepath = self.filepath + '.tmp'
        resume_pos = 0
        if os.path.exists(temp_filepath):
            resume_pos = os.path.getsize(temp_filepath)
            if resume_pos > 0 and supports_range:
                self.log.emit(f"检测到未完成的下载，从 {resume_pos} 字节处续传")
        
        success = False
        message = ""
        
        for attempt in range(1, self.MAX_RETRIES + 1):
            if not self._is_running:
                message = "下载已取消"
                break
                
            try:
                self.log.emit(f"下载尝试 {attempt}/{self.MAX_RETRIES}")
                
                if self.use_multithread and supports_range and resume_pos == 0:
                    # 多线程下载
                    success, message = self._multithread_download(temp_filepath)
                else:
                    # 单线程下载（支持断点续传）
                    success, message = self._single_thread_download(temp_filepath, resume_pos)
                
                if success:
                    break
                    
            except urllib.error.URLError as e:
                message = f"网络错误: {str(e)}"
                self.log.emit(f"下载失败 (尝试 {attempt}): {message}")
                if attempt < self.MAX_RETRIES:
                    self.log.emit(f"等待 {self.RETRY_DELAY} 秒后重试...")
                    time.sleep(self.RETRY_DELAY)
            except Exception as e:
                message = f"下载出错: {str(e)}"
                self.log.emit(f"下载失败 (尝试 {attempt}): {message}")
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY)
        
        # 下载成功，重命名文件
        if success and os.path.exists(temp_filepath):
            # 校验文件完整性
            if self.expected_checksum:
                self.log.emit("正在校验文件完整性...")
                if not self._verify_checksum(temp_filepath, self.expected_checksum):
                    os.remove(temp_filepath)
                    self.finished.emit(False, "", "文件校验失败，请重新下载")
                    return
            
            try:
                if os.path.exists(self.filepath):
                    os.remove(self.filepath)
                os.rename(temp_filepath, self.filepath)
                self.log.emit(f"下载完成: {self.filepath}")
                self.finished.emit(True, self.filepath, "下载成功")
            except Exception as e:
                self.finished.emit(False, "", f"保存文件失败: {str(e)}")
        else:
            self.finished.emit(False, "", message)
    
    def _check_range_support(self) -> bool:
        """检查服务器是否支持断点续传"""
        try:
            request = urllib.request.Request(self.url, method='HEAD')
            request.add_header('User-Agent', 'EasyEnv/1.0')
            
            opener = self._get_opener()
            response = opener.open(request, timeout=10)
            
            accept_ranges = response.headers.get('Accept-Ranges', '')
            return accept_ranges.lower() == 'bytes'
        except Exception:
            return False
    
    def _get_opener(self):
        """获取URL opener（支持代理）"""
        if self.mirror_manager:
            proxy_handler = self.mirror_manager.get_proxy_handler()
            if proxy_handler:
                return urllib.request.build_opener(proxy_handler)
        return urllib.request.build_opener()
    
    def _get_file_size(self) -> int:
        """获取远程文件大小"""
        try:
            request = urllib.request.Request(self.url, method='HEAD')
            request.add_header('User-Agent', 'EasyEnv/1.0')
            
            opener = self._get_opener()
            response = opener.open(request, timeout=self.TIMEOUT)
            
            return int(response.headers.get('Content-Length', 0))
        except Exception:
            return 0
    
    def _single_thread_download(self, filepath: str, resume_pos: int = 0) -> Tuple[bool, str]:
        """单线程下载（支持断点续传）"""
        total_size = self._get_file_size()
        
        # 打开文件（追加模式）
        mode = 'ab' if resume_pos > 0 else 'wb'
        file = open(filepath, mode)
        
        try:
            request = urllib.request.Request(self.url)
            request.add_header('User-Agent', 'EasyEnv/1.0')
            
            if resume_pos > 0:
                request.add_header('Range', f'bytes={resume_pos}-')
            
            opener = self._get_opener()
            response = opener.open(request, timeout=self.TIMEOUT)
            
            # 更新总大小
            content_length = int(response.headers.get('Content-Length', 0))
            if resume_pos > 0 and content_length > 0:
                total_size = resume_pos + content_length
            
            downloaded = resume_pos
            start_time = time.time()
            last_time = start_time
            last_downloaded = downloaded
            
            while self._is_running:
                # 处理暂停
                while self._pause:
                    time.sleep(0.1)
                
                chunk = response.read(self.CHUNK_SIZE)
                if not chunk:
                    break
                
                file.write(chunk)
                downloaded += len(chunk)
                
                # 计算速度
                current_time = time.time()
                time_diff = current_time - last_time
                if time_diff >= 0.5:  # 每0.5秒更新一次
                    speed = (downloaded - last_downloaded) / time_diff / 1024  # KB/s
                    last_time = current_time
                    last_downloaded = downloaded
                    
                    percentage = int((downloaded / total_size) * 100) if total_size > 0 else 0
                    self.progress.emit(downloaded, total_size, speed, f"{percentage}%")
            
            if not self._is_running:
                return False, "下载已取消"
            
            return True, "下载完成"
            
        finally:
            file.close()
    
    def _multithread_download(self, filepath: str, num_threads: int = 4) -> Tuple[bool, str]:
        """多线程下载"""
        total_size = self._get_file_size()
        
        if total_size == 0:
            # 不支持多线程，回退到单线程
            return self._single_thread_download(filepath)
        
        self.log.emit(f"使用 {num_threads} 线程下载，文件大小: {total_size / 1024 / 1024:.2f} MB")
        
        # 计算每个线程下载的范围
        chunk_size = total_size // num_threads
        ranges = []
        for i in range(num_threads):
            start = i * chunk_size
            end = start + chunk_size - 1 if i < num_threads - 1 else total_size - 1
            ranges.append((start, end))
        
        # 创建临时文件
        temp_file = open(filepath, 'wb')
        temp_file.truncate(total_size)
        temp_file.close()
        
        # 下载进度跟踪
        progress_lock = threading.Lock()
        downloaded_chunks = [0] * num_threads
        start_time = time.time()
        
        def download_chunk(thread_id: int, start: int, end: int) -> bool:
            """下载一个分片"""
            try:
                request = urllib.request.Request(self.url)
                request.add_header('User-Agent', 'EasyEnv/1.0')
                request.add_header('Range', f'bytes={start}-{end}')
                
                opener = self._get_opener()
                response = opener.open(request, timeout=self.TIMEOUT)
                
                with open(filepath, 'r+b') as f:
                    f.seek(start)
                    while self._is_running:
                        chunk = response.read(self.CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        
                        with progress_lock:
                            downloaded_chunks[thread_id] += len(chunk)
                            total_downloaded = sum(downloaded_chunks)
                            elapsed = time.time() - start_time
                            speed = total_downloaded / elapsed / 1024 if elapsed > 0 else 0
                            percentage = int((total_downloaded / total_size) * 100)
                            self.progress.emit(total_downloaded, total_size, speed, f"{percentage}%")
                
                return True
                
            except Exception as e:
                self.log.emit(f"线程 {thread_id} 下载失败: {str(e)}")
                return False
        
        # 使用线程池下载
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = {
                executor.submit(download_chunk, i, start, end): i 
                for i, (start, end) in enumerate(ranges)
            }
            
            success = True
            for future in as_completed(futures):
                if not future.result():
                    success = False
        
        if not self._is_running:
            return False, "下载已取消"
        
        if success:
            return True, "下载完成"
        return False, "部分分片下载失败"
    
    def _verify_checksum(self, filepath: str, expected: str) -> bool:
        """校验文件校验和"""
        algorithm = 'sha256'
        if ':' in expected:
            algorithm, expected = expected.split(':', 1)
        
        hasher = hashlib.new(algorithm)
        with open(filepath, 'rb') as f:
            while chunk := f.read(self.CHUNK_SIZE):
                hasher.update(chunk)
        
        return hasher.hexdigest().lower() == expected.lower()
    
    def pause(self):
        """暂停下载"""
        self._pause = True
    
    def resume(self):
        """恢复下载"""
        self._pause = False
    
    def cancel(self):
        """取消下载"""
        self._is_running = False


class DownloadManager:
    """下载管理器"""
    
    def __init__(self, mirror_manager=None):
        self.mirror_manager = mirror_manager
        self.download_dir = os.path.join(
            os.path.expanduser('~'), '.easyenv', 'downloads'
        )
        os.makedirs(self.download_dir, exist_ok=True)
        
        self._active_workers: dict = {}
        self._lock = threading.Lock()
    
    def download(self, url: str, filename: str, 
                 progress_callback: Callable = None,
                 finished_callback: Callable = None,
                 use_multithread: bool = True) -> DownloadWorker:
        """开始下载"""
        filepath = os.path.join(self.download_dir, filename)
        
        worker = DownloadWorker(
            url=url,
            filepath=filepath,
            mirror_manager=self.mirror_manager,
            use_multithread=use_multithread
        )
        
        if progress_callback:
            worker.progress.connect(progress_callback)
        if finished_callback:
            worker.finished.connect(finished_callback)
        
        worker.start()
        
        with self._lock:
            self._active_workers[filepath] = worker
        
        return worker
    
    def cancel_download(self, filepath: str):
        """取消下载"""
        with self._lock:
            if filepath in self._active_workers:
                self._active_workers[filepath].cancel()
    
    def cancel_all(self):
        """取消所有下载"""
        with self._lock:
            for worker in self._active_workers.values():
                worker.cancel()
    
    def get_download_path(self, filename: str) -> str:
        """获取下载文件路径"""
        return os.path.join(self.download_dir, filename)
    
    def has_cached_file(self, filename: str) -> Tuple[bool, str]:
        """检查是否有缓存的文件"""
        filepath = self.get_download_path(filename)
        if os.path.exists(filepath):
            return True, filepath
        return False, ""
    
    def clear_cache(self, days: int = 30):
        """清理旧的下载缓存"""
        import time
        now = time.time()
        
        for filename in os.listdir(self.download_dir):
            filepath = os.path.join(self.download_dir, filename)
            if os.path.isfile(filepath):
                file_mtime = os.path.getmtime(filepath)
                if (now - file_mtime) > days * 24 * 3600:
                    try:
                        os.remove(filepath)
                    except Exception:
                        pass
