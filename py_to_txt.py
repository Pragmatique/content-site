import os
import fnmatch

# === Настройки ===
OUTPUT_FILE = "project_dump.txt"  # итоговый файл
ROOT_DIR = os.getcwd()  # корень проекта
IGNORED_DIRS = {".venv", "venv", "__pycache__", ".git"}  # папки для игнора
IGNORED_FILES = {"*.pyc", "*.pyo", "*.log", "*.md", "*.json", "*.txt"}  # маски файлов для игнора


def is_empty_init(file_path):
    """Проверяет, является ли файл __init__.py пустым"""
    return os.path.basename(file_path) == "__init__.py" and os.path.getsize(file_path) == 0


def is_ignored(file_name, dir_path):
    """Проверка, игнорируется ли файл"""
    # Игнорируем по маскам
    for pattern in IGNORED_FILES:
        if fnmatch.fnmatch(file_name, pattern):
            return True
    return False


def collect_python_files(root):
    """Собирает все .py файлы, исключая игнорируемые"""
    python_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Убираем игнорируемые директории
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        for filename in filenames:
            if filename.endswith(".py") and not is_ignored(filename, dirpath):
                full_path = os.path.join(dirpath, filename)
                if not is_empty_init(full_path):
                    python_files.append(full_path)
    return sorted(python_files)


def relative_path(path, root):
    """Возвращает относительный путь от root"""
    return os.path.relpath(path, root).replace("\\", "/")


def build_dump(root, output_file):
    files = collect_python_files(root)
    with open(output_file, "w", encoding="utf-8") as out:
        for file_path in files:
            rel_path = relative_path(file_path, root)
            out.write(f"\n# {rel_path}\n")
            with open(file_path, "r", encoding="utf-8") as f:
                out.write(f.read())
                out.write("\n")
    print(f"Собрано {len(files)} файлов в {output_file}")


if __name__ == "__main__":
    build_dump(ROOT_DIR, OUTPUT_FILE)