# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- CLI interface for headless operation (`cli.py`)
- Security verification module with hash checking
- Audit logging for system modifications
- Transaction-based installation with rollback support

## [2.0.0] - 2024-01-XX

### Added

#### Core Features
- **Dynamic Version Management**: Fetch latest versions from official APIs instead of hardcoded lists
- **Mirror Source Support**: Support for Chinese mirrors (Tsinghua, USTC, Aliyun, Huawei Cloud)
- **Advanced Downloader**: Retry mechanism, multi-threaded downloads, progress tracking
- **Installation Rollback**: Transaction-based rollback on failure
- **Environment Templates**: Preset templates and JSON/YAML import/export
- **Multi-version Management**: Support multiple versions coexistence
- **Lifecycle Management**: Uninstall and version switching support

#### Architecture
- **Structured Logging**: JSON logs with trace IDs for debugging
- **Error Code System**: Unified error codes with actionable suggestions
- **Security Module**: URL validation, hash verification, path sanitization
- **Audit System**: Track all system modifications for compliance

#### Developer Experience
- **CLI Interface**: Command-line tool for CI/CD integration
- **Decoupled Core**: Business logic separated from UI for reusability
- **Unit Tests**: Comprehensive test coverage for core modules
- **CI/CD Pipeline**: GitHub Actions for automated testing and builds

### Changed
- Complete rewrite of version manager to use dynamic APIs
- Refactored installer to support transaction-based rollback
- Improved error handling with structured error codes
- Enhanced security with certificate verification and hash checking

### Fixed
- Fixed hardcoded version numbers that quickly became outdated
- Fixed missing mirror source support for Chinese users
- Fixed lack of retry mechanism for downloads
- Fixed insufficient error handling and logging

## [1.0.0] - 2024-01-XX

### Added
- Initial release with basic GUI
- Support for Python, Node.js, Git, VS Code, JDK, Go, Rust, CMake, MinGW, Docker
- Basic installation functionality
- Simple environment detection
- Single-file executable packaging with PyInstaller

---

## Version Naming Convention

- **Major (X.0.0)**: Breaking changes, major architecture rewrites
- **Minor (2.X.0)**: New features, backward compatible
- **Patch (2.0.X)**: Bug fixes, minor improvements

## Support Policy

- Current major version (2.x): Active development and support
- Previous major version (1.x): Security fixes only
- End of life versions: No longer maintained
