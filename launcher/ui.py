from __future__ import annotations

import os
import subprocess
import threading
import time
import traceback
import webbrowser
from pathlib import Path

import customtkinter as ctk

from .config import LauncherConfig
from .constants import APP_NAME, DISCORD_URL, FEATURED_VERSION, GITHUB_URL, SUPPORTED_VERSIONS
from .dialogs import Dialog
from .file_picker import pick_mod_file
from .logs import rotate_latest_log
from .minecraft_service import (
    build_launch_command,
    install_fabric,
    installed_fabric_id,
    start_process,
    valid_username,
)
from .mods import ModEntry, add_mod, list_mods, prepare_version_mods, restore_original_mods, toggle_mod
from .paths import LauncherPaths


class LauncherApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.paths = LauncherPaths.create()
        self.paths.ensure_runtime_dirs(SUPPORTED_VERSIONS)
        self.config = LauncherConfig(self.paths.config)

        self.minecraft_proc: subprocess.Popen | None = None
        self.selected_version = self.config.get("last_version") or SUPPORTED_VERSIONS[-2]
        self.mods_preview_version = self.selected_version
        self.selected_mod: ModEntry | None = None

        self.version_buttons: dict[str, ctk.CTkButton] = {}
        self.mod_buttons: dict[Path, ctk.CTkButton] = {}

        self._setup_window()
        self._build_layout()
        self.refresh_versions()
        self.refresh_mod_versions()
        self.refresh_mods_list()

    def _setup_window(self) -> None:
        self.title(APP_NAME)
        self.geometry(self._centered_geometry(980, 640))
        self.minsize(820, 520)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        if self.paths.icon.exists():
            self.iconbitmap(str(self.paths.icon))

    def _centered_geometry(self, width: int, height: int) -> str:
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        pos_x = (screen_w - width) // 2
        pos_y = (screen_h - height) // 2
        return f"{width}x{height}+{pos_x}+{pos_y}"

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_top_bar()
        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=16, pady=(8, 16))

        self.launch_tab = self.tabs.add("Launch")
        self.mods_tab = self.tabs.add("Mods")

        self._build_launch_tab()
        self._build_mods_tab()

    def _build_top_bar(self) -> None:
        top_bar = ctk.CTkFrame(self, height=56, corner_radius=8)
        top_bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 4))
        top_bar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            top_bar,
            text=APP_NAME,
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=14, pady=12)

        actions = ctk.CTkFrame(top_bar, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e", padx=10)

        ctk.CTkButton(actions, text="GitHub", width=96, command=lambda: webbrowser.open(GITHUB_URL)).pack(
            side="left",
            padx=4,
        )
        ctk.CTkButton(actions, text="Discord", width=96, command=lambda: webbrowser.open(DISCORD_URL)).pack(
            side="left",
            padx=4,
        )

    def _build_launch_tab(self) -> None:
        self.launch_tab.grid_columnconfigure(0, weight=1)
        self.launch_tab.grid_rowconfigure(2, weight=1)

        account_frame = ctk.CTkFrame(self.launch_tab)
        account_frame.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        account_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(account_frame, text="Username").grid(row=0, column=0, sticky="w", padx=14, pady=14)
        self.username_entry = ctk.CTkEntry(account_frame, placeholder_text="Player name")
        self.username_entry.grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=14)
        self.username_entry.insert(0, self.config.get("username", ""))
        self.username_entry.bind("<KeyRelease>", self.on_username_change)

        versions_header = ctk.CTkFrame(self.launch_tab, fg_color="transparent")
        versions_header.grid(row=1, column=0, sticky="ew", padx=18)
        ctk.CTkLabel(
            versions_header,
            text="Fabric versions",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(side="left")
        self.version_status_label = ctk.CTkLabel(versions_header, text="")
        self.version_status_label.pack(side="right")

        self.versions_frame = ctk.CTkScrollableFrame(self.launch_tab, corner_radius=8)
        self.versions_frame.grid(row=2, column=0, sticky="nsew", padx=18, pady=(8, 12))

        bottom = ctk.CTkFrame(self.launch_tab, fg_color="transparent")
        bottom.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))
        bottom.grid_columnconfigure(0, weight=1)

        self.progress = ctk.CTkProgressBar(bottom, mode="indeterminate")
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.progress.grid_remove()

        self.play_button = ctk.CTkButton(
            bottom,
            text="Launch Minecraft",
            height=42,
            width=190,
            command=self.launch_game,
        )
        self.play_button.grid(row=0, column=1, sticky="e")

    def _build_mods_tab(self) -> None:
        self.mods_tab.grid_columnconfigure(0, weight=1)
        self.mods_tab.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(self.mods_tab)
        toolbar.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        toolbar.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(toolbar, text="Version").grid(row=0, column=0, sticky="w", padx=(14, 8), pady=12)
        self.mods_version_combo = ctk.CTkComboBox(
            toolbar,
            width=190,
            values=list(SUPPORTED_VERSIONS),
            command=self.on_mods_version_change,
            state="readonly",
        )
        self.mods_version_combo.grid(row=0, column=1, sticky="w", pady=12)
        self.mods_version_combo.set(self.mods_preview_version)

        ctk.CTkButton(toolbar, text="Open Folder", width=120, command=self.open_mods_folder).grid(
            row=0,
            column=3,
            padx=8,
            pady=12,
        )

        self.mods_list_frame = ctk.CTkScrollableFrame(self.mods_tab, corner_radius=8)
        self.mods_list_frame.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 12))

        actions = ctk.CTkFrame(self.mods_tab, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 18))
        actions.grid_columnconfigure(4, weight=1)

        ctk.CTkButton(actions, text="Add Mod", command=self.add_mod).grid(row=0, column=0, padx=(0, 8))
        ctk.CTkButton(actions, text="Enable", command=lambda: self.toggle_selected_mod(True)).grid(
            row=0,
            column=1,
            padx=8,
        )
        ctk.CTkButton(actions, text="Disable", command=lambda: self.toggle_selected_mod(False)).grid(
            row=0,
            column=2,
            padx=8,
        )

    def set_busy(self, busy: bool, status: str = "") -> None:
        if busy:
            self.version_status_label.configure(text=status)
            self.progress.grid()
            self.progress.start()
            self.play_button.configure(state="disabled")
            return

        self.progress.stop()
        self.progress.grid_remove()
        self.version_status_label.configure(text=status)
        self.play_button.configure(state="normal")

    def refresh_versions(self) -> None:
        for child in self.versions_frame.winfo_children():
            child.destroy()

        self.version_buttons.clear()
        for version in SUPPORTED_VERSIONS:
            installed = installed_fabric_id(self.paths.minecraft, version) is not None
            selected = version == self.selected_version
            color = self.version_color(version, installed, selected)
            label = f"{version}  -  {'Installed' if installed else 'Install on launch'}"
            button = ctk.CTkButton(
                self.versions_frame,
                text=label,
                anchor="w",
                fg_color=color,
                command=lambda selected_version=version: self.select_version(selected_version),
            )
            button.pack(fill="x", pady=4)
            self.version_buttons[version] = button

    def version_color(self, version: str, installed: bool, selected: bool) -> str:
        if selected:
            return "#1f6aa5"
        if version == FEATURED_VERSION:
            return "#b58b00" if installed else "#705e1c"
        return "#2d7d46" if installed else "#7d2d2d"

    def refresh_mod_versions(self) -> None:
        self.mods_version_combo.configure(values=list(SUPPORTED_VERSIONS))
        if self.mods_preview_version not in SUPPORTED_VERSIONS:
            self.mods_preview_version = SUPPORTED_VERSIONS[0]
        self.mods_version_combo.set(self.mods_preview_version)

    def refresh_mods_list(self) -> None:
        for child in self.mods_list_frame.winfo_children():
            child.destroy()

        self.mod_buttons.clear()
        selected_path = self.selected_mod.path if self.selected_mod else None
        self.selected_mod = None
        entries = list_mods(self.paths.mods, self.mods_preview_version)

        if not entries:
            ctk.CTkLabel(
                self.mods_list_frame,
                text="No mods added for this version.",
                text_color="#a8b3bd",
            ).pack(anchor="w", padx=12, pady=12)
            return

        for entry in entries:
            selected = entry.path == selected_path
            if selected:
                self.selected_mod = entry
            color = self.mod_color(entry, selected)
            button = ctk.CTkButton(
                self.mods_list_frame,
                text=entry.name,
                anchor="w",
                fg_color=color,
                command=lambda selected=entry: self.select_mod(selected),
            )
            button.pack(fill="x", pady=4)
            self.mod_buttons[entry.path] = button

    def mod_color(self, entry: ModEntry, selected: bool = False) -> str:
        if selected:
            return "#1f6aa5"
        if entry.locked:
            return "#1f6aa5"
        return "#2d7d46" if entry.enabled else "#7d2d2d"

    def select_version(self, version: str) -> None:
        self.selected_version = version
        self.mods_preview_version = version
        self.config.set("last_version", version)
        self.refresh_versions()
        self.refresh_mod_versions()
        self.refresh_mods_list()

    def select_mod(self, entry: ModEntry) -> None:
        self.selected_mod = entry
        self.refresh_mods_list()

    def on_username_change(self, _event=None) -> None:
        self.config.set("username", self.username_entry.get().strip())

    def on_mods_version_change(self, version: str) -> None:
        self.mods_preview_version = version
        self.refresh_mods_list()

    def add_mod(self) -> None:
        version = self.mods_version_combo.get()
        if not version:
            Dialog.show(self, "Select version", "Please select a version first.", "warning")
            return

        path = pick_mod_file(self.winfo_id())
        if not path:
            return

        try:
            add_mod(self.paths.mods, version, Path(path))
            self.refresh_mods_list()
        except Exception as error:
            Dialog.show(self, "Add mod failed", str(error), "error")

    def toggle_selected_mod(self, enable: bool) -> None:
        if not self.selected_mod:
            Dialog.show(self, "Select mod", "Please select a mod first.", "warning")
            return

        try:
            toggle_mod(self.selected_mod, enable)
            self.refresh_mods_list()
        except Exception as error:
            Dialog.show(self, "Mod update failed", str(error), "error")

    def open_mods_folder(self) -> None:
        folder = self.paths.mods / f"fabric-{self.mods_version_combo.get()}"
        folder.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(folder)
        except Exception as error:
            Dialog.show(self, "Open folder failed", str(error), "error")

    def launch_game(self) -> None:
        username = self.username_entry.get().strip()
        version = self.selected_version

        if not valid_username(username):
            Dialog.show(
                self,
                "Invalid username",
                "Username must be 3-16 characters and use only A-Z, 0-9, or underscore.",
                "warning",
            )
            return

        if not version:
            Dialog.show(self, "Select version", "Please select a Fabric version.", "warning")
            return

        self.config.set("username", username)
        self.config.set("last_version", version)
        self.set_busy(True, f"Preparing {version}...")

        thread = threading.Thread(target=self._launch_worker, args=(username, version), daemon=True)
        thread.start()

    def _launch_worker(self, username: str, version: str) -> None:
        try:
            version_id = installed_fabric_id(self.paths.minecraft, version)
            if not version_id:
                self.after(0, lambda: self.set_busy(True, f"Installing Fabric {version}..."))
                install_fabric(self.paths.minecraft, version)
                version_id = installed_fabric_id(self.paths.minecraft, version)

            if not version_id:
                raise RuntimeError(f"Fabric {version} could not be installed.")

            prepare_version_mods(self.paths.mods, self.paths.minecraft, version)
            command = build_launch_command(self.paths.minecraft, version_id, username)
            latest_log = rotate_latest_log(self.paths.logs)

            with latest_log.open("w", encoding="utf-8") as log_file:
                self.minecraft_proc = start_process(command, self.paths.minecraft, log_file)
                self.after(0, lambda: self.set_busy(False, f"Running {version}"))
                self.minecraft_proc.wait()

            time.sleep(1)
            restore_original_mods(self.paths.mods, self.paths.minecraft)
            self.minecraft_proc = None
            self.after(0, self.refresh_versions)
            self.after(0, lambda: self.set_busy(False, "Minecraft closed"))
        except Exception as error:
            traceback.print_exc()
            restore_original_mods(self.paths.mods, self.paths.minecraft)
            self.minecraft_proc = None
            self.after(0, self.refresh_versions)
            self.after(0, lambda: self.set_busy(False, ""))
            self.after(0, lambda: Dialog.show(self, "Launch failed", str(error), "error"))

    def is_minecraft_running(self) -> bool:
        return self.minecraft_proc is not None and self.minecraft_proc.poll() is None

    def on_close(self) -> None:
        if not self.is_minecraft_running():
            self.destroy()
            return

        should_close = Dialog.confirm(
            self,
            "Minecraft is running",
            "Closing the launcher will also close Minecraft and restore your original mods.",
        )
        if not should_close:
            return

        try:
            if self.minecraft_proc:
                self.minecraft_proc.terminate()
                self.minecraft_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if self.minecraft_proc:
                self.minecraft_proc.kill()
        finally:
            restore_original_mods(self.paths.mods, self.paths.minecraft)
            self.destroy()


def main() -> None:
    app = LauncherApp()
    app.mainloop()
