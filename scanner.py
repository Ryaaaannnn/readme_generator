import os
from pathlib import Path
from typing import Dict, Set

# 定義需要忽略的目錄與檔案
IGNORE_DIRS: Set[str] = {".git", "__pycache__", "node_modules", "venv", ".venv", ".idea", ".vscode", "dist", "build"}
IGNORE_FILES: Set[str] = {".env", ".env.local", ".DS_Store"}

# 定義需要讀取內容的核心檔案名稱與副檔名
TARGET_FILES: Set[str] = {"requirements.txt", "package.json", "go.mod", "Cargo.toml", "main.py", "app.ts", "index.js"}
TARGET_EXTS: Set[str] = {".py", ".ts", ".js", ".go", ".rs"}

class ProjectScanner:
    """負責優雅地掃描目錄結構並提取核心檔案內容。"""
    
    def __init__(self, target_path: str):
        self.root_path = Path(target_path).resolve()
        if not self.root_path.exists() or not self.root_path.is_dir():
            raise ValueError(f"目標路徑無效或不存在: {self.root_path}")

    def generate_tree(self) -> str:
        """生成專案目錄樹狀結構字串。"""
        tree_lines = []
        
        def _walk(path: Path, prefix: str = ""):
            try:
                entries = sorted([e for e in path.iterdir() if e.name not in IGNORE_DIRS and e.name not in IGNORE_FILES])
            except PermissionError:
                return

            entries_count = len(entries)
            for i, entry in enumerate(entries):
                connector = "├── " if i < entries_count - 1 else "└── "
                tree_lines.append(f"{prefix}{connector}{entry.name}")
                
                if entry.is_dir():
                    extension = "│   " if i < entries_count - 1 else "    "
                    _walk(entry, prefix + extension)

        tree_lines.append(f"📁 {self.root_path.name}/")
        _walk(self.root_path)
        return "\n".join(tree_lines)

    def get_core_files_content(self, max_files: int = 10, max_lines_per_file: int = 300) -> Dict[str, str]:
        """讀取核心構建檔案與部分源碼檔案的內容，以便後續分析。"""
        files_content: Dict[str, str] = {}
        
        for root, dirs, files in os.walk(self.root_path):
            # 過濾忽略的目錄，避免遞迴進入
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for file_name in files:
                if file_name in IGNORE_FILES:
                    continue
                    
                file_path = Path(root) / file_name
                ext = file_path.suffix
                
                # 判斷是否為「依賴配置」或「核心代碼」
                if file_name in TARGET_FILES or (ext in TARGET_EXTS and len(files_content) < max_files):
                    rel_path = file_path.relative_to(self.root_path).as_posix()
                    
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                            # 限制讀取行數，避免 Token 爆炸
                            content = "".join(lines[:max_lines_per_file])
                            if len(lines) > max_lines_per_file:
                                content += f"\n... (truncated {len(lines) - max_lines_per_file} lines)"
                            files_content[rel_path] = content
                    except Exception as e:
                        files_content[rel_path] = f"Error reading file {file_name}: {e}"
                        
        return files_content
