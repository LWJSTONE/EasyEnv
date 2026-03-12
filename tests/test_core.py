#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
EasyEnv 单元测试
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestVersionManager(unittest.TestCase):
    """版本管理器测试"""
    
    def setUp(self):
        from src.core.version_manager import VersionManager
        self.version_manager = VersionManager()
    
    def test_get_fallback_versions(self):
        """测试回退版本获取"""
        for env in ['python', 'nodejs', 'go', 'git']:
            versions = self.version_manager._get_fallback_versions(env)
            self.assertIsInstance(versions, list)
            self.assertGreater(len(versions), 0)
    
    def test_version_info_dataclass(self):
        """测试版本信息数据类"""
        from src.core.version_manager import VersionInfo
        
        info = VersionInfo(
            version="3.12.0",
            release_date="2024-01-01",
            lts=False
        )
        
        self.assertEqual(info.version, "3.12.0")
        self.assertEqual(info.release_date, "2024-01-01")
        self.assertFalse(info.lts)


class TestMirrorManager(unittest.TestCase):
    """镜像管理器测试"""
    
    def setUp(self):
        from src.core.mirror_manager import MirrorManager
        self.mirror_manager = MirrorManager()
    
    def test_get_preference(self):
        """测试获取偏好设置"""
        pref = self.mirror_manager.get_preference()
        self.assertIn(pref, ['auto', 'official', 'china', 'custom'])
    
    def test_set_preference(self):
        """测试设置偏好"""
        self.mirror_manager.set_preference('china')
        self.assertEqual(self.mirror_manager.get_preference(), 'china')
        
        # 恢复默认
        self.mirror_manager.set_preference('auto')
    
    def test_get_available_mirrors(self):
        """测试获取可用镜像"""
        mirrors = self.mirror_manager.get_available_mirrors_for_env('python')
        self.assertIsInstance(mirrors, list)
        self.assertIn(('official', '官方源'), mirrors)
    
    def test_mirror_sources_defined(self):
        """测试镜像源定义"""
        self.assertIn('official', self.mirror_manager.MIRROR_SOURCES)
        self.assertIn('npmmirror', self.mirror_manager.MIRROR_SOURCES)
        self.assertIn('tuna', self.mirror_manager.MIRROR_SOURCES)


class TestTemplateManager(unittest.TestCase):
    """模板管理器测试"""
    
    def setUp(self):
        from src.core.template_manager import TemplateManager
        self.template_manager = TemplateManager()
    
    def test_preset_templates_exist(self):
        """测试预设模板存在"""
        templates = self.template_manager.get_all_templates()
        self.assertIn('frontend', templates)
        self.assertIn('backend', templates)
        self.assertIn('fullstack', templates)
        self.assertIn('java', templates)
        self.assertIn('golang', templates)
    
    def test_get_template(self):
        """测试获取模板"""
        template = self.template_manager.get_template('frontend')
        self.assertIsNotNone(template)
        self.assertEqual(template.name, 'frontend')
        self.assertIn('nodejs', [e.name for e in template.environments])
    
    def test_create_template(self):
        """测试创建模板"""
        template = self.template_manager.create_template(
            name='test_template',
            description='Test template',
            environments=[
                {'name': 'python', 'version': '3.12'},
                {'name': 'git', 'version': 'latest'},
            ]
        )
        
        self.assertEqual(template.name, 'test_template')
        self.assertEqual(len(template.environments), 2)


class TestRollbackManager(unittest.TestCase):
    """回滚管理器测试"""
    
    def setUp(self):
        from src.core.rollback_manager import RollbackManager, InstallStatus
        self.rollback_manager = RollbackManager()
        self.InstallStatus = InstallStatus
    
    def test_begin_install(self):
        """测试开始安装记录"""
        from src.core.rollback_manager import InstallRecord
        
        record = self.rollback_manager.begin_install('python', '3.12.0')
        
        self.assertIsInstance(record, InstallRecord)
        self.assertEqual(record.env_name, 'python')
        self.assertEqual(record.version, '3.12.0')
        self.assertEqual(record.status, self.InstallStatus.PENDING.value)
    
    def test_update_status(self):
        """测试更新状态"""
        self.rollback_manager.begin_install('nodejs', '20.0.0')
        self.rollback_manager.update_status('nodejs', self.InstallStatus.INSTALLING)
        
        record = self.rollback_manager._current_session.get('nodejs')
        self.assertEqual(record.status, self.InstallStatus.INSTALLING.value)


class TestDownloader(unittest.TestCase):
    """下载器测试"""
    
    def test_download_progress_dataclass(self):
        """测试下载进度数据类"""
        from src.core.downloader import DownloadProgress
        
        progress = DownloadProgress(
            total_size=1024000,
            downloaded=512000,
            speed=1024.0,
            percentage=50,
            status="下载中"
        )
        
        self.assertEqual(progress.total_size, 1024000)
        self.assertEqual(progress.percentage, 50)


class TestPrivilegeManager(unittest.TestCase):
    """权限管理器测试"""
    
    def test_is_admin_check(self):
        """测试管理员权限检查"""
        from src.utils.privilege import PrivilegeManager
        
        # 这个测试只验证方法可以调用
        result = PrivilegeManager.is_admin()
        self.assertIsInstance(result, bool)


class TestHelpers(unittest.TestCase):
    """辅助函数测试"""
    
    def test_format_size(self):
        """测试文件大小格式化"""
        from src.utils.helpers import format_size
        
        self.assertEqual(format_size(0), "0.00 B")
        self.assertEqual(format_size(1024), "1.00 KB")
        self.assertEqual(format_size(1024 * 1024), "1.00 MB")
        self.assertEqual(format_size(1024 * 1024 * 1024), "1.00 GB")
    
    def test_format_duration(self):
        """测试持续时间格式化"""
        from src.utils.helpers import format_duration
        
        self.assertIn("秒", format_duration(30))
        self.assertIn("分钟", format_duration(120))
        self.assertIn("小时", format_duration(7200))


def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestVersionManager))
    suite.addTests(loader.loadTestsFromTestCase(TestMirrorManager))
    suite.addTests(loader.loadTestsFromTestCase(TestTemplateManager))
    suite.addTests(loader.loadTestsFromTestCase(TestRollbackManager))
    suite.addTests(loader.loadTestsFromTestCase(TestDownloader))
    suite.addTests(loader.loadTestsFromTestCase(TestPrivilegeManager))
    suite.addTests(loader.loadTestsFromTestCase(TestHelpers))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
