@echo off
chcp 65001 >nul
echo ========================================
echo    EasyEnv 构建脚本
echo    Windows开发环境一键部署工具
echo ========================================
echo.

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python 环境，请先安装 Python 3.8+
    pause
    exit /b 1
)

echo [1/5] 检查并安装依赖...
pip install -r requirements.txt -q

echo [2/5] 清理旧的构建文件...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "__pycache__" rmdir /s /q "__pycache__"

echo [3/5] 创建版本信息...
python -c "
VSVersionInfo = '''
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
print('version_info.txt 创建成功')
"

echo [4/5] 使用 PyInstaller 打包...
pyinstaller build.spec --clean

echo [5/5] 检查构建结果...
if exist "dist\EasyEnv.exe" (
    echo.
    echo ========================================
    echo    构建成功！
    echo ========================================
    echo.
    echo 输出文件: dist\EasyEnv.exe
    
    REM 显示文件大小
    for %%A in ("dist\EasyEnv.exe") do echo 文件大小: %%~zA 字节 ^(约 %%~zAKB^)
    
    echo.
    echo 您可以将 EasyEnv.exe 复制到任意位置使用
    echo.
) else (
    echo.
    echo ========================================
    echo    构建失败！
    echo ========================================
    echo 请检查错误信息并重试
    echo.
)

pause
