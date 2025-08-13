import os

def is_utf8(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            f.read()
        return True
    except UnicodeDecodeError as e:
        print(f"[❌] {filepath} → {e}")
        return False

def scan_project(root_dir):
    print(f"🔍 Scanning files in: {root_dir}")
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(('.env', '.json', '.txt', '.csv', '.py')):
                full_path = os.path.join(dirpath, filename)
                is_utf8(full_path)

if __name__ == "__main__":
    scan_project(".")
