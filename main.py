import minecraft_launcher_lib as mc
import subprocess
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, PhotoImage
from pathlib import Path
import shutil
import traceback
import json
import sys
import zipfile
import urllib.request
import urllib.error
import os
import webbrowser
import time
import gzip

GITHUB_URL = "https://github.com/AdmerPRO/Enchanted_Launcher"
DISCORD_URL = "https://discord.gg/qTfWSFP2MQ"

minecraft_proc = None

mc_dir = Path(mc.utils.get_minecraft_directory())

ALLOWED_VERSIONS = [
    "1.16.2",
    "1.17.1",
    "1.18.2",
    "1.20.2",
    "1.21.2",
    "1.21.8",
    "1.21.10"
]

HIGHLIGHT_VERSION = "1.21.8"

if getattr(sys, 'frozen', False):
    # if running as exe file
    launcher_dir = Path(sys.executable).parent
else:
    # if running as py file
    launcher_dir = Path(__file__).parent

CONFIG_FILE = launcher_dir / "launcher_config.json"

mods_root = launcher_dir / "mods"
mods_root.mkdir(exist_ok=True)

logs_dir = launcher_dir / "logs"
logs_dir.mkdir(exist_ok=True)

# ------------------ WEBSITES ------------------

def open_github():
    webbrowser.open(GITHUB_URL)

def open_discord():
    webbrowser.open(DISCORD_URL)

def open_account():
    pass

# ------------------ FOLDER INIT ------------------

# mods/
mods_root.mkdir(exist_ok=True)

# mods/temp-mods
(mods_root / "temp-mods").mkdir(exist_ok=True)

# mods/enchanted-packs (TYLKO TEN FOLDER)
(mods_root / "enchanted-packs").mkdir(exist_ok=True)

# mods/fabric-<version> dla każdej wersji
for v in ALLOWED_VERSIONS:
    (mods_root / f"fabric-{v}").mkdir(exist_ok=True)

# ------------------ MOD PACK HELPERS ------------------

def get_mod_display_name(filename: str):
    """Removes 'locked_el-' prefix for display in GUI"""
    if filename.startswith("locked_el-"):
        return filename.replace("locked_el-", "")
    return filename

def copy_active_mods(src_dir: Path, dst_dir: Path):
    """Copy .jar and .mrpack mods from src_dir to dst_dir"""
    if not src_dir.exists():
        return
    for f in src_dir.iterdir():
        if f.suffix in (".jar", ".mrpack") and not f.name.endswith(".disabled"):
            shutil.copy(f, dst_dir / f"tmp_el_{f.name}")

