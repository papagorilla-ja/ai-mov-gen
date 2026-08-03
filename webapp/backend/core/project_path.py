import os
from pathlib import Path

PROJECTS_DIR = Path("/app/projects")

def get_project_dir_name(project) -> str:
    """後方互換を考慮してプロジェクトのディレクトリ名（フォルダ名）を取得する。
    1. UUID ディレクトリが存在すれば UUID (project.id) を使う。
    2. UUID ディレクトリが存在せず、project.name ディレクトリが存在すれば project.name を使う。
    3. 新規作成時は project.id を使う。
    """
    id_dir = PROJECTS_DIR / project.id
    name_dir = PROJECTS_DIR / project.name
    
    if id_dir.exists():
        return project.id
    if name_dir.exists():
        return project.name
        
    return project.id

def get_project_dir(project) -> Path:
    """プロジェクトの絶対パスを取得する"""
    return PROJECTS_DIR / get_project_dir_name(project)
