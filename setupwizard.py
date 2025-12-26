import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import zipfile
import shutil
import urllib.request
import os
import subprocess
import sys
import traceback

# ================== DEBUG ==================
DEBUG = True
def debug(msg):
    if DEBUG:
        print(f"[SETUP-DEBUG] {msg}")

print("=== SETUP ENV DEBUG ===")
print("sys.executable:", sys.executable)
print("__file__:", __file__)
print("APPDATA env:", os.environ.get("APPDATA"))
print("HOME:", os.path.expanduser("~"))
print("=======================")

# ================== ENV ==================
IS_EXE = getattr(sys, "frozen", False)
debug(f"Running mode: {'EXE' if IS_EXE else 'PY'}")
debug(f"sys.executable = {sys.executable}")
debug(f"__file__ = {__file__}")

# ================== CONFIG ==================
APP_NAME = "Enchanted Launcher"
GITHUB_ZIP_URL = (
    "https://github.com/AdmerPRO/Enchanted_Launcher/"
    "archive/refs/heads/ELauncher-SetupWizard.zip"
)

# Domyślny folder instalacji = folder, gdzie jest setup + Enchanted_Launcher
SETUP_DIR = Path(__file__).parent.resolve()
DEFAULT_INSTALL_DIR = SETUP_DIR / "Enchanted_Launcher"
INSTALL_DIR = DEFAULT_INSTALL_DIR
ZIP_PATH = None
MAIN_EXE = None
MAIN_PY = None

debug(f"Default install dir: {INSTALL_DIR}")

# ================== INSTALL LOGIC ==================
def download_and_install(progress):
    global ZIP_PATH, MAIN_EXE, MAIN_PY
    try:
        debug("Starting installation")
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)

        ZIP_PATH = INSTALL_DIR / "setup.zip"
        MAIN_EXE = INSTALL_DIR / "main.exe"
        MAIN_PY = INSTALL_DIR / "main.py"

        debug(f"Downloading ZIP from: {GITHUB_ZIP_URL}")
        req = urllib.request.Request(
            GITHUB_ZIP_URL,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        with urllib.request.urlopen(req) as response, open(ZIP_PATH, "wb") as out:
            shutil.copyfileobj(response, out)

        debug(f"ZIP downloaded to: {ZIP_PATH}")

        with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
            names = zip_ref.namelist()
            root_folder = names[0].split("/")[0]

            debug(f"ZIP root folder: {root_folder}")
            debug(f"ZIP contains {len(names)} files")

            for member in names:
                if member.endswith("/"):
                    continue
                rel_path = Path(member).relative_to(root_folder)
                target = INSTALL_DIR / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                debug(f"Extracting: {rel_path}")
                with zip_ref.open(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)

        progress.stop()
        debug(f"ZIP preserved at: {ZIP_PATH}")
        return True

    except Exception as e:
        progress.stop()
        debug("INSTALL ERROR")
        traceback.print_exc()
        messagebox.showerror("Installation error", str(e))
        return False

# ================== SHORTCUT ==================
def create_desktop_shortcut():
    try:
        debug("Creating desktop shortcut")
        import winshell
        from win32com.client import Dispatch

        desktop = Path(winshell.desktop())
        shortcut_path = desktop / "Enchanted Launcher.lnk"

        shell = Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))

        if MAIN_EXE.exists():
            shortcut.Targetpath = str(MAIN_EXE)
        else:
            shortcut.Targetpath = sys.executable
            shortcut.Arguments = f'"{MAIN_PY}"'

        shortcut.WorkingDirectory = str(INSTALL_DIR)
        icon = INSTALL_DIR / "icon.ico"
        if icon.exists():
            shortcut.IconLocation = str(icon)

        shortcut.save()
        debug(f"Shortcut created: {shortcut_path}")

    except Exception as e:
        debug("SHORTCUT ERROR")
        traceback.print_exc()
        messagebox.showwarning("Shortcut", f"Failed to create shortcut:\n{e}")

