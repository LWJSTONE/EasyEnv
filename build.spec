# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置文件
用于将 EasyEnv 打包成单个 exe 文件
"""

import os
import sys

# 获取当前目录
block_cipher = None
current_dir = os.path.dirname(os.path.abspath(SPEC))

# 收集所有数据文件
datas = [
    # (源路径, 目标路径)
]

# 收集所有隐藏导入
hiddenimports = [
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'requests',
    'urllib3',
    'packaging',
    'packaging.version',
    'packaging.specifiers',
    'packaging.requirements',
]

# 二进制文件
binaries = []

a = Analysis(
    ['main.py'],
    pathex=[current_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'IPython',
        'jupyter',
        'PIL',
        'cv2',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='EasyEnv',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标: 'assets/icon.ico'
    version='version_info.txt',
    uac_admin=True,  # 请求管理员权限
    uac_uiaccess=False,
)
