#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
构建脚本 - 跨平台版本
"""

import os
import sys
import shutil
import subprocess


def clean_build():
    """清理构建目录"""
    dirs_to_remove = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"已删除: {dir_name}")
    
    # 删除 .spec 文件产生的缓存
    for file in os.listdir('.'):
        if file.endswith('.pyc') or file.endswith('.pyo'):
            os.remove(file)


def install_dependencies():
    """安装依赖"""
    print("正在安装依赖...")
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt', '-q'])


def create_version_info():
    """创建版本信息文件"""
    version_info = '''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'080404b0',
        [StringStruct(u'CompanyName', u'EasyEnv'),
        StringStruct(u'FileDescription', u'Windows开发环境一键部署工具'),
        StringStruct(u'FileVersion', u'1.0.0.0'),
        StringStruct(u'InternalName', u'EasyEnv'),
        StringStruct(u'LegalCopyright', u'Copyright (c) 2024 EasyEnv'),
        StringStruct(u'OriginalFilename', u'EasyEnv.exe'),
        StringStruct(u'ProductName', u'EasyEnv'),
        StringStruct(u'ProductVersion', u'1.0.0.0')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [2052, 1200])])
  ]
)
'''
    with open('version_info.txt', 'w', encoding='utf-8') as f:
        f.write(version_info)
    print("已创建版本信息文件")


def build_exe():
    """构建 exe 文件"""
    print("正在构建 exe 文件...")
    
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        'build.spec',
        '--clean',
        '--noconfirm'
    ]
    
    result = subprocess.run(cmd)
    return result.returncode == 0


def main():
    """主函数"""
    print("=" * 50)
    print("   EasyEnv 构建脚本")
    print("   Windows开发环境一键部署工具")
    print("=" * 50)
    print()
    
    # 切换到脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"工作目录: {script_dir}")
    print()
    
    # 步骤1: 安装依赖
    print("[1/4] 安装依赖...")
    install_dependencies()
    print()
    
    # 步骤2: 清理旧的构建文件
    print("[2/4] 清理旧的构建文件...")
    clean_build()
    print()
    
    # 步骤3: 创建版本信息
    print("[3/4] 创建版本信息...")
    create_version_info()
    print()
    
    # 步骤4: 构建
    print("[4/4] 构建 exe 文件...")
    success = build_exe()
    print()
    
    if success and os.path.exists('dist/EasyEnv.exe'):
        size = os.path.getsize('dist/EasyEnv.exe')
        print("=" * 50)
        print("   构建成功！")
        print("=" * 50)
        print(f"   输出文件: dist/EasyEnv.exe")
        print(f"   文件大小: {size / 1024 / 1024:.2f} MB")
        print()
    else:
        print("=" * 50)
        print("   构建失败！请检查错误信息")
        print("=" * 50)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
