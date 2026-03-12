# EasyEnv - Windows开发环境一键部署工具

<div align="center">

![EasyEnv Logo](assets/logo.png)

**一键安装Python、Node.js、Git、VSCode、JDK、Go等开发环境**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)

</div>

---

## 📖 简介

EasyEnv 是一款专为 Windows 平台设计的开发环境一键部署工具。它提供了简洁美观的图形界面，让您能够快速安装和管理常用的开发环境，无需手动下载和配置。

### ✨ 主要特性

- 🎨 **简洁美观的UI** - 现代化界面设计，操作直观便捷
- 📦 **一键批量安装** - 支持同时选择多个环境一键安装
- 🔖 **版本自由选择** - 每个环境支持多版本选择
- 📊 **实时进度显示** - 清晰的安装进度和日志输出
- 🔍 **环境检测** - 自动检测已安装的开发环境
- 🚀 **单文件部署** - 仅需一个 exe 文件，复制即用

---

## 🛠️ 支持的开发环境

| 环境 | 图标 | 支持版本 |
|------|------|----------|
| Python | 🐍 | 3.12, 3.11, 3.10, 3.9, 3.8 |
| Node.js | 💚 | 20.x, 18.x, 16.x, 14.x |
| Git | 🔀 | 2.43, 2.42, 2.41, 2.40, 2.39 |
| VS Code | 💠 | 最新版 |
| OpenJDK | ☕ | 21, 17, 11, 8 |
| Go | 🔵 | 1.21, 1.20, 1.19, 1.18 |
| Rust | 🦀 | stable, beta, nightly |
| CMake | 📐 | 3.28, 3.27, 3.26, 3.25 |
| MinGW-w64 | ⚙️ | 13.2, 12.2, 11.2 |
| Docker Desktop | 🐳 | 最新版 |

---

## 📥 下载安装

### 方式一：直接下载 exe 文件

1. 前往 [Releases](../../releases) 页面
2. 下载最新的 `EasyEnv.exe`
3. 双击运行即可（建议以管理员身份运行）

### 方式二：从源码构建

```bash
# 克隆仓库
git clone https://github.com/LWJSTONE/EasyEnv.git
cd EasyEnv

# 安装依赖
pip install -r requirements.txt

# 运行开发版本
python main.py

# 构建单文件 exe
python scripts/build.py
```

---

## 📋 使用说明

### 基本操作

1. **选择环境** - 在"环境安装"选项卡中勾选需要安装的开发环境
2. **选择版本** - 使用下拉框选择所需的版本
3. **一键安装** - 点击"一键安装"按钮开始安装
4. **查看进度** - 在底部进度条和"安装日志"选项卡中查看进度

### 界面说明

```
┌─────────────────────────────────────────────────────────┐
│                    EasyEnv 标题栏                        │
├─────────────────────────────────────────────────────────┤
│  [📦 环境安装] [✅ 已安装环境] [📋 安装日志]              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 🐍 Python 3.12      [版本选择 ▼]    [✓] 选择    │   │
│  │    Python编程语言环境                            │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 💚 Node.js 20.x    [版本选择 ▼]    [ ] 选择     │   │
│  │    JavaScript运行时环境                          │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│                        ...                              │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  准备就绪                          [全选] [🚀 一键安装] │
│  [████████████████████████████████] 100%               │
└─────────────────────────────────────────────────────────┘
```

---

## 🔧 系统要求

- **操作系统**: Windows 10/11 (64位)
- **权限**: 建议以管理员身份运行
- **网络**: 需要稳定的网络连接以下载安装包

---

## 📁 项目结构

```
EasyEnv/
├── main.py              # 主入口文件
├── requirements.txt     # Python 依赖
├── build.spec          # PyInstaller 配置
├── src/
│   ├── ui/
│   │   └── main_window.py    # 主界面 UI
│   ├── core/
│   │   ├── env_manager.py    # 环境管理器
│   │   └── installer.py      # 安装器
│   └── utils/
│       └── helpers.py        # 辅助函数
├── scripts/
│   ├── build.bat        # Windows 构建脚本
│   └── build.py        # 跨平台构建脚本
├── assets/             # 资源文件
└── README.md           # 说明文档
```

---

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

---

## 📄 开源协议

本项目采用 MIT 协议开源 - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) - 优秀的 Python GUI 框架
- [PyInstaller](https://pyinstaller.org/) - Python 打包工具
- 各开发环境的官方发布源

---

## 📮 联系方式

如有问题或建议，请提交 [Issue](../../issues)

<div align="center">

**⭐ 如果这个项目对您有帮助，请给一个 Star！⭐**

Made with ❤️ by LWJSTONE

</div>
