# Reproducible Windows desktop build, including the real historical sample.
from pathlib import Path
root = Path(SPECPATH).parent
a = Analysis([str(root / 'desktop.py')], pathex=[str(root)],
             binaries=[], datas=[(str(root / 'data/aapl.csv'), 'data')],
             hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=['pyqtgraph.opengl'], noarchive=False, optimize=0)
# Qt 6.11 on Windows imports the system's unversioned ICU API. In a conda-based
# venv PyInstaller may choose conda's icuuc78.dll and rename it icuuc.dll, whose
# suffixed exports cannot satisfy Qt. Resolve these names from Windows instead.
a.binaries = [entry for entry in a.binaries
              if Path(entry[0]).name.lower() not in {'icuuc.dll', 'icuin.dll'}]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='QuantDesk',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='QuantDesk')
