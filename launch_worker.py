"""Lanza overnight.py como proceso independiente de Windows sin ventana."""
import subprocess, sys, os, pathlib

root = pathlib.Path(__file__).parent
python = root / "backend" / "venv" / "Scripts" / "python.exe"
script = root / "overnight.py"

CREATE_NO_WINDOW = 0x08000000

proc = subprocess.Popen(
    [str(python), str(script)],
    cwd=str(root),
    creationflags=CREATE_NO_WINDOW,
    stdout=open(root / "overnight_log.txt", "w", encoding="utf-8"),
    stderr=subprocess.STDOUT,
)
print(f"Worker nocturno lanzado. PID={proc.pid}")
print(f"Log: {root / 'overnight_log.txt'}")