# ================== OPENING FOLDER ==================
def open_install_folder():
    try:
        debug(f"Opening install folder: {INSTALL_DIR}")
        if INSTALL_DIR.exists():
            os.startfile(INSTALL_DIR)
        else:
            debug("Install folder does not exist")
            messagebox.showwarning("Folder", "Installation folder does not exist.")
    except Exception as e:
        debug("OPEN FOLDER ERROR")
        traceback.print_exc()
        messagebox.showwarning("Folder", f"Failed to open installation folder:\n{e}")

def open_zip_folder():
    try:
        if ZIP_PATH and ZIP_PATH.exists():
            os.startfile(ZIP_PATH.parent)
        else:
            messagebox.showwarning("ZIP Folder", "ZIP file not found.")
    except Exception as e:
        debug("OPEN ZIP FOLDER ERROR")
        traceback.print_exc()
        messagebox.showwarning("ZIP Folder", f"Failed to open ZIP folder:\n{e}")

# ================== RUN APP ==================
def run_installed_app():
    debug("Attempting to run installed app")
    if MAIN_EXE.exists():
        debug("Running main.exe")
        subprocess.Popen([str(MAIN_EXE)], cwd=str(INSTALL_DIR))
        return
    if MAIN_PY.exists():
        debug("Running main.py")
        subprocess.Popen([sys.executable, str(MAIN_PY)], cwd=str(INSTALL_DIR))
        return
    debug("No executable found to run")
    messagebox.showwarning("Run", "Installation completed, but no main.exe or main.py found.")

# ================== FOLDER CHOICE ==================
def choose_install_folder():
    global INSTALL_DIR
    selected = filedialog.askdirectory(
        title="Select installation folder",
        initialdir=SETUP_DIR
    )
    if selected:
        INSTALL_DIR = Path(selected) / "Enchanted_Launcher"
        install_dir_label.config(
            text=f"Program will be installed to:\n{INSTALL_DIR}"
        )
        debug(f"User selected install dir: {INSTALL_DIR}")

# ================== GUI ==================
root = tk.Tk()
root.title("Enchanted Launcher Setup")
root.geometry("500x350")
root.resizable(False, False)

frame = ttk.Frame(root, padding=20)
frame.pack(fill="both", expand=True)

ttk.Label(frame, text="Enchanted Launcher Setup", font=("Segoe UI", 14, "bold")).pack(pady=(0, 10))

install_dir_label = ttk.Label(frame, text=f"Program will be installed to:\n{INSTALL_DIR}", wraplength=460)
install_dir_label.pack(pady=10)

ttk.Button(frame, text="Choose folder...", command=choose_install_folder).pack(pady=(0, 10))

progress = ttk.Progressbar(frame, mode="indeterminate")
progress.pack(fill="x", pady=10)

create_shortcut_var = tk.BooleanVar(value=True)
run_after_var = tk.BooleanVar(value=True)
open_folder_var = tk.BooleanVar(value=False)
open_zip_var = tk.BooleanVar(value=False)

ttk.Checkbutton(frame, text="Create desktop shortcut", variable=create_shortcut_var).pack(anchor="w")
ttk.Checkbutton(frame, text="Run Enchanted Launcher after install", variable=run_after_var).pack(anchor="w")
ttk.Checkbutton(frame, text="Open installation folder", variable=open_folder_var).pack(anchor="w")
ttk.Checkbutton(frame, text="Open ZIP folder after install", variable=open_zip_var).pack(anchor="w")

def start_install():
    debug("Install button clicked")
    progress.start(10)
    root.update()

    ok = download_and_install(progress)
    if not ok:
        debug("Installation failed")
        return

    if create_shortcut_var.get():
        create_desktop_shortcut()

    if run_after_var.get():
        run_installed_app()

    if open_folder_var.get():
        open_install_folder()

    if open_zip_var.get():
        open_zip_folder()

    messagebox.showinfo("Done", "Installation completed successfully")
    debug("Setup finished")
    root.destroy()

ttk.Button(frame, text="Install", command=start_install).pack(pady=15)

root.mainloop()
