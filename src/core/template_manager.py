#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
环境模板管理器 - 支持配置文件导入/导出和预设模板
"""

import os
import json
import yaml
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class EnvironmentSpec:
    """环境规格"""
    name: str
    version: str = "latest"
    optional: bool = False
    pre_install: str = ""  # 安装前命令
    post_install: str = ""  # 安装后命令
    config: Dict = field(default_factory=dict)  # 环境特定配置


@dataclass
class EnvironmentTemplate:
    """环境模板"""
    name: str
    description: str
    author: str = ""
    version: str = "1.0"
    created_at: str = ""
    environments: List[EnvironmentSpec] = field(default_factory=list)
    scripts: Dict[str, str] = field(default_factory=dict)  # 预定义脚本
    variables: Dict[str, str] = field(default_factory=dict)  # 变量定义


class TemplateManager:
    """环境模板管理器"""
    
    TEMPLATES_DIR = os.path.join(os.path.expanduser('~'), '.easyenv', 'templates')
    
    # 预设模板
    PRESET_TEMPLATES = {
        'frontend': EnvironmentTemplate(
            name='frontend',
            description='前端开发环境 - Node.js, VS Code, Git',
            author='EasyEnv',
            environments=[
                EnvironmentSpec(name='nodejs', version='20'),
                EnvironmentSpec(name='git', version='latest'),
                EnvironmentSpec(name='vscode', version='latest'),
            ],
            scripts={
                'post_setup': 'npm install -g pnpm yarn',
            }
        ),
        'backend': EnvironmentTemplate(
            name='backend',
            description='后端开发环境 - Python, Git, VS Code',
            author='EasyEnv',
            environments=[
                EnvironmentSpec(name='python', version='3.12'),
                EnvironmentSpec(name='git', version='latest'),
                EnvironmentSpec(name='vscode', version='latest'),
            ],
            scripts={
                'post_setup': 'pip install virtualenv pipenv poetry',
            }
        ),
        'fullstack': EnvironmentTemplate(
            name='fullstack',
            description='全栈开发环境 - Node.js, Python, Git, VS Code',
            author='EasyEnv',
            environments=[
                EnvironmentSpec(name='nodejs', version='20'),
                EnvironmentSpec(name='python', version='3.12'),
                EnvironmentSpec(name='git', version='latest'),
                EnvironmentSpec(name='vscode', version='latest'),
            ]
        ),
        'java': EnvironmentTemplate(
            name='java',
            description='Java开发环境 - JDK, Maven/Gradle, Git, VS Code',
            author='EasyEnv',
            environments=[
                EnvironmentSpec(name='jdk', version='21'),
                EnvironmentSpec(name='git', version='latest'),
                EnvironmentSpec(name='vscode', version='latest'),
                EnvironmentSpec(name='cmake', version='latest', optional=True),
            ]
        ),
        'golang': EnvironmentTemplate(
            name='golang',
            description='Go开发环境 - Go, Git, VS Code',
            author='EasyEnv',
            environments=[
                EnvironmentSpec(name='go', version='1.21'),
                EnvironmentSpec(name='git', version='latest'),
                EnvironmentSpec(name='vscode', version='latest'),
            ]
        ),
        'rust': EnvironmentTemplate(
            name='rust',
            description='Rust开发环境 - Rust, Git, VS Code',
            author='EasyEnv',
            environments=[
                EnvironmentSpec(name='rust', version='stable'),
                EnvironmentSpec(name='git', version='latest'),
                EnvironmentSpec(name='vscode', version='latest'),
                EnvironmentSpec(name='cmake', version='latest', optional=True),
            ]
        ),
        'data_science': EnvironmentTemplate(
            name='data_science',
            description='数据科学环境 - Python, VS Code',
            author='EasyEnv',
            environments=[
                EnvironmentSpec(name='python', version='3.12'),
                EnvironmentSpec(name='git', version='latest'),
                EnvironmentSpec(name='vscode', version='latest'),
            ],
            scripts={
                'post_setup': 'pip install numpy pandas matplotlib scikit-learn jupyter',
            }
        ),
        'devops': EnvironmentTemplate(
            name='devops',
            description='DevOps环境 - Docker, Git, Python, VS Code',
            author='EasyEnv',
            environments=[
                EnvironmentSpec(name='docker', version='latest'),
                EnvironmentSpec(name='git', version='latest'),
                EnvironmentSpec(name='python', version='3.12'),
                EnvironmentSpec(name='vscode', version='latest'),
            ]
        ),
        'minimal': EnvironmentTemplate(
            name='minimal',
            description='最小开发环境 - Git, VS Code',
            author='EasyEnv',
            environments=[
                EnvironmentSpec(name='git', version='latest'),
                EnvironmentSpec(name='vscode', version='latest', optional=True),
            ]
        ),
        'cpp': EnvironmentTemplate(
            name='cpp',
            description='C/C++开发环境 - MinGW, CMake, Git, VS Code',
            author='EasyEnv',
            environments=[
                EnvironmentSpec(name='mingw', version='latest'),
                EnvironmentSpec(name='cmake', version='latest'),
                EnvironmentSpec(name='git', version='latest'),
                EnvironmentSpec(name='vscode', version='latest'),
            ]
        ),
    }
    
    def __init__(self):
        os.makedirs(self.TEMPLATES_DIR, exist_ok=True)
        self._load_custom_templates()
    
    def _load_custom_templates(self):
        """加载自定义模板"""
        for filename in os.listdir(self.TEMPLATES_DIR):
            if filename.endswith(('.json', '.yaml', '.yml')):
                try:
                    filepath = os.path.join(self.TEMPLATES_DIR, filename)
                    template = self.load_template(filepath)
                    if template and template.name:
                        self.PRESET_TEMPLATES[f"custom_{template.name}"] = template
                except Exception:
                    pass
    
    def get_template(self, name: str) -> Optional[EnvironmentTemplate]:
        """获取模板"""
        return self.PRESET_TEMPLATES.get(name)
    
    def get_all_templates(self) -> Dict[str, EnvironmentTemplate]:
        """获取所有模板"""
        return self.PRESET_TEMPLATES.copy()
    
    def get_template_list(self) -> List[Dict]:
        """获取模板列表（用于UI显示）"""
        result = []
        for name, template in self.PRESET_TEMPLATES.items():
            result.append({
                'name': name,
                'display_name': template.name,
                'description': template.description,
                'author': template.author,
                'env_count': len(template.environments),
                'is_custom': name.startswith('custom_'),
            })
        return result
    
    def create_template(self, name: str, description: str, 
                       environments: List[Dict]) -> EnvironmentTemplate:
        """创建新模板"""
        env_specs = []
        for env in environments:
            env_specs.append(EnvironmentSpec(
                name=env.get('name', ''),
                version=env.get('version', 'latest'),
                optional=env.get('optional', False),
                pre_install=env.get('pre_install', ''),
                post_install=env.get('post_install', ''),
                config=env.get('config', {}),
            ))
        
        template = EnvironmentTemplate(
            name=name,
            description=description,
            author='User',
            created_at=datetime.now().isoformat(),
            environments=env_specs,
        )
        
        return template
    
    def save_template(self, template: EnvironmentTemplate, 
                     filepath: str = None, format: str = 'json') -> str:
        """保存模板到文件"""
        if not filepath:
            filepath = os.path.join(
                self.TEMPLATES_DIR, 
                f"{template.name}.{format}"
            )
        
        data = {
            'name': template.name,
            'description': template.description,
            'author': template.author,
            'version': template.version,
            'created_at': template.created_at,
            'environments': [asdict(e) for e in template.environments],
            'scripts': template.scripts,
            'variables': template.variables,
        }
        
        if format == 'yaml' or filepath.endswith(('.yaml', '.yml')):
            with open(filepath, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
        else:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 添加到模板列表
        self.PRESET_TEMPLATES[f"custom_{template.name}"] = template
        
        return filepath
    
    def load_template(self, filepath: str) -> Optional[EnvironmentTemplate]:
        """从文件加载模板"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                if filepath.endswith(('.yaml', '.yml')):
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
            
            environments = []
            for env_data in data.get('environments', []):
                environments.append(EnvironmentSpec(
                    name=env_data.get('name', ''),
                    version=env_data.get('version', 'latest'),
                    optional=env_data.get('optional', False),
                    pre_install=env_data.get('pre_install', ''),
                    post_install=env_data.get('post_install', ''),
                    config=env_data.get('config', {}),
                ))
            
            return EnvironmentTemplate(
                name=data.get('name', ''),
                description=data.get('description', ''),
                author=data.get('author', ''),
                version=data.get('version', '1.0'),
                created_at=data.get('created_at', ''),
                environments=environments,
                scripts=data.get('scripts', {}),
                variables=data.get('variables', {}),
            )
        except Exception as e:
            return None
    
    def delete_template(self, name: str) -> bool:
        """删除自定义模板"""
        if not name.startswith('custom_'):
            return False
        
        template = self.PRESET_TEMPLATES.get(name)
        if not template:
            return False
        
        # 删除文件
        for ext in ['json', 'yaml', 'yml']:
            filepath = os.path.join(self.TEMPLATES_DIR, f"{template.name}.{ext}")
            if os.path.exists(filepath):
                os.remove(filepath)
        
        # 从内存中移除
        del self.PRESET_TEMPLATES[name]
        
        return True
    
    def export_to_file(self, template_name: str, output_path: str, 
                      format: str = 'json') -> bool:
        """导出模板到指定路径"""
        template = self.get_template(template_name)
        if not template:
            return False
        
        self.save_template(template, output_path, format)
        return True
    
    def create_from_selection(self, name: str, description: str,
                             selections: List[Dict]) -> EnvironmentTemplate:
        """从用户选择创建模板"""
        return self.create_template(name, description, selections)


