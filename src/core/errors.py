#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
EasyEnv 错误处理和结构化日志系统
提供统一的错误码、结构化日志和可观测性支持
"""

import os
import sys
import json
import logging
import traceback
import hashlib
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum
from functools import wraps


class ErrorCode(Enum):
    """统一错误码定义"""
    # 通用错误 1xxx
    UNKNOWN_ERROR = ("E1000", "未知错误", "请联系支持团队")
    INVALID_ARGUMENT = ("E1001", "参数无效", "请检查输入参数")
    PERMISSION_DENIED = ("E1002", "权限不足", "请以管理员身份运行")
    RESOURCE_NOT_FOUND = ("E1003", "资源不存在", "请检查路径或网络连接")
    
    # 网络错误 2xxx
    NETWORK_ERROR = ("E2000", "网络错误", "请检查网络连接")
    DOWNLOAD_FAILED = ("E2001", "下载失败", "请检查网络或更换镜像源")
    DOWNLOAD_TIMEOUT = ("E2002", "下载超时", "网络不稳定，请重试")
    DOWNLOAD_INTEGRITY = ("E2003", "文件校验失败", "文件可能已损坏，请重新下载")
    CERTIFICATE_ERROR = ("E2004", "证书验证失败", "请检查系统时间或网络环境")
    
    # 版本错误 3xxx
    VERSION_FETCH_FAILED = ("E3000", "版本信息获取失败", "使用缓存版本或检查网络")
    VERSION_NOT_FOUND = ("E3001", "指定版本不存在", "请选择其他版本")
    VERSION_PARSE_ERROR = ("E3002", "版本解析错误", "请联系支持团队")
    
    # 安装错误 4xxx
    INSTALL_FAILED = ("E4000", "安装失败", "请查看详细日志")
    INSTALL_TIMEOUT = ("E4001", "安装超时", "安装程序可能卡死，请手动处理")
    INSTALL_CANCELLED = ("E4002", "安装已取消", "用户取消安装")
    INSTALL_ALREADY_EXISTS = ("E4003", "环境已安装", "可选择其他版本或卸载后重装")
    INSTALL_DEPENDENCY_MISSING = ("E4004", "依赖缺失", "请先安装所需依赖")
    
    # 回滚错误 5xxx
    ROLLBACK_FAILED = ("E5000", "回滚失败", "请手动检查环境")
    ROLLBACK_PARTIAL = ("E5001", "部分回滚失败", "请查看详细日志手动清理")
    BACKUP_RESTORE_FAILED = ("E5002", "备份恢复失败", "请手动恢复PATH和注册表")
    
    # 环境管理错误 6xxx
    ENV_DETECT_FAILED = ("E6000", "环境检测失败", "请手动验证")
    ENV_SWITCH_FAILED = ("E6001", "版本切换失败", "请检查安装状态")
    UNINSTALL_FAILED = ("E6002", "卸载失败", "请手动卸载")
    
    # 磁盘错误 7xxx
    DISK_SPACE_INSUFFICIENT = ("E7000", "磁盘空间不足", "请清理磁盘后重试")
    DISK_WRITE_ERROR = ("E7001", "磁盘写入错误", "请检查磁盘权限")
    
    def __init__(self, code: str, message: str, suggestion: str):
        self.code = code
        self.message = message
        self.suggestion = suggestion


@dataclass
class ErrorInfo:
    """错误信息结构"""
    code: str
    message: str
    suggestion: str
    details: str = ""
    timestamp: str = ""
    trace_id: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if not self.trace_id:
            self.trace_id = str(uuid.uuid4())[:8]
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_user_message(self) -> str:
        """生成用户友好的错误消息"""
        msg = f"[{self.code}] {self.message}"
        if self.details:
            msg += f"\n详情: {self.details}"
        if self.suggestion:
            msg += f"\n建议: {self.suggestion}"
        return msg


class EasyEnvError(Exception):
    """EasyEnv 统一异常类"""
    
    def __init__(self, error_code: ErrorCode, details: str = "", context: Dict = None):
        self.error_code = error_code
        self.details = details
        self.context = context or {}
        self.trace_id = str(uuid.uuid4())[:8]
        self.timestamp = datetime.now().isoformat()
        
        self.error_info = ErrorInfo(
            code=error_code.code,
            message=error_code.message,
            suggestion=error_code.suggestion,
            details=details,
            timestamp=self.timestamp,
            trace_id=self.trace_id,
            context=self.context
        )
        
        super().__init__(self.error_info.to_user_message())
    
    def to_dict(self) -> dict:
        return self.error_info.to_dict()


class StructuredLogger:
    """结构化日志记录器"""
    
    def __init__(self, name: str = "EasyEnv", log_dir: str = None):
        self.name = name
        self.trace_id = str(uuid.uuid4())[:8]
        
        # 日志目录
        if log_dir is None:
            log_dir = os.path.join(os.path.expanduser('~'), '.easyenv', 'logs')
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        # 创建logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # 避免重复添加handler
        if not self.logger.handlers:
            # 控制台输出
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_format = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(message)s'
            )
            console_handler.setFormatter(console_format)
            self.logger.addHandler(console_handler)
            
            # 文件输出（JSON格式）
            log_file = os.path.join(
                log_dir, 
                f"easyenv_{datetime.now().strftime('%Y%m%d')}.jsonl"
            )
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            self.logger.addHandler(file_handler)
    
    def _create_log_entry(self, level: str, message: str, 
                          extra: Dict = None, error: Exception = None) -> dict:
        """创建结构化日志条目"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "trace_id": self.trace_id,
            "level": level,
            "logger": self.name,
            "message": message,
        }
        
        if extra:
            entry["context"] = extra
        
        if error:
            entry["error"] = {
                "type": type(error).__name__,
                "message": str(error),
            }
            if isinstance(error, EasyEnvError):
                entry["error"]["code"] = error.error_code.code
                entry["error"]["suggestion"] = error.error_code.suggestion
            entry["stack_trace"] = traceback.format_exc()
        
        return entry
    
    def _log(self, level: str, message: str, extra: Dict = None, error: Exception = None):
        """内部日志方法"""
        entry = self._create_log_entry(level, message, extra, error)
        
        # 写入JSON日志文件
        log_file = os.path.join(
            self.log_dir, 
            f"easyenv_{datetime.now().strftime('%Y%m%d')}.jsonl"
        )
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        
        # 控制台输出
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        if error:
            log_method(f"[{self.trace_id}] {message} - {error}")
        else:
            log_method(f"[{self.trace_id}] {message}")
    
    def debug(self, message: str, **kwargs):
        self._log("DEBUG", message, kwargs if kwargs else None)
    
    def info(self, message: str, **kwargs):
        self._log("INFO", message, kwargs if kwargs else None)
    
    def warning(self, message: str, **kwargs):
        self._log("WARNING", message, kwargs if kwargs else None)
    
    def error(self, message: str, error: Exception = None, **kwargs):
        self._log("ERROR", message, kwargs if kwargs else None, error)
    
    def critical(self, message: str, error: Exception = None, **kwargs):
        self._log("CRITICAL", message, kwargs if kwargs else None, error)
    
    def with_trace_id(self, trace_id: str) -> 'StructuredLogger':
        """创建带有指定trace_id的logger副本"""
        new_logger = StructuredLogger(self.name, self.log_dir)
        new_logger.trace_id = trace_id
        return new_logger


