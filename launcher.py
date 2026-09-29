"""Portable Windows entry point; all private files stay next to the executable."""
import json
import sys
from pathlib import Path
import app

def main():
    if '--self-test' in sys.argv:
        import pypdf
        for name in ('index.html','assistant.js','features.js','company.js','feedback.js','onboarding.js'):
            if not (app.BASE/'web'/name).is_file():raise RuntimeError('Missing UI file: '+name)
        print(json.dumps({'ok':True,'version':app.VERSION,'pdf':pypdf.__version__}))
        return
    if '--no-browser' not in sys.argv and '--open' not in sys.argv:sys.argv.append('--open')
    try:app.main()
    except SystemExit as error:
        if error.code and getattr(sys,'frozen',False) and sys.stdin and sys.stdin.isatty():
            input('Cannot start. Read the message above; press Enter to close. ')
        raise

if __name__=='__main__':main()
