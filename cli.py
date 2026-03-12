#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
EasyEnv CLI - 命令行接口
与GUI解耦，支持脚本和CI/CD使用
"""

import os
import sys
import json
import argparse
from typing import Optional, List
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.install_engine import InstallEngine, InstallConfig, InstallMode
from src.core.errors import get_logger, EasyEnvError, ErrorCode


class CLI:
    """EasyEnv 命令行接口"""
    
    def __init__(self):
        self.logger = get_logger()
        self.engine = InstallEngine()
    
    def install(self, args):
        """安装环境"""
        print(f"\n🚀 EasyEnv 安装器")
        print(f"   环境: {args.env}")
        print(f"   版本: {args.version or 'latest'}")
        print(f"   模式: {'系统级' if args.system else '用户级'}")
        print(f"   镜像: {args.mirror or 'auto'}")
        print()
        
        # 创建配置
        config = InstallConfig(
            env_name=args.env,
            version=args.version or 'latest',
            mode=InstallMode.SYSTEM_WIDE if args.system else InstallMode.USER_ONLY,
            mirror=args.mirror or 'auto',
            add_to_path=not args.no_path,
            verify_checksum=not args.skip_verify,
        )
        
        # 进度回调
        def progress_callback(stage: str, progress: int, message: str):
            bar_length = 40
            filled = int(bar_length * progress / 100)
            bar = '█' * filled + '░' * (bar_length - filled)
            
            stage_names = {
                'precheck': '🔍 检查',
                'download': '📥 下载',
                'install': '⚙️ 安装',
                'postprocess': '🔧 配置',
            }
            
            stage_name = stage_names.get(stage, stage)
            print(f"\r{stage_name}: [{bar}] {progress}% {message}", end='', flush=True)
        
        # 执行安装
        try:
            result = self.engine.install(config, progress_callback)
            print()  # 换行
            
            if result.success:
                print(f"\n✅ 安装成功!")
                print(f"   环境: {result.env_name} v{result.version}")
                print(f"   路径: {result.install_path}")
                print(f"   耗时: {result.duration:.1f}秒")
                
                # 验证安装
                print(f"\n🔍 验证安装...")
                is_installed, path = self.engine.check_installed(result.env_name)
                if is_installed:
                    print(f"   ✅ 已验证: {path}")
                else:
                    print(f"   ⚠️ 无法验证安装，请手动检查")
                
                return 0
            else:
                print(f"\n❌ 安装失败!")
                print(f"   错误码: {result.error_code.code if result.error_code else 'N/A'}")
                print(f"   错误信息: {result.error_message}")
                return 1
                
        except EasyEnvError as e:
            print(f"\n❌ 安装出错: {e.error_info.to_user_message()}")
            return 1
        except KeyboardInterrupt:
            print(f"\n\n⚠️ 安装已取消")
            return 130
        except Exception as e:
            print(f"\n❌ 未知错误: {e}")
            return 1
    
    def list_envs(self, args):
        """列出支持的环境"""
        print("\n📦 EasyEnv 支持的环境:\n")
        
        envs = self.engine.get_supported_environments()
        
        for env in envs:
            is_installed, info = self.engine.check_installed(env)
            status = f"✅ 已安装 ({info})" if is_installed else "⭕ 未安装"
            print(f"  • {env:15} {status}")
        
        print()
        return 0
    
    def check(self, args):
        """检查环境状态"""
        print(f"\n🔍 检查环境: {args.env or '全部'}\n")
        
        if args.env:
            envs = [args.env]
        else:
            envs = self.engine.get_supported_environments()
        
        results = []
        for env in envs:
            is_installed, info = self.engine.check_installed(env)
            results.append({
                'env': env,
                'installed': is_installed,
                'info': info
            })
            
            if is_installed:
                print(f"  ✅ {env:15} 已安装: {info}")
            else:
                print(f"  ⭕ {env:15} 未安装")
        
        # JSON输出
        if args.json:
            print(f"\n{json.dumps(results, ensure_ascii=False, indent=2)}")
        
        print()
        return 0
    
    def config(self, args):
        """配置管理"""
        config_dir = os.path.join(os.path.expanduser('~'), '.easyenv')
        config_file = os.path.join(config_dir, 'config.json')
        
        if args.action == 'show':
            print(f"\n📋 EasyEnv 配置\n")
            print(f"  配置目录: {config_dir}")
            
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                print(f"  配置文件: {config_file}")
                print(f"  内容:\n{json.dumps(config_data, ensure_ascii=False, indent=4)}")
            else:
                print(f"  配置文件: 不存在（使用默认配置）")
            
            # 显示日志目录
            log_dir = os.path.join(config_dir, 'logs')
            print(f"  日志目录: {log_dir}")
            
            # 显示缓存目录
            cache_dir = os.path.join(config_dir, 'downloads')
            print(f"  缓存目录: {cache_dir}")
            
            # 显示磁盘使用
            import shutil
            if os.path.exists(cache_dir):
                total_size = 0
                for dirpath, dirnames, filenames in os.walk(cache_dir):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        total_size += os.path.getsize(fp)
                print(f"  缓存大小: {total_size / 1024 / 1024:.1f} MB")
            
            print()
            
        elif args.action == 'set':
            os.makedirs(config_dir, exist_ok=True)
            
            config_data = {}
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            
            # 设置镜像
            if args.mirror:
                config_data['default_mirror'] = args.mirror
                print(f"✅ 设置默认镜像: {args.mirror}")
            
            # 设置代理
            if args.proxy:
                config_data['proxy'] = args.proxy
                print(f"✅ 设置代理: {args.proxy}")
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 配置已保存到: {config_file}\n")
        
        elif args.action == 'clear':
            import shutil
            
            cache_dir = os.path.join(config_dir, 'downloads')
            if os.path.exists(cache_dir):
                shutil.rmtree(cache_dir)
                os.makedirs(cache_dir)
                print(f"✅ 已清理缓存目录: {cache_dir}\n")
            else:
                print(f"⚠️ 缓存目录不存在\n")
        
        return 0
    
    def logs(self, args):
        """查看日志"""
        log_dir = os.path.join(os.path.expanduser('~'), '.easyenv', 'logs')
        
        if args.latest:
            # 显示最近的日志
            log_files = sorted(
                [f for f in os.listdir(log_dir) if f.endswith('.jsonl')],
                reverse=True
            )
            
            if not log_files:
                print("暂无日志文件")
                return 0
            
            latest_log = os.path.join(log_dir, log_files[0])
            print(f"\n📋 最近日志: {log_files[0]}\n")
            
            with open(latest_log, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-(args.lines or 20):]
                for line in lines:
                    try:
                        entry = json.loads(line)
                        timestamp = entry.get('timestamp', '')[:19]
                        level = entry.get('level', 'INFO')
                        message = entry.get('message', '')
                        trace_id = entry.get('trace_id', '')
                        
                        level_icons = {
                            'DEBUG': '🔍',
                            'INFO': 'ℹ️',
                            'WARNING': '⚠️',
                            'ERROR': '❌',
                            'CRITICAL': '🔥',
                        }
                        icon = level_icons.get(level, '•')
                        
                        print(f"  {icon} [{timestamp}] [{trace_id}] {message}")
                        
                        if entry.get('error'):
                            print(f"      └─ 错误: {entry['error'].get('message', '')}")
                    except:
                        print(f"  {line.strip()}")
        
        elif args.audit:
            # 显示审计日志
            audit_file = os.path.join(log_dir, 'audit.jsonl')
            if not os.path.exists(audit_file):
                print("暂无审计日志")
                return 0
            
            print(f"\n📋 审计日志\n")
            
            with open(audit_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-(args.lines or 20):]
                for line in lines:
                    try:
                        entry = json.loads(line)
                        timestamp = entry.get('timestamp', '')[:19]
                        operation = entry.get('operation', '')
                        target = entry.get('target', '')
                        success = entry.get('success', False)
                        
                        icon = '✅' if success else '❌'
                        print(f"  {icon} [{timestamp}] {operation} -> {target}")
                    except:
                        pass
        
        print()
        return 0


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog='easyenv',
        description='EasyEnv - Windows开发环境一键部署工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  easyenv install python --version 3.12.0    安装Python 3.12.0
  easyenv install nodejs --mirror tuna       使用清华镜像安装Node.js
  easyenv list                               列出支持的环境
  easyenv check                              检查所有环境状态
  easyenv config show                        显示当前配置
  easyenv logs --latest                      查看最近日志

更多信息: https://github.com/LWJSTONE/EasyEnv
        """
    )
    
    parser.add_argument('-v', '--version', action='version', version='EasyEnv 2.0.0')
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # install 命令
    install_parser = subparsers.add_parser('install', help='安装开发环境')
    install_parser.add_argument('env', help='环境名称 (python, nodejs)')
    install_parser.add_argument('--version', '-V', help='指定版本')
    install_parser.add_argument('--system', action='store_true', help='系统级安装（需要管理员权限）')
    install_parser.add_argument('--mirror', '-m', help='使用指定镜像源')
    install_parser.add_argument('--no-path', action='store_true', help='不添加到PATH')
    install_parser.add_argument('--skip-verify', action='store_true', help='跳过校验')
    install_parser.set_defaults(func='install')
    
    # list 命令
    list_parser = subparsers.add_parser('list', help='列出支持的环境')
    list_parser.set_defaults(func='list_envs')
    
    # check 命令
    check_parser = subparsers.add_parser('check', help='检查环境状态')
    check_parser.add_argument('env', nargs='?', help='环境名称（可选）')
    check_parser.add_argument('--json', action='store_true', help='JSON格式输出')
    check_parser.set_defaults(func='check')
    
    # config 命令
    config_parser = subparsers.add_parser('config', help='配置管理')
    config_parser.add_argument('action', choices=['show', 'set', 'clear'], help='操作')
    config_parser.add_argument('--mirror', help='设置默认镜像源')
    config_parser.add_argument('--proxy', help='设置代理服务器')
    config_parser.set_defaults(func='config')
    
    # logs 命令
    logs_parser = subparsers.add_parser('logs', help='查看日志')
    logs_parser.add_argument('--latest', action='store_true', help='显示最近的日志')
    logs_parser.add_argument('--audit', action='store_true', help='显示审计日志')
    logs_parser.add_argument('--lines', '-n', type=int, default=20, help='显示行数')
    logs_parser.set_defaults(func='logs')
    
    return parser


def main():
    """CLI主入口"""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    cli = CLI()
    
    # 调用对应的方法
    func_name = args.func
    if hasattr(cli, func_name):
        return getattr(cli, func_name)(args)
    else:
        print(f"未知命令: {args.command}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
