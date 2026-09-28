"""Build a source ZIP from a fixed allowlist; never include user data."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ['app.py', 'web/index.html', 'start-windows.cmd', 'start.sh',
         'config.example.json', 'examples/catalog.example.json', 'README.md',
         '.gitignore', 'tests/test_app.py', 'tools/build_release.py',
         '.github/workflows/test.yml']


def build():
    target = ROOT / 'dist' / 'autumn-job-tracker-v1.0.0.zip'
    target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in FILES:
            data = (ROOT / name).read_bytes()
            info = zipfile.ZipInfo('autumn-job-tracker/' + name)
            info.external_attr = (0o100755 if name == 'start.sh' else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    print(target)
    return target


if __name__ == '__main__':
    build()