# ------------------ CONFIG LOADERS ------------------

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(data: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# ------------------ LOGIC ------------------

def rotate_logs():
    latest_log = logs_dir / "latest.txt"
    if latest_log.exists():
        mtime = time.strftime("%Y-%m-%d-%H%M%S", time.localtime(latest_log.stat().st_mtime))
        archive_path = logs_dir / f"{mtime}.log.gz"
        
        try:
            with open(latest_log, 'rb') as f_in:
                with gzip.open(archive_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            latest_log.unlink()
        except Exception as e:
            print(f"[DEBUG] Error in log rotation: {e}")

def is_minecraft_running():
    global minecraft_proc
    return minecraft_proc is not None and minecraft_proc.poll() is None

def install_enchanted_pack(version: str):
    try:
        packs_root = mods_root / "enchanted-packs"
        target_dir = packs_root / f"fabric-{version}"
        target_dir.mkdir(parents=True, exist_ok=True)

        zip_path = packs_root / f"fabric-{version}.zip"
        repo_url = f"https://github.com/AdmerPRO/Enchanted_Launcher/archive/refs/heads/enchanted-pack-{version}.zip"

        print(f"[DEBUG] Downloading enchanted pack from: {repo_url}")
        req = urllib.request.Request(repo_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(zip_path, "wb") as out_file:
            shutil.copyfileobj(response, out_file)
        print(f"[DEBUG] Download complete: {zip_path}")

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            members = zip_ref.namelist()
            print(f"[DEBUG] ZIP contains {len(members)} entries")
            for member in members:
                prefix = f"Enchanted_Launcher-enchanted-pack-{version}/mods/"
                if member.startswith(prefix) and member.endswith((".jar", ".mrpack")):
                    filename = Path(member).name
                    with zip_ref.open(member) as src, open(target_dir / filename, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                        print(f"[DEBUG] Installed mod: {filename}")

        zip_path.unlink(missing_ok=True)
        print(f"[DEBUG] Enchanted pack installed for version {version}")

    except urllib.error.HTTPError as e:
        print(f"[ERROR] Failed to download enchanted pack: {e}")
        messagebox.showerror("Download Error", f"Failed to download enchanted pack for {version}.\nHTTP Error {e.code}")
    except Exception as e:
        print("[ERROR] Exception during enchanted pack installation")
        traceback.print_exc()
        messagebox.showerror("Error", f"Failed to install enchanted pack for {version}.\n{e}")

def check_enchanted_mods(version: str) -> bool:
    packs_root = mods_root / "enchanted-packs"
    target_dir = packs_root / f"fabric-{version}"
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        zip_path = packs_root / f"fabric-{version}.zip"
        repo_url = f"https://github.com/AdmerPRO/Enchanted_Launcher/archive/refs/heads/enchanted-pack-{version}.zip"

        print(f"[DEBUG] Checking enchanted pack for version {version} at: {repo_url}")
        req = urllib.request.Request(repo_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(zip_path, "wb") as out_file:
            shutil.copyfileobj(response, out_file)
        print(f"[DEBUG] Downloaded pack for check: {zip_path}")

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            repo_mods = [
                Path(member).name
                for member in zip_ref.namelist()
                if member.startswith(f"Enchanted_Launcher-enchanted-pack-{version}/mods/") and member.endswith((".jar", ".mrpack"))
            ]
        print(f"[DEBUG] Mods in repo: {repo_mods}")

        zip_path.unlink(missing_ok=True)
        missing_mods = [f for f in repo_mods if not (target_dir / f).exists()]
        print(f"[DEBUG] Missing mods: {missing_mods}")

        if not missing_mods:
            print(f"[DEBUG] All enchanted mods are installed for {version}")
            return True

        res = messagebox.askyesno(
            "Missing Enchanted Mods",
            f"Some mods from Enchanted Pack {version} are not installed:\n{missing_mods}\n"
            f"Do you want to download/update them?"
        )
        if res:
            print(f"[DEBUG] User chose to install missing mods for {version}")
            install_enchanted_pack(version)
            return True
        else:
            print(f"[DEBUG] User canceled enchanted mod update for {version}")
            return False

    except urllib.error.HTTPError as e:
        print(f"[ERROR] Failed to download enchanted pack for check: {e}")
        messagebox.showerror("Download Error", f"Failed to check enchanted pack for {version}.\nHTTP Error {e.code}")
        return False
    except Exception as e:
        print("[ERROR] Exception during checking enchanted mods")
        traceback.print_exc()
        return True

def sync_version_to_mods(version):
    global mods_preview_version
    if version in mods_version_combo["values"]:
        mods_version_combo.set(version)
        mods_preview_version = version
        refresh_mods_list()

def list_fabric_versions():
    print("=== Installed Fabric Versions ===")
    installed_versions = mc.utils.get_installed_versions(str(mc_dir))
    for idx, v in enumerate(ALLOWED_VERSIONS):
        matching_ids = [
            iv["id"] for iv in installed_versions
            if iv.get("id", "").startswith("fabric-loader") and v in iv.get("id", "")
        ]
        if matching_ids:
            for mid in matching_ids:
                print(f"[{idx}] Version {v} -> ID: {mid}")
        else:
            print(f"[{idx}] Version {v} -> Not installed")
    print("================================")

list_fabric_versions()


def valid_username(name: str) -> bool:
    return 3 <= len(name) <= 12 and re.fullmatch(r"[A-Za-z0-9_]+", name)

def fabric_id_for(version: str) -> str | None:
    fabric_versions = []

    for v in mc.utils.get_installed_versions(str(mc_dir)):
        vid = v.get("id", "")
        if vid.startswith("fabric-loader") and vid.endswith(version):
            # fabric-loader-0.18.4-1.21.8
            parts = vid.split("-")
            if len(parts) >= 3:
                loader_version = parts[2]
                fabric_versions.append((loader_version, vid))

    if not fabric_versions:
        return None

    # sortujemy po wersji loadera (semver)
    fabric_versions.sort(
        key=lambda x: [int(p) for p in x[0].split(".")]
    )

    return fabric_versions[-1][1]  # NAJNOWSZY

def install_fabric(version):
    try:
        mc.fabric.install_fabric(version, str(mc_dir))
        install_enchanted_pack(version)
        refresh_versions()
        refresh_mods_versions()
        messagebox.showinfo("Success", f"Fabric {version} installed")
    except Exception as e:
        messagebox.showerror("Error", str(e))

def prepare_mods(version: str):
    mc_mods = mc_dir / "mods"
    mc_mods.mkdir(exist_ok=True)

    temp_mods = mods_root / "temp-mods"
    temp_mods.mkdir(exist_ok=True)

    # Move all user mods and enchanted mods to temp
    for ext in ("*.jar", "*.mrpack"):
        for f in mc_mods.glob(ext):
            shutil.move(f, temp_mods / f.name)

    # Copy user mods
    user_dir = mods_root / f"fabric-{version}"
    copy_active_mods(user_dir, mc_mods)

    # Copy enchanted mods
    enchanted_dir = mods_root / "enchanted-packs" / f"fabric-{version}"
    copy_active_mods(enchanted_dir, mc_mods)

def restore_mods():
    time.sleep(1)
    mc_mods = mc_dir / "mods"
    temp_mods = mods_root / "temp-mods"

    # remove temporary mods
    for ext in ("tmp_el_*.jar", "tmp_el_*.mrpack"):
        for f in mc_mods.glob(ext):
            f.unlink(missing_ok=True)

    # restore original mods
    for ext in ("*.jar", "*.mrpack"):
        for f in temp_mods.glob(ext):
            shutil.move(f, mc_mods / f.name)


def launch_game():
    try:
        username = username_entry.get().strip()

        config = load_config()
        config["username"] = username
        save_config(config)

        version_idx = versions_list.curselection()
        if version_idx:
            version = versions_list.get(version_idx[0])
            print(version)
            print(version_idx)
        else:
            version = None

        print(f"[DEBUG] Selected username: '{username}'")
        print(f"[DEBUG] Selected version index: {version_idx}, value: {version}")

        if not username or not valid_username(username):
            messagebox.showwarning("Invalid username", "Username must be 3–12 characters (A–Z, 0–9, _)")
            print("[DEBUG] Invalid username")
            return

        if not version:
            messagebox.showwarning("Version", "Select a version")
            print("[DEBUG] No version selected")
            return
        
        if not check_enchanted_mods(version):
            print("[DEBUG] User cancelled enchanted mod update")
            return

        print("[DEBUG] Preparing mods...")
        prepare_mods(version)
        print("[DEBUG] Mods prepared")

        settings = {
            "username": username,
            "uuid": "17cadab7-deb2-4208-90fa-16d2df7d072b", 
            "token": "offline"
        }

        version_id = fabric_id_for(version)

        if not version_id:
            show_progress()

            def install_and_continue():
                try:
                    mc.fabric.install_fabric(version, str(mc_dir))
                    install_enchanted_pack(version)
                    refresh_versions()
                    refresh_mods_versions()
                except Exception as e:
                    root.after(0, lambda: messagebox.showerror("Install Error", str(e)))
                    root.after(0, hide_progress)
                    return

                root.after(0, hide_progress)
                root.after(0, launch_game)

            threading.Thread(target=install_and_continue, daemon=True).start()
            return
        
        print(version_id)

        print("[DEBUG] Creating Minecraft launch command...")
        cmd = mc.command.get_minecraft_command(version_id, mc_dir, settings)
        print(f"[DEBUG] Command: {cmd}")

        def run_game():
            print("[DEBUG] Launching Minecraft...")
            global minecraft_proc
            
            rotate_logs()
            latest_log_path = logs_dir / "latest.txt"
            
            try:
                # Otwieramy plik w trybie zapisu
                with open(latest_log_path, "w", encoding="utf-8") as log_file:
                    minecraft_proc = subprocess.Popen(
                        cmd,
                        cwd=str(mc_dir),
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        stdout=log_file,
                        stderr=subprocess.STDOUT
                    )
                    
                    minecraft_proc.wait()
            except Exception as e:
                print(f"[ERROR] Launcher log error: {e}")
            
            print("[DEBUG] Minecraft exited, restoring mods...")
            time.sleep(2)
            restore_mods()
            print("[DEBUG] Mods restored")

        threading.Thread(target=run_game, daemon=True).start()

    except Exception as e:
        print("[DEBUG] Exception occurred during launch_game:")
        traceback.print_exc()
        messagebox.showerror("Launch Error", str(e))

def set_active_version(version):
    config = load_config()
    config["last_version"] = version
    save_config(config)

    sync_version_to_mods(version)

def on_username_change(event=None):
    username = username_entry.get().strip()
    config = load_config()
    config["username"] = username
    save_config(config)

# ------------------ REFRESH ------------------

def refresh_versions():
    versions_list.delete(0, tk.END)

    for v in ALLOWED_VERSIONS:
        idx = versions_list.size()
        versions_list.insert(tk.END, v)

        is_installed = fabric_id_for(v) is not None

        if v == HIGHLIGHT_VERSION:
            if is_installed:
                versions_list.itemconfig(idx, bg="#FFD700")  # gold
            else:
                versions_list.itemconfig(idx, bg="#ADD8E6")  # light blue
        else:
            if is_installed:
                versions_list.itemconfig(idx, bg="#b6fcb6")  # green
            else:
                versions_list.itemconfig(idx, bg="#fcb6b6")  # red

    config = load_config()
    last = config.get("last_version")

    if last in ALLOWED_VERSIONS:
        idx = ALLOWED_VERSIONS.index(last)
        versions_list.selection_set(idx)
        versions_list.activate(idx)
        versions_list.see(idx)
        sync_version_to_mods(last) 
        set_active_version(last)

def refresh_mods_versions():
    versions = [v for v in ALLOWED_VERSIONS if fabric_id_for(v)]
    mods_version_combo["values"] = versions


def refresh_mods_list():
    mods_list.delete(0, tk.END)
    v = mods_preview_version
    if not v:
        return

    paths = [
        mods_root / f"fabric-{v}",
        mods_root / "enchanted-packs" / f"fabric-{v}"
    ]

    for path in paths:
        if not path.exists():
            continue

        for f in path.iterdir():
            display = get_mod_display_name(f.name)
            idx = mods_list.size()
            mods_list.insert(tk.END, display)

            # Color coding
            if f.name.startswith("locked_el-"):
                mods_list.itemconfig(idx, bg="#add8e6")  # light blue = locked
            elif f.name.endswith(".disabled"):
                mods_list.itemconfig(idx, bg="#fcb6b6")  # red = disabled
            else:
                mods_list.itemconfig(idx, bg="#b6fcb6")  # green = enabled

# ------------------ GUI LOGIC ------------------

def resource_path(relative_path):
    if getattr(sys, "frozen", False):
        base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

icon_path = resource_path(
    "icon.ico" if getattr(sys, "frozen", False) else "assets/icon.ico"
)

def open_mods_folder():
    v = mods_version_combo.get()
    if not v:
        messagebox.showwarning("Select version", "Please select a version first")
        return
    folder = mods_root / f"fabric-{v}"
    if not folder.exists():
        messagebox.showinfo("Folder not found", f"Mods folder for version {v} does not exist.")
        return
    try:
        os.startfile(folder)  # Windows
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open folder:\n{e}")

def show_progress():
    progress.pack(pady=5)
    progress.start(10)
    play_button.config(state="disabled")

def hide_progress():
    progress.stop()
    progress.pack_forget()
    play_button.config(state="normal")

def lock_ui():
    play_button.config(state="disabled")
    progress.start(10)

def unlock_ui():
    progress.stop()
    play_button.config(state="normal")

def on_close():
    global minecraft_proc
    if is_minecraft_running():
        # Use a custom Toplevel for Yes/No style buttons
        warning = tk.Toplevel(root)
        warning.title("Warning")
        warning.geometry("400x180")
        warning.grab_set()  # modal window

        tk.Label(
            warning, 
            text="WARNING! Closing the Launcher will also close Minecraft.\n"
                 "This may cause issues with mods.\n"
                 "In the worst case, it may prevent Minecraft Fabric from launching (Temporary).",
            wraplength=380
        ).pack(pady=20)

        btn_frame = tk.Frame(warning)
        btn_frame.pack(pady=10)

        def cancel():
            warning.destroy()

        def close_launcher():
            warning.destroy()
            if is_minecraft_running():
                try:
                    minecraft_proc.terminate()
                    minecraft_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    minecraft_proc.kill()
                finally:
                    restore_mods()
            root.destroy()

        tk.Button(btn_frame, text="Cancel", command=cancel).pack(side="left", padx=10)
        tk.Button(btn_frame, text="Close", command=close_launcher).pack(side="left", padx=10)
    else:
        root.destroy()

def toggle_mod(enable: bool):
    sel = mods_list.curselection()
    if not sel:
        return

    v = mods_version_combo.get()
    name = mods_list.get(sel)

    paths = [
        mods_root / f"fabric-{v}",
        mods_root / "enchanted-packs" / f"fabric-{v}"
    ]

    for path in paths:
        if not path.exists():
            continue

        for f in path.iterdir():
            if get_mod_display_name(f.name) == name:

                if f.name.startswith("locked_el-"):
                    messagebox.showwarning("Locked mod", "This mod cannot be disabled")
                    return

                if enable and f.name.endswith(".disabled"):
                    f.rename(f.with_suffix(""))
                elif not enable and not f.name.endswith(".disabled"):
                    f.rename(f.with_name(f.name + ".disabled"))

                refresh_mods_list()
                return

def add_mod():
    v = mods_version_combo.get()
    if not v:
        return
    path = filedialog.askopenfilename(filetypes=[("Jar", "*.jar")])
    if path:
        shutil.copy(path, mods_root / f"fabric-{v}" / Path(path).name)
        refresh_mods_list()


def remove_mod():
    sel = mods_list.curselection()
    if not sel:
        return
    v = mods_version_combo.get()
    f = mods_root / f"fabric-{v}" / mods_list.get(sel)
    f.unlink(missing_ok=True)
    refresh_mods_list()

# ------------------ GUI ------------------

root = tk.Tk()
root.title("Enchanted Launcher")

# --- WINDOW SIZE & CENTER ---
screen_w = root.winfo_screenwidth()
screen_h = root.winfo_screenheight()

win_w = screen_w // 2.6
win_h = screen_h // 2.6

pos_x = (screen_w - win_w) // 2
pos_y = (screen_h - win_h) // 2

root.geometry(f"{int(win_w)}x{int(win_h)}+{int(pos_x)}+{int(pos_y)}")
root.minsize(720, 480)

root.protocol("WM_DELETE_WINDOW", on_close)

root.iconbitmap(icon_path)

# ===== TOP BAR =====
top_bar = ttk.Frame(root)
top_bar.pack(fill="x", padx=10, pady=(8, 4))

ttk.Label(
    top_bar,
    text="Enchanted Launcher",
    font=("Segoe UI", 14, "bold")
).pack(side="left")

top_btns = ttk.Frame(top_bar)
top_btns.pack(side="right")

ttk.Button(top_btns, text="Account", command=open_account).pack(side="left", padx=4)
ttk.Button(top_btns, text="GitHub", command=open_github).pack(side="left", padx=4)
ttk.Button(top_btns, text="Discord", command=open_discord).pack(side="left", padx=4)

# ===== NOTEBOOK =====
notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True, padx=10, pady=10)

# ================= TAB: LAUNCH =================
launch_tab = ttk.Frame(notebook)
notebook.add(launch_tab, text="Launch")

launch_container = ttk.Frame(launch_tab)
launch_container.pack(fill="both", expand=True, padx=30, pady=20)

ttk.Label(launch_container, text="Username").pack(anchor="w")
username_entry = ttk.Entry(launch_container)
username_entry.pack(fill="x", pady=(2, 10))

config = load_config()
if "username" in config:
    username_entry.insert(0, config["username"])

last_version = config.get("last_version")
mods_preview_version = last_version

ttk.Label(launch_container, text="Versions").pack(anchor="w")
versions_list = tk.Listbox(launch_container, height=8)
versions_list.pack(fill="both", expand=True, pady=(2, 10))

def on_version_select(event):
    sel = versions_list.curselection()
    if not sel:
        return
    version = versions_list.get(sel[0])
    set_active_version(version)

versions_list.bind("<<ListboxSelect>>", on_version_select)

play_button = ttk.Button(
    launch_container,
    text="▶ Launch Minecraft",
    command=launch_game
)
play_button.pack(pady=(10, 6))

progress = ttk.Progressbar(
    launch_container,
    mode="indeterminate",
    length=300
)

# ================= TAB: MODS =================
mods_tab = ttk.Frame(notebook)
notebook.add(mods_tab, text="Mods")

mods_container = ttk.Frame(mods_tab)
mods_container.pack(fill="both", expand=True, padx=20, pady=15)

top_mods = ttk.Frame(mods_container)
top_mods.pack(fill="x")

ttk.Label(top_mods, text="Minecraft Version").pack(side="left")
mods_version_combo = ttk.Combobox(top_mods, state="readonly", width=20)
mods_version_combo.pack(side="left", padx=8)

mods_list = tk.Listbox(mods_container)
mods_list.pack(fill="both", expand=True, pady=10)

mods_btns = ttk.Frame(mods_container)
mods_btns.pack(fill="x")

ttk.Button(mods_btns, text="Add Mod", command=add_mod).pack(side="left", padx=4)
ttk.Button(mods_btns, text="Remove", command=remove_mod).pack(side="left", padx=4)
ttk.Button(mods_btns, text="Enable", command=lambda: toggle_mod(True)).pack(side="left", padx=4)
ttk.Button(mods_btns, text="Disable", command=lambda: toggle_mod(False)).pack(side="left", padx=4)
ttk.Button(mods_btns, text="Open Mods Folder", command=open_mods_folder).pack(side="right", padx=4)

def on_mods_version_change(event):
    global mods_preview_version
    mods_preview_version = mods_version_combo.get()
    refresh_mods_list()

mods_version_combo.bind("<<ComboboxSelected>>", on_mods_version_change)

refresh_versions()
refresh_mods_versions()

root.mainloop()