class TemplateExecutor:
    """模板执行器"""
    
    def __init__(self, installer_manager):
        self.installer = installer_manager
    
    def execute_template(self, template: EnvironmentTemplate, 
                        progress_callback=None) -> Dict:
        """
        执行模板安装
        
        Returns:
            {
                'success': bool,
                'installed': List[str],
                'failed': List[str],
                'skipped': List[str],
            }
        """
        result = {
            'success': True,
            'installed': [],
            'failed': [],
            'skipped': [],
        }
        
        total = len(template.environments)
        
        for i, env_spec in enumerate(template.environments):
            if progress_callback:
                progress_callback(i, total, env_spec.name, "准备安装")
            
            # 执行预安装命令
            if env_spec.pre_install:
                try:
                    os.system(env_spec.pre_install)
                except Exception:
                    pass
            
            # 执行安装
            success = self._install_environment(env_spec)
            
            if success:
                result['installed'].append(env_spec.name)
                
                # 执行后安装命令
                if env_spec.post_install:
                    try:
                        os.system(env_spec.post_install)
                    except Exception:
                        pass
            else:
                if env_spec.optional:
                    result['skipped'].append(env_spec.name)
                else:
                    result['failed'].append(env_spec.name)
                    result['success'] = False
        
        # 执行模板级别的后置脚本
        if result['success'] and template.scripts.get('post_setup'):
            try:
                os.system(template.scripts['post_setup'])
            except Exception:
                pass
        
        return result
    
    def _install_environment(self, spec: EnvironmentSpec) -> bool:
        """安装单个环境"""
        # 这里调用实际的安装逻辑
        # 返回安装是否成功
        return True
