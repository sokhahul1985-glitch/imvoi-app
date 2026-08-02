"""
PyInstaller Build Script for Imvoi AI OCR & VIP Receipt App
Packages main.py into a standalone executable Windows Application.
"""
import sys
import subprocess
import os

def build_executable():
    print("=" * 60)
    print("Building Imvoi Standalone Windows Executable (.exe)")
    print("=" * 60)

    # Collect data files that exist in directory
    data_files = []
    for asset in ["cmp_logo.png", "invoice_counter.json", "saved_customers.json"]:
        if os.path.exists(asset):
            data_files.append(f"--add-data={asset};.")

    venv_pyinstaller = os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "pyinstaller.exe")
    if os.path.exists(venv_pyinstaller):
        pyinstaller_bin = venv_pyinstaller
    else:
        pyinstaller_bin = os.path.join(os.path.dirname(sys.executable), "Scripts", "pyinstaller.exe")
        if not os.path.exists(pyinstaller_bin):
            pyinstaller_bin = "pyinstaller"


    # PyInstaller options
    cmd = [
        pyinstaller_bin,
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name=ImvoiApp",
    ] + data_files + [
        "--clean",
        "main.py"
    ]


    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("\n" + "=" * 60)
        print("BUILD SUCCESSFUL!")
        print("Executable output located at: dist\\ImvoiApp\\ImvoiApp.exe")
        print("=" * 60)
    else:
        print(f"\nBuild failed with exit code {result.returncode}")

if __name__ == "__main__":
    build_executable()