# 全局日志实例
_logger = None

def get_logger(name: str = "EasyEnv") -> StructuredLogger:
    """获取日志实例"""
    global _logger
    if _logger is None:
        _logger = StructuredLogger(name)
    return _logger


def error_handler(func):
    """错误处理装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger()
        try:
            return func(*args, **kwargs)
        except EasyEnvError as e:
            logger.error(f"操作失败: {func.__name__}", error=e)
            raise
        except PermissionError as e:
            error = EasyEnvError(
                ErrorCode.PERMISSION_DENIED,
                details=str(e),
                context={"function": func.__name__}
            )
            logger.error("权限错误", error=error)
            raise error
        except Exception as e:
            error = EasyEnvError(
                ErrorCode.UNKNOWN_ERROR,
                details=str(e),
                context={"function": func.__name__}
            )
            logger.error("未知错误", error=error)
            raise error
    return wrapper


class AuditLogger:
    """审计日志记录器 - 用于记录对系统的修改操作"""
    
    AUDIT_FILE = "audit.jsonl"
    
    def __init__(self, audit_dir: str = None):
        if audit_dir is None:
            audit_dir = os.path.join(os.path.expanduser('~'), '.easyenv', 'logs')
        self.audit_dir = audit_dir
        os.makedirs(audit_dir, exist_ok=True)
        self.audit_file = os.path.join(audit_dir, self.AUDIT_FILE)
    
    def log_operation(self, operation: str, target: str, details: Dict,
                      success: bool, dry_run: bool = False):
        """记录操作审计日志"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "target": target,
            "details": details,
            "success": success,
            "dry_run": dry_run,
            "user": os.environ.get('USERNAME', 'unknown'),
        }
        
        with open(self.audit_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def get_operations(self, limit: int = 100) -> List[dict]:
        """获取最近的操作记录"""
        operations = []
        if os.path.exists(self.audit_file):
            with open(self.audit_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-limit:]
                for line in lines:
                    try:
                        operations.append(json.loads(line))
                    except:
                        pass
        return operations


class TransactionManager:
    """事务管理器 - 提供操作的事务性保证"""
    
    def __init__(self, name: str, audit_logger: AuditLogger = None):
        self.name = name
        self.operations: List[Dict] = []
        self.completed = False
        self.audit_logger = audit_logger or AuditLogger()
        self.logger = get_logger()
    
    def add_operation(self, operation_type: str, execute_func, rollback_func, 
                      description: str = ""):
        """添加一个操作到事务"""
        self.operations.append({
            "type": operation_type,
            "execute": execute_func,
            "rollback": rollback_func,
            "description": description,
            "executed": False,
            "result": None,
        })
    
    def execute(self, stop_on_failure: bool = True) -> Dict:
        """执行事务中的所有操作"""
        results = {
            "success": True,
            "executed": [],
            "failed": None,
            "rolled_back": [],
            "rollback_failed": [],
        }
        
        for i, op in enumerate(self.operations):
            try:
                self.logger.info(f"执行操作: {op['description'] or op['type']}")
                op["result"] = op["execute"]()
                op["executed"] = True
                results["executed"].append({
                    "type": op["type"],
                    "description": op["description"],
                    "result": op["result"],
                })
                
                # 记录审计日志
                self.audit_logger.log_operation(
                    operation=op["type"],
                    target=self.name,
                    details={"description": op["description"]},
                    success=True
                )
                
            except Exception as e:
                results["success"] = False
                results["failed"] = {
                    "type": op["type"],
                    "description": op["description"],
                    "error": str(e),
                }
                
                self.logger.error(f"操作失败: {op['description']}", error=e)
                
                # 记录失败审计
                self.audit_logger.log_operation(
                    operation=op["type"],
                    target=self.name,
                    details={"description": op["description"], "error": str(e)},
                    success=False
                )
                
                if stop_on_failure:
                    # 执行回滚
                    self.logger.info("开始回滚已执行的操作...")
                    rollback_result = self._rollback()
                    results["rolled_back"] = rollback_result["rolled_back"]
                    results["rollback_failed"] = rollback_result["failed"]
                    break
        
        self.completed = True
        return results
    
    def _rollback(self) -> Dict:
        """回滚已执行的操作（逆序）"""
        result = {
            "rolled_back": [],
            "failed": [],
        }
        
        # 逆序回滚
        for op in reversed(self.operations):
            if op["executed"]:
                try:
                    self.logger.info(f"回滚操作: {op['description'] or op['type']}")
                    op["rollback"](op["result"])
                    result["rolled_back"].append(op["type"])
                    
                    self.audit_logger.log_operation(
                        operation=f"rollback_{op['type']}",
                        target=self.name,
                        details={"description": op["description"]},
                        success=True
                    )
                    
                except Exception as e:
                    self.logger.error(f"回滚失败: {op['description']}", error=e)
                    result["failed"].append({
                        "type": op["type"],
                        "error": str(e),
                    })
                    
                    self.audit_logger.log_operation(
                        operation=f"rollback_{op['type']}",
                        target=self.name,
                        details={"description": op["description"], "error": str(e)},
                        success=False
                    )
        
        return result
    
    def dry_run(self) -> List[str]:
        """模拟运行，返回将执行的操作列表"""
        return [op["description"] or op["type"] for op in self.operations]
