from __future__ import annotations

import os
import subprocess
import threading
import time
import traceback
import webbrowser
from pathlib import Path

import customtkinter as ctk

try:
    from PIL import Image
except ImportError:  # pragma: no cover - handled at runtime in the UI
    Image = None

from .config import LauncherConfig
from .constants import APP_NAME, DISCORD_URL, GITHUB_URL, SUPPORTED_VERSIONS
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
from .modrinth import ModrinthProject, download_project_file, download_project_icon, search_mods
from .paths import LauncherPaths
from .profiles import DEFAULT_PROFILE_ID, Profile, ProfileMod, ProfileStore, QuickPlaySlot
from .skin_viewer import SteveSkinViewer


MAX_QUICKPLAYS = 4


class Tooltip:
    def __init__(self, parent: ctk.CTk) -> None:
        self.parent = parent
        self.window: ctk.CTkToplevel | None = None

    def bind(self, widget, text: str) -> None:
        widget.bind("<Enter>", lambda event: self.show(event, text))
        widget.bind("<Leave>", lambda _event: self.hide())

    def show(self, event, text: str) -> None:
        self.hide()
        self.window = ctk.CTkToplevel(self.parent)
        self.window.overrideredirect(True)
        self.window.geometry(f"+{event.x_root + 12}+{event.y_root + 12}")
        ctk.CTkLabel(
            self.window,
            text=text,
            corner_radius=6,
            fg_color="#111827",
            text_color="#d8dee9",
            padx=10,
            pady=6,
        ).pack()

    def hide(self) -> None:
        if self.window:
            self.window.destroy()
            self.window = None


class LauncherApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.paths = LauncherPaths.create()
        self.paths.ensure_runtime_dirs(SUPPORTED_VERSIONS)
        self.config = LauncherConfig(self.paths.config)
        self.profile_store = ProfileStore(self.paths.profiles, self.paths.temp_mods, self.paths.root)

        self.minecraft_proc: subprocess.Popen | None = None
        self.selected_profile_id = self._initial_profile_id()
        self.selected_mod: ProfileMod | None = None
        self.quickplays = self.load_quickplays()
        self.modrinth_results: list[ModrinthProject] = []
        self.image_refs: list[ctk.CTkImage] = []
        self.tooltip = Tooltip(self)

        self._setup_window()
        self._build_layout()
        self.refresh_all()

    def _initial_profile_id(self) -> str:
        saved = str(
            self.config.get(
                "selected_profile_id",
                self.config.get("last_profile_id", DEFAULT_PROFILE_ID),
            )
        )
        profile_ids = {profile.id for profile in self.profile_store.list_profiles()}
        return saved if saved in profile_ids else DEFAULT_PROFILE_ID

    def _setup_window(self) -> None:
        self.title(APP_NAME)
        self.geometry(self._centered_geometry(1180, 720))
        self.minsize(980, 620)
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
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_top_panel()
        self._build_sidebar()
        self._build_center_panel()
        self._build_right_panel()

    def _build_top_panel(self) -> None:
        panel = ctk.CTkFrame(self, corner_radius=8)
        panel.grid(row=0, column=0, columnspan=3, sticky="ew", padx=14, pady=(14, 8))
        panel.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(
            panel,
            text=APP_NAME,
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=14, pady=12)

        links = ctk.CTkFrame(panel, fg_color="transparent")
        links.grid(row=0, column=1, padx=(0, 16))
        ctk.CTkButton(links, text="GitHub", width=86, command=lambda: webbrowser.open(GITHUB_URL)).pack(
            side="left",
            padx=3,
        )
        ctk.CTkButton(links, text="Discord", width=86, command=lambda: webbrowser.open(DISCORD_URL)).pack(
            side="left",
            padx=3,
        )

        quick = ctk.CTkFrame(panel, fg_color="transparent")
        quick.grid(row=0, column=2, sticky="e", padx=10)

        self.last_play_button = ctk.CTkButton(
            quick,
            text="Last profile",
            width=138,
            command=self.launch_last_profile,
        )
        self.last_play_button.pack(side="left", padx=(0, 8))

        self.quickplay_frame = ctk.CTkFrame(quick, fg_color="transparent")
        self.quickplay_frame.pack(side="left")

    def _build_sidebar(self) -> None:
        side = ctk.CTkFrame(self, width=230, corner_radius=8)
        side.grid(row=1, column=0, sticky="nsew", padx=(14, 8), pady=(0, 14))
        side.grid_rowconfigure(6, weight=1)
        side.grid_propagate(False)

        ctk.CTkLabel(side, text="WERSJA", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0,
            column=0,
            sticky="w",
            padx=14,
            pady=(16, 4),
        )
        self.version_combo = ctk.CTkComboBox(
            side,
            values=list(SUPPORTED_VERSIONS),
            command=self.on_version_change,
            state="readonly",
        )
        self.version_combo.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))

        ctk.CTkLabel(side, text="NICK", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=2,
            column=0,
            sticky="w",
            padx=14,
            pady=(4, 4),
        )
        self.username_entry = ctk.CTkEntry(side, placeholder_text="Player name")
        self.username_entry.grid(row=3, column=0, sticky="ew", padx=14)
        self.username_entry.insert(0, self.config.get("username", ""))
        self.username_entry.bind("<KeyRelease>", self.on_username_change)

        profile_head = ctk.CTkFrame(side, fg_color="transparent")
        profile_head.grid(row=4, column=0, sticky="ew", padx=14, pady=(18, 6))
        profile_head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(profile_head, text="PROFILE", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0,
            column=0,
            sticky="w",
        )
        ctk.CTkButton(profile_head, text="+", width=34, command=self.create_profile).grid(row=0, column=1)

        self.profiles_frame = ctk.CTkScrollableFrame(side, corner_radius=8)
        self.profiles_frame.grid(row=6, column=0, sticky="nsew", padx=14, pady=(0, 10))

        ctk.CTkButton(side, text="Open Profile Folder", command=self.open_profile_folder).grid(
            row=7,
            column=0,
            sticky="ew",
            padx=14,
            pady=(0, 14),
        )

    def _build_center_panel(self) -> None:
        center = ctk.CTkFrame(self, corner_radius=8)
        center.grid(row=1, column=1, sticky="nsew", padx=8, pady=(0, 14))
        center.grid_columnconfigure(0, weight=1)
        center.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(center, text="PANEL", font=ctk.CTkFont(size=32, weight="bold")).grid(
            row=0,
            column=0,
            pady=(24, 4),
        )
        self.active_profile_label = ctk.CTkLabel(center, text="", font=ctk.CTkFont(size=16))
        self.active_profile_label.grid(row=1, column=0, pady=(0, 14))

        self.launch_button = ctk.CTkButton(
            center,
            text="LAUNCH",
            height=58,
            width=360,
            font=ctk.CTkFont(size=22, weight="bold"),
            command=lambda: self.launch_game(),
        )
        self.launch_button.grid(row=2, column=0, pady=(0, 24))

        self.skin_viewer = SteveSkinViewer(center, skin_path=self.paths.steve_skin, width=230, height=250)
        self.skin_viewer.grid(row=3, column=0)

        bottom = ctk.CTkFrame(center, fg_color="transparent")
        bottom.grid(row=4, column=0, sticky="ew", padx=22, pady=20)
        bottom.grid_columnconfigure(0, weight=1)
        self.progress = ctk.CTkProgressBar(bottom, mode="indeterminate")
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.progress.grid_remove()
        self.status_label = ctk.CTkLabel(bottom, text="", width=180, anchor="e")
        self.status_label.grid(row=0, column=1, sticky="e")

    def _build_right_panel(self) -> None:
        right = ctk.CTkFrame(self, width=340, corner_radius=8)
        right.grid(row=1, column=2, sticky="nsew", padx=(8, 14), pady=(0, 14))
        right.grid_propagate(False)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1)

        self.right_tabs = ctk.CTkTabview(right)
        self.right_tabs.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.profile_tab = self.right_tabs.add("Profile")
        self.mods_tab = self.right_tabs.add("Mody")
        self.modrinth_tab = self.right_tabs.add("Modrinth")

        self._build_profile_tab()
        self._build_mods_tab()
        self._build_modrinth_tab()

    def _build_profile_tab(self) -> None:
        self.profile_tab.grid_columnconfigure(0, weight=1)

        self.profile_icon_label = ctk.CTkLabel(
            self.profile_tab,
            text="?",
            width=70,
            height=70,
            corner_radius=8,
            fg_color="#171c22",
            font=ctk.CTkFont(size=28, weight="bold"),
        )
        self.profile_icon_label.grid(row=0, column=0, pady=(20, 14))

        ctk.CTkLabel(self.profile_tab, text="Profile name").grid(row=1, column=0, sticky="w", padx=12)
        self.profile_name_entry = ctk.CTkEntry(self.profile_tab)
        self.profile_name_entry.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 12))

        ctk.CTkButton(self.profile_tab, text="Save Profile", command=self.save_profile_fields).grid(
            row=3,
            column=0,
            sticky="ew",
            padx=12,
            pady=(0, 8),
        )

    def _build_mods_tab(self) -> None:
        self.mods_tab.grid_columnconfigure(0, weight=1)
        self.mods_tab.grid_rowconfigure(0, weight=1)

        self.mods_frame = ctk.CTkScrollableFrame(self.mods_tab, corner_radius=8)
        self.mods_frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=(12, 8))

        actions = ctk.CTkFrame(self.mods_tab, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 10))
        actions.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(actions, text="Add File", command=self.add_custom_mod).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 4),
        )
        ctk.CTkButton(actions, text="Enable", command=lambda: self.toggle_selected_mod(True)).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=4,
        )
        ctk.CTkButton(actions, text="Disable", command=lambda: self.toggle_selected_mod(False)).grid(
            row=0,
            column=2,
            sticky="ew",
            padx=(4, 0),
        )

    def _build_modrinth_tab(self) -> None:
        self.modrinth_tab.grid_columnconfigure(0, weight=1)
        self.modrinth_tab.grid_rowconfigure(2, weight=1)

        self.modrinth_query = ctk.CTkEntry(self.modrinth_tab, placeholder_text="Search Modrinth")
        self.modrinth_query.grid(row=0, column=0, sticky="ew", padx=8, pady=(12, 8))
        ctk.CTkButton(self.modrinth_tab, text="Search", command=self.search_modrinth).grid(
            row=1,
            column=0,
            sticky="ew",
            padx=8,
            pady=(0, 8),
        )
        self.modrinth_results_frame = ctk.CTkScrollableFrame(self.modrinth_tab, corner_radius=8)
        self.modrinth_results_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 10))

    def refresh_all(self) -> None:
        self.refresh_quickplay()
        self.refresh_profiles()
        self.refresh_selected_profile()
        self.refresh_mods()
        self.refresh_modrinth_results()

    def current_profile(self) -> Profile:
        return self.profile_store.load_profile(self.selected_profile_id)

    def refresh_quickplay(self) -> None:
        for child in self.quickplay_frame.winfo_children():
            child.destroy()

        last = self.safe_profile(self.config.get("last_profile_id", self.selected_profile_id))
        self.last_play_button.configure(text=f"Last: {last.name}", command=self.launch_last_profile)

        for slot in self.quickplays:
            frame = ctk.CTkFrame(self.quickplay_frame, fg_color="transparent")
            frame.pack(side="left", padx=3)
            play_text = (slot.label or self.quickplay_label(slot))[:16]
            ctk.CTkButton(frame, text=play_text, width=96, command=lambda s=slot: self.launch_quickplay(s)).pack(
                side="left",
            )
            ctk.CTkButton(frame, text="x", width=30, command=lambda s=slot: self.remove_quickplay(s.index)).pack(
                side="left",
                padx=(3, 0),
            )
        if len(self.quickplays) < MAX_QUICKPLAYS:
            ctk.CTkButton(self.quickplay_frame, text="+", width=38, command=self.add_quickplay).pack(
                side="left",
                padx=(6, 0),
            )

    def refresh_profiles(self) -> None:
        for child in self.profiles_frame.winfo_children():
            child.destroy()

        for profile in self.profile_store.list_profiles():
            selected = profile.id == self.selected_profile_id
            frame = ctk.CTkFrame(
                self.profiles_frame,
                fg_color="#1f6aa5" if selected else "#171c22",
                corner_radius=8,
            )
            frame.pack(fill="x", pady=4)
            frame.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(
                frame,
                text=profile.name[:1].upper(),
                width=32,
                height=32,
                corner_radius=6,
                fg_color="#2b3340",
                font=ctk.CTkFont(size=14, weight="bold"),
            ).grid(row=0, column=0, padx=8, pady=8)
            ctk.CTkLabel(frame, text=profile.name, anchor="w").grid(row=0, column=1, sticky="ew", pady=8)
            frame.bind("<Button-1>", lambda _event, pid=profile.id: self.select_profile(pid))
            for child in frame.winfo_children():
                child.bind("<Button-1>", lambda _event, pid=profile.id: self.select_profile(pid))

    def refresh_selected_profile(self) -> None:
        profile = self.current_profile()
        self.active_profile_label.configure(text=f"{profile.name} - {profile.version}")
        self.version_combo.set(profile.version)
        self.profile_icon_label.configure(text=profile.name[:1].upper() if profile.name else "?")
        self.profile_name_entry.delete(0, "end")
        self.profile_name_entry.insert(0, profile.name)

    def refresh_mods(self) -> None:
        for child in self.mods_frame.winfo_children():
            child.destroy()

        selected_path = self.selected_mod.path if self.selected_mod else None
        self.selected_mod = None
        mods = self.profile_store.list_mods(self.selected_profile_id)
        if not mods:
            ctk.CTkLabel(
                self.mods_frame,
                text="No mods in this profile.",
                text_color="#8d99a6",
            ).pack(anchor="w", padx=10, pady=10)
            return

        for mod in mods:
            selected = mod.path == selected_path
            if selected:
                self.selected_mod = mod
            self._add_mod_row(mod, selected)

    def _add_mod_row(self, mod: ProfileMod, selected: bool) -> None:
        color = "#1f6aa5" if selected else "#252b33" if mod.inherited else "#17251c" if mod.enabled else "#2a1717"
        row = ctk.CTkFrame(self.mods_frame, fg_color=color, corner_radius=8)
        row.pack(fill="x", pady=4)
        row.grid_columnconfigure(1, weight=1)

        icon = self.load_image(mod.icon_path, (28, 28))
        if icon:
            icon_label = ctk.CTkLabel(row, text="", image=icon, width=34)
        else:
            icon_label = ctk.CTkLabel(
                row,
                text=mod.name[:1].upper(),
                width=34,
                height=34,
                corner_radius=6,
                fg_color="#2b3340",
            )
        icon_label.grid(row=0, column=0, padx=(8, 6), pady=8)

        name_color = "#aeb6c2" if mod.inherited else "#e5edf5"
        ctk.CTkLabel(row, text=mod.name, anchor="w", text_color=name_color).grid(
            row=0,
            column=1,
            sticky="ew",
            pady=8,
        )
        source_text = "Default" if mod.inherited else mod.source
        ctk.CTkLabel(row, text=source_text, text_color="#8d99a6", width=64).grid(
            row=0,
            column=2,
            padx=8,
        )

        row.bind("<Button-1>", lambda _event, selected_mod=mod: self.select_mod(selected_mod))
        for child in row.winfo_children():
            child.bind("<Button-1>", lambda _event, selected_mod=mod: self.select_mod(selected_mod))
        if mod.inherited:
            text = "Skopiowane z profilu Default. Edytuj ten mod w profilu Default."
            self.tooltip.bind(row, text)
            for child in row.winfo_children():
                self.tooltip.bind(child, text)

    def refresh_modrinth_results(self) -> None:
        for child in self.modrinth_results_frame.winfo_children():
            child.destroy()

        if not self.modrinth_results:
            ctk.CTkLabel(
                self.modrinth_results_frame,
                text="Search Fabric mods for this profile version.",
                text_color="#8d99a6",
            ).pack(anchor="w", padx=10, pady=10)
            return

        for project in self.modrinth_results:
            row = ctk.CTkFrame(self.modrinth_results_frame, fg_color="#171c22", corner_radius=8)
            row.pack(fill="x", pady=5)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=project.title, anchor="w", font=ctk.CTkFont(weight="bold")).grid(
                row=0,
                column=0,
                sticky="ew",
                padx=10,
                pady=(8, 0),
            )
            ctk.CTkLabel(
                row,
                text=project.description,
                anchor="w",
                justify="left",
                wraplength=220,
                text_color="#a8b3bd",
            ).grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 8))
            ctk.CTkButton(row, text="Add", width=64, command=lambda p=project: self.install_modrinth(p)).grid(
                row=0,
                column=1,
                rowspan=2,
                padx=8,
            )

    def load_image(self, path: Path | None, size: tuple[int, int]) -> ctk.CTkImage | None:
        if not path or Image is None or not path.exists():
            return None
        try:
            image = ctk.CTkImage(Image.open(path), size=size)
        except Exception:
            return None
        self.image_refs.append(image)
        return image

    def select_profile(self, profile_id: str) -> None:
        self.selected_profile_id = profile_id
        self.config.set("selected_profile_id", profile_id)
        self.selected_mod = None
        self.refresh_profiles()
        self.refresh_selected_profile()
        self.refresh_mods()
        self.refresh_quickplay()

    def create_profile(self) -> None:
        dialog = ctk.CTkInputDialog(text="Profile name", title="New Profile")
        name = dialog.get_input()
        if not name:
            return
        profile = self.profile_store.create_profile(name, self.current_profile().version)
        self.select_profile(profile.id)

    def save_profile_fields(self) -> None:
        self.profile_store.update_profile(
            self.selected_profile_id,
            name=self.profile_name_entry.get(),
            version=self.version_combo.get(),
        )
        self.refresh_all()

    def on_version_change(self, version: str) -> None:
        self.profile_store.update_profile(self.selected_profile_id, version=version)
        self.refresh_selected_profile()
        self.refresh_profiles()

    def on_username_change(self, _event=None) -> None:
        self.config.set("username", self.username_entry.get().strip())

    def split_server_address(self, host: str, port: str) -> tuple[str, str]:
        host = host.strip()
        port = port.strip()
        if ":" in host and not port:
            split_host, split_port = host.rsplit(":", 1)
            if split_port.isdigit():
                return split_host, split_port
        return host, port

    def add_custom_mod(self) -> None:
        path = pick_mod_file(self.winfo_id())
        if not path:
            return
        try:
            self.profile_store.add_custom_mod(self.selected_profile_id, Path(path))
            self.refresh_mods()
        except Exception as error:
            Dialog.show(self, "Add mod failed", str(error), "error")

    def select_mod(self, mod: ProfileMod) -> None:
        self.selected_mod = mod
        self.refresh_mods()

    def toggle_selected_mod(self, enable: bool) -> None:
        if not self.selected_mod:
            Dialog.show(self, "Select mod", "Please select a mod first.", "warning")
            return
        try:
            self.profile_store.toggle_mod(self.selected_mod, enable)
            self.refresh_mods()
        except Exception as error:
            Dialog.show(self, "Mod update failed", str(error), "error")

    def open_profile_folder(self) -> None:
        folder = self.profile_store.mods_dir(self.selected_profile_id)
        try:
            os.startfile(folder)
        except Exception as error:
            Dialog.show(self, "Open folder failed", str(error), "error")

    def search_modrinth(self) -> None:
        query = self.modrinth_query.get().strip()
        if not query:
            Dialog.show(self, "Search", "Type a mod name first.", "warning")
            return
        profile = self.current_profile()
        self.set_busy(True, "Searching Modrinth...")

        def worker() -> None:
            try:
                results = search_mods(query, profile.version)
                self.after(0, lambda: self.apply_modrinth_results(results))
            except Exception as error:
                self.after(0, lambda: Dialog.show(self, "Modrinth search failed", str(error), "error"))
            finally:
                self.after(0, lambda: self.set_busy(False, ""))

        threading.Thread(target=worker, daemon=True).start()

    def apply_modrinth_results(self, results: list[ModrinthProject]) -> None:
        self.modrinth_results = results
        self.refresh_modrinth_results()

    def install_modrinth(self, project: ModrinthProject) -> None:
        profile = self.current_profile()
        self.set_busy(True, f"Downloading {project.title}...")

        def worker() -> None:
            try:
                download_dir = self.paths.cache / "modrinth-downloads"
                icon = download_project_icon(project, self.paths.modrinth_icons)
                mod_file = download_project_file(project, profile.version, download_dir)
                self.profile_store.add_downloaded_mod(
                    profile.id,
                    mod_file,
                    title=project.title,
                    project_id=project.project_id,
                    icon_path=icon,
                )
                self.after(0, self.refresh_mods)
            except Exception as error:
                self.after(0, lambda: Dialog.show(self, "Modrinth install failed", str(error), "error"))
            finally:
                self.after(0, lambda: self.set_busy(False, ""))

        threading.Thread(target=worker, daemon=True).start()

    def load_quickplays(self) -> list[QuickPlaySlot]:
        raw = self.config.get("quickplays", [])
        slots: list[QuickPlaySlot] = []
        if not isinstance(raw, list):
            return slots
        for index, data in enumerate(raw[:MAX_QUICKPLAYS], start=1):
            if not isinstance(data, dict) or not data.get("profile_id"):
                continue
            slots.append(
                QuickPlaySlot(
                    index=index,
                    label=str(data.get("label", "")),
                    profile_id=str(data.get("profile_id", "")),
                    server_host=str(data.get("server_host", "")),
                    server_port=str(data.get("server_port", "")),
                )
            )
        return slots

    def quickplay_label(self, slot: QuickPlaySlot) -> str:
        profile = self.safe_profile(slot.profile_id)
        return slot.label or f"{profile.name} @ {slot.server_host}"

    def save_quickplays(self) -> None:
        for index, slot in enumerate(self.quickplays, start=1):
            slot.index = index
        self.config.set(
            "quickplays",
            [
                {
                    "label": slot.label,
                    "profile_id": slot.profile_id,
                    "server_host": slot.server_host,
                    "server_port": slot.server_port,
                }
                for slot in self.quickplays
            ],
        )

    def add_quickplay(self) -> None:
        if len(self.quickplays) >= MAX_QUICKPLAYS:
            Dialog.show(self, "Quickplay", "You can add up to 4 quickplay entries.", "warning")
            return
        self.open_quickplay_dialog()

    def remove_quickplay(self, index: int) -> None:
        self.quickplays = [slot for slot in self.quickplays if slot.index != index]
        self.save_quickplays()
        self.refresh_quickplay()

    def open_quickplay_dialog(self) -> None:
        profiles = self.profile_store.list_profiles()
        profile_labels = {f"{profile.name} ({profile.version})": profile for profile in profiles}
        current = self.current_profile()
        default_label = next(
            (label for label, profile in profile_labels.items() if profile.id == current.id),
            next(iter(profile_labels)),
        )

        window = ctk.CTkToplevel(self)
        window.title("Add Quickplay")
        window.geometry("430x270")
        window.resizable(False, False)
        window.transient(self)
        window.grab_set()

        body = ctk.CTkFrame(window, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=18)
        body.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(body, text="Profile").grid(row=0, column=0, sticky="w")
        profile_combo = ctk.CTkComboBox(body, values=list(profile_labels), state="readonly")
        profile_combo.grid(row=1, column=0, sticky="ew", pady=(4, 12))
        profile_combo.set(default_label)

        ctk.CTkLabel(body, text="Server").grid(row=2, column=0, sticky="w")
        host_entry = ctk.CTkEntry(body, placeholder_text="play.example.net or play.example.net:25565")
        host_entry.grid(row=3, column=0, sticky="ew", pady=(4, 12))

        ctk.CTkLabel(body, text="Port").grid(row=4, column=0, sticky="w")
        port_entry = ctk.CTkEntry(body, placeholder_text="25565")
        port_entry.grid(row=5, column=0, sticky="ew", pady=(4, 14))

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.grid(row=6, column=0, sticky="ew")
        actions.grid_columnconfigure(0, weight=1)

        def close() -> None:
            window.grab_release()
            window.destroy()

        def save() -> None:
            profile = profile_labels[profile_combo.get()]
            host, port = self.split_server_address(host_entry.get(), port_entry.get())
            if not host:
                Dialog.show(self, "Quickplay", "Server address is required.", "warning")
                return
            self.quickplays.append(
                QuickPlaySlot(
                    index=len(self.quickplays) + 1,
                    label=f"{profile.name} @ {host}",
                    profile_id=profile.id,
                    server_host=host,
                    server_port=port,
                )
            )
            self.save_quickplays()
            self.refresh_quickplay()
            close()

        ctk.CTkButton(actions, text="Cancel", width=100, command=close).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(actions, text="Add", width=100, command=save).grid(row=0, column=2)

    def launch_last_profile(self) -> None:
        profile_id = str(self.config.get("last_profile_id", self.selected_profile_id))
        profile = self.safe_profile(profile_id)
        self.launch_game(profile.id)

    def launch_quickplay(self, slot: QuickPlaySlot) -> None:
        profile = self.safe_profile(slot.profile_id)
        self.launch_game(profile.id, slot.server_host, slot.server_port)

    def safe_profile(self, profile_id: str) -> Profile:
        try:
            return self.profile_store.load_profile(profile_id)
        except Exception:
            return self.profile_store.load_profile(DEFAULT_PROFILE_ID)

    def set_busy(self, busy: bool, status: str = "") -> None:
        if busy:
            self.status_label.configure(text=status)
            self.progress.grid()
            self.progress.start()
            self.launch_button.configure(state="disabled")
            return
        self.progress.stop()
        self.progress.grid_remove()
        self.status_label.configure(text=status)
        self.launch_button.configure(state="normal")

    def launch_game(
        self,
        profile_id: str | None = None,
        server_host: str | None = None,
        server_port: str | None = None,
    ) -> None:
        username = self.username_entry.get().strip()
        if not valid_username(username):
            Dialog.show(
                self,
                "Invalid username",
                "Username must be 3-16 characters and use only A-Z, 0-9, or underscore.",
                "warning",
            )
            return

        profile = self.safe_profile(profile_id or self.selected_profile_id)
        host = server_host or ""
        port = server_port or ""

        self.config.set("username", username)
        self.config.set("last_profile_id", profile.id)
        self.set_busy(True, f"Preparing {profile.name}...")

        thread = threading.Thread(
            target=self._launch_worker,
            args=(username, profile.id, host or "", port or ""),
            daemon=True,
        )
        thread.start()

    def _launch_worker(self, username: str, profile_id: str, server_host: str, server_port: str) -> None:
        try:
            profile = self.profile_store.load_profile(profile_id)
            version_id = installed_fabric_id(self.paths.minecraft, profile.version)
            if not version_id:
                self.after(0, lambda: self.set_busy(True, f"Installing Fabric {profile.version}..."))
                install_fabric(self.paths.minecraft, profile.version)
                version_id = installed_fabric_id(self.paths.minecraft, profile.version)

            if not version_id:
                raise RuntimeError(f"Fabric {profile.version} could not be installed.")

            self.profile_store.prepare_mods(profile.id, self.paths.minecraft)
            command = build_launch_command(
                self.paths.minecraft,
                version_id,
                username,
                server_host,
                server_port,
            )
            latest_log = rotate_latest_log(self.paths.logs)

            with latest_log.open("w", encoding="utf-8") as log_file:
                self.minecraft_proc = start_process(command, self.paths.minecraft, log_file)
                self.after(0, lambda: self.set_busy(False, f"Running {profile.name}"))
                self.minecraft_proc.wait()

            time.sleep(1)
            self.profile_store.restore_mods(self.paths.minecraft)
            self.minecraft_proc = None
            self.after(0, self.refresh_quickplay)
            self.after(0, lambda: self.set_busy(False, "Minecraft closed"))
        except Exception as error:
            traceback.print_exc()
            self.profile_store.restore_mods(self.paths.minecraft)
            self.minecraft_proc = None
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
            self.profile_store.restore_mods(self.paths.minecraft)
            self.destroy()


def main() -> None:
    app = LauncherApp()
    app.mainloop()
