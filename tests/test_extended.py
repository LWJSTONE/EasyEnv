#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
EasyEnv 扩展测试 - 覆盖核心安装流程、错误处理、回滚等
"""

import os
import sys
import json
import tempfile
import shutil
import unittest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestErrorHandling(unittest.TestCase):
    """错误处理测试"""
    
    def test_error_code_definition(self):
        """测试错误码定义"""
        from src.core.errors import ErrorCode
        
        # 验证错误码格式
        for error in ErrorCode:
            self.assertTrue(error.code.startswith('E'))
            self.assertTrue(len(error.code) == 5)
            self.assertIsNotNone(error.message)
            self.assertIsNotNone(error.suggestion)
    
    def test_error_info_creation(self):
        """测试错误信息创建"""
        from src.core.errors import ErrorInfo, ErrorCode
        
        info = ErrorInfo(
            code=ErrorCode.PERMISSION_DENIED.code,
            message=ErrorCode.PERMISSION_DENIED.message,
            suggestion=ErrorCode.PERMISSION_DENIED.suggestion,
            details="Test details"
        )
        
        self.assertEqual(info.code, "E1002")
        self.assertIn("权限不足", info.message)
        self.assertIn("Test details", info.to_user_message())
    
    def test_easy_env_error(self):
        """测试自定义异常"""
        from src.core.errors import EasyEnvError, ErrorCode
        
        error = EasyEnvError(
            ErrorCode.DOWNLOAD_FAILED,
            details="Connection timeout",
            context={"url": "https://example.com"}
        )
        
        self.assertEqual(error.error_code, ErrorCode.DOWNLOAD_FAILED)
        self.assertIn("E2001", str(error))
        self.assertIn("Connection timeout", error.details)
        self.assertEqual(error.context["url"], "https://example.com")
    
    def test_error_to_dict(self):
        """测试错误序列化"""
        from src.core.errors import EasyEnvError, ErrorCode
        
        error = EasyEnvError(ErrorCode.NETWORK_ERROR, details="Test")
        error_dict = error.to_dict()
        
        self.assertIn("code", error_dict)
        self.assertIn("message", error_dict)
        self.assertIn("timestamp", error_dict)
        self.assertIn("trace_id", error_dict)


class TestStructuredLogger(unittest.TestCase):
    """结构化日志测试"""
    
    def setUp(self):
        self.test_log_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.test_log_dir, ignore_errors=True)
    
    def test_logger_creation(self):
        """测试日志器创建"""
        from src.core.errors import StructuredLogger
        
        logger = StructuredLogger("TestLogger", self.test_log_dir)
        self.assertEqual(logger.name, "TestLogger")
        self.assertEqual(logger.log_dir, self.test_log_dir)
    
    def test_log_entry_format(self):
        """测试日志条目格式"""
        from src.core.errors import StructuredLogger
        
        logger = StructuredLogger("TestLogger", self.test_log_dir)
        logger.info("Test message", key="value")
        
        # 检查日志文件是否创建
        log_files = [f for f in os.listdir(self.test_log_dir) if f.endswith('.jsonl')]
        self.assertEqual(len(log_files), 1)
        
        # 读取并验证日志内容
        with open(os.path.join(self.test_log_dir, log_files[0]), 'r') as f:
            entry = json.loads(f.readline())
        
        self.assertEqual(entry["level"], "INFO")
        self.assertEqual(entry["message"], "Test message")
        self.assertEqual(entry["context"]["key"], "value")
    
    def test_error_logging(self):
        """测试错误日志"""
        from src.core.errors import StructuredLogger, EasyEnvError, ErrorCode
        
        logger = StructuredLogger("TestLogger", self.test_log_dir)
        
        error = EasyEnvError(ErrorCode.UNKNOWN_ERROR, details="Test error")
        logger.error("Error occurred", error=error)
        
        # 读取日志
        log_files = [f for f in os.listdir(self.test_log_dir) if f.endswith('.jsonl')]
        with open(os.path.join(self.test_log_dir, log_files[0]), 'r') as f:
            entry = json.loads(f.readline())
        
        self.assertEqual(entry["level"], "ERROR")
        self.assertIn("error", entry)
        self.assertEqual(entry["error"]["code"], "E1000")


class TestAuditLogger(unittest.TestCase):
    """审计日志测试"""
    
    def setUp(self):
        self.test_audit_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.test_audit_dir, ignore_errors=True)
    
    def test_audit_logging(self):
        """测试审计日志记录"""
        from src.core.errors import AuditLogger
        
        logger = AuditLogger(self.test_audit_dir)
        
        logger.log_operation(
            operation="install",
            target="python@3.12.0",
            details={"mirror": "official"},
            success=True
        )
        
        # 读取审计日志
        operations = logger.get_operations()
        self.assertEqual(len(operations), 1)
        self.assertEqual(operations[0]["operation"], "install")
        self.assertTrue(operations[0]["success"])
    
    def test_audit_multiple_operations(self):
        """测试多条审计记录"""
        from src.core.errors import AuditLogger
        
        logger = AuditLogger(self.test_audit_dir)
        
        for i in range(5):
            logger.log_operation(
                operation=f"test_op_{i}",
                target=f"target_{i}",
                details={},
                success=(i % 2 == 0)
            )
        
        operations = logger.get_operations()
        self.assertEqual(len(operations), 5)


class TestTransactionManager(unittest.TestCase):
    """事务管理器测试"""
    
    def setUp(self):
        self.test_audit_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.test_audit_dir, ignore_errors=True)
    
    def test_transaction_success(self):
        """测试成功事务"""
        from src.core.errors import TransactionManager, AuditLogger
        
        audit = AuditLogger(self.test_audit_dir)
        tx = TransactionManager("test_tx", audit)
        
        executed = []
        
        def op1():
            executed.append("op1")
            return "result1"
        
        def rollback1(result):
            executed.append(f"rollback1:{result}")
        
        tx.add_operation("op1", op1, rollback1, "操作1")
        
        result = tx.execute()
        
        self.assertTrue(result["success"])
        self.assertEqual(len(result["executed"]), 1)
        self.assertIn("op1", executed)
    
    def test_transaction_rollback(self):
        """测试事务回滚"""
        from src.core.errors import TransactionManager, AuditLogger
        
        audit = AuditLogger(self.test_audit_dir)
        tx = TransactionManager("test_tx", audit)
        
        executed = []
        
        def op1():
            executed.append("op1")
            return "result1"
        
        def rollback1(result):
            executed.append(f"rollback1")
        
        def op2():
            executed.append("op2")
            raise Exception("Operation failed")
        
        def rollback2(result):
            executed.append("rollback2")
        
        tx.add_operation("op1", op1, rollback1, "操作1")
        tx.add_operation("op2", op2, rollback2, "操作2")
        
        result = tx.execute()
        
        self.assertFalse(result["success"])
        self.assertEqual(len(result["executed"]), 1)
        self.assertIn("rollback1", executed)
    
    def test_dry_run(self):
        """测试模拟运行"""
        from src.core.errors import TransactionManager, AuditLogger
        
        audit = AuditLogger(self.test_audit_dir)
        tx = TransactionManager("test_tx", audit)
        
        tx.add_operation("op1", lambda: None, lambda x: None, "操作1")
        tx.add_operation("op2", lambda: None, lambda x: None, "操作2")
        
        ops = tx.dry_run()
        
        self.assertEqual(len(ops), 2)
        self.assertIn("操作1", ops)


class TestSecurityVerifier(unittest.TestCase):
    """安全校验测试"""
    
    def setUp(self):
        self.test_file = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
        self.test_file.write(b"test content for hash calculation")
        self.test_file.close()
    
    def tearDown(self):
        os.unlink(self.test_file.name)
    
    def test_hash_calculation(self):
        """测试哈希计算"""
        from src.core.security import SecurityVerifier
        
        verifier = SecurityVerifier()
        hash_value = verifier._calculate_hash(self.test_file.name, "sha256")
        
        self.assertEqual(len(hash_value), 64)  # SHA256 produces 64 hex chars
        self.assertTrue(all(c in '0123456789abcdef' for c in hash_value))
    
    def test_url_validation(self):
        """测试URL验证"""
        from src.core.security import SecurityVerifier
        
        verifier = SecurityVerifier()
        
        # 测试HTTPS URL
        self.assertTrue(verifier.validate_url(
            "https://www.python.org/ftp/python/3.12.0/python.exe",
            allowed_hosts=["python.org", "www.python.org"]
        ))
        
        # 测试非HTTPS URL
        self.assertFalse(verifier.validate_url(
            "http://example.com/file.exe"
        ))
        
        # 测试不在白名单的主机
        self.assertFalse(verifier.validate_url(
            "https://malicious.com/file.exe",
            allowed_hosts=["python.org"]
        ))
    
    def test_path_sanitization(self):
        """测试路径清理"""
        from src.core.security import SecurityVerifier
        from src.core.errors import EasyEnvError
        
        verifier = SecurityVerifier()
        
        # 正常路径
        safe_path = verifier.sanitize_path("C:\\Program Files\\Python")
        self.assertEqual(safe_path, "C:\\Program Files\\Python")
        
        # 包含路径遍历的路径
        with self.assertRaises(EasyEnvError):
            verifier.sanitize_path("C:\\Program Files\\..\\Windows")
    
    def test_disk_space_check(self):
        """测试磁盘空间检查"""
        from src.core.security import SecurityVerifier
        
        verifier = SecurityVerifier()
        
        # 检查当前目录
        is_sufficient, available = verifier.check_disk_space(1)
        self.assertTrue(is_sufficient)
        self.assertGreater(available, 0)
        
        # 检查不可能的大空间需求
        is_sufficient, _ = verifier.check_disk_space(10 * 1024 * 1024)  # 10PB
        self.assertFalse(is_sufficient)


class TestInstallEngine(unittest.TestCase):
    """安装引擎测试"""
    
    def test_supported_environments(self):
        """测试支持的环境列表"""
        from src.core.install_engine import InstallEngine
        
        engine = InstallEngine()
        envs = engine.get_supported_environments()
        
        self.assertIn("python", envs)
        self.assertIn("nodejs", envs)
    
    def test_install_config_defaults(self):
        """测试安装配置默认值"""
        from src.core.install_engine import InstallConfig, InstallMode
        
        config = InstallConfig(env_name="python", version="3.12.0")
        
        self.assertEqual(config.mode, InstallMode.USER_ONLY)
        self.assertTrue(config.add_to_path)
        self.assertTrue(config.verify_checksum)
        self.assertEqual(config.mirror, "auto")
    
    def test_install_result(self):
        """测试安装结果"""
        from src.core.install_engine import InstallResult
        from src.core.errors import ErrorCode
        
        result = InstallResult(
            success=True,
            env_name="python",
            version="3.12.0",
            install_path="C:\\Python312",
            duration=30.5
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.env_name, "python")
        self.assertIsNone(result.error_code)
        
        # 失败结果
        fail_result = InstallResult(
            success=False,
            env_name="nodejs",
            version="20.0.0",
            error_code=ErrorCode.DOWNLOAD_FAILED,
            error_message="Network error"
        )
        
        self.assertFalse(fail_result.success)
        self.assertEqual(fail_result.error_code, ErrorCode.DOWNLOAD_FAILED)


class TestPythonInstaller(unittest.TestCase):
    """Python安装器测试"""
    
    def test_download_url_generation(self):
        """测试下载URL生成"""
        from src.core.install_engine import PythonInstaller, InstallConfig, InstallMode
        
        config = InstallConfig(env_name="python", version="3.12.0", mirror="official")
        installer = PythonInstaller(config)
        
        url = installer._get_download_url()
        self.assertIn("3.12.0", url)
        self.assertIn("python.org", url)
        
        # 测试镜像URL
        config_mirror = InstallConfig(env_name="python", version="3.12.0", mirror="npmmirror")
        installer_mirror = PythonInstaller(config_mirror)
        
        url_mirror = installer_mirror._get_download_url()
        self.assertIn("npmmirror", url_mirror)
    
    @patch('subprocess.run')
    def test_check_existing_installation(self, mock_run):
        """测试检查已安装Python"""
        from src.core.install_engine import PythonInstaller, InstallConfig
        
        config = InstallConfig(env_name="python", version="3.12.0")
        installer = PythonInstaller(config)
        
        # 模拟已安装
        with patch('winreg.OpenKey', side_effect=FileNotFoundError):
            with patch('os.path.exists', return_value=False):
                result = installer._check_existing_installation()
                self.assertIsNone(result)


class TestNodeJsInstaller(unittest.TestCase):
    """Node.js安装器测试"""
    
    def test_download_url_generation(self):
        """测试下载URL生成"""
        from src.core.install_engine import NodeJsInstaller, InstallConfig
        
        config = InstallConfig(env_name="nodejs", version="20.10.0")
        installer = NodeJsInstaller(config)
        
        url = installer._get_download_url()
        self.assertIn("20.10.0", url)
        self.assertIn("nodejs.org", url)
    
    def test_mirror_url_generation(self):
        """测试镜像URL生成"""
        from src.core.install_engine import NodeJsInstaller, InstallConfig
        
        config = InstallConfig(env_name="nodejs", version="20.10.0", mirror="tuna")
        installer = NodeJsInstaller(config)
        
        url = installer._get_download_url()
        self.assertIn("tuna.tsinghua.edu.cn", url)


class TestPackageInfo(unittest.TestCase):
    """包信息测试"""
    
    def test_package_info_creation(self):
        """测试包信息创建"""
        from src.core.security import PackageInfo
        
        info = PackageInfo(
            name="python",
            version="3.12.0",
            url="https://python.org/ftp/python/3.12.0/python.exe",
            expected_hash="abc123",
            hash_algorithm="sha256",
            size=25000000
        )
        
        self.assertEqual(info.name, "python")
        self.assertEqual(info.version, "3.12.0")
        self.assertEqual(info.hash_algorithm, "sha256")


class TestVerificationResult(unittest.TestCase):
    """校验结果测试"""
    
    def test_verification_result_success(self):
        """测试成功的校验结果"""
        from src.core.security import VerificationResult
        
        result = VerificationResult(
            success=True,
            hash_matched=True,
            signature_valid=True
        )
        
        self.assertTrue(result.success)
        self.assertTrue(result.hash_matched)
        self.assertTrue(result.signature_valid)
    
    def test_verification_result_failure(self):
        """测试失败的校验结果"""
        from src.core.security import VerificationResult
        
        result = VerificationResult(
            success=False,
            hash_matched=False,
            error_message="Hash mismatch"
        )
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Hash mismatch")


def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestStructuredLogger))
    suite.addTests(loader.loadTestsFromTestCase(TestAuditLogger))
    suite.addTests(loader.loadTestsFromTestCase(TestTransactionManager))
    suite.addTests(loader.loadTestsFromTestCase(TestSecurityVerifier))
    suite.addTests(loader.loadTestsFromTestCase(TestInstallEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestPythonInstaller))
    suite.addTests(loader.loadTestsFromTestCase(TestNodeJsInstaller))
    suite.addTests(loader.loadTestsFromTestCase(TestPackageInfo))
    suite.addTests(loader.loadTestsFromTestCase(TestVerificationResult))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
