# Enchanted Launcher

Enchanted Launcher is a lightweight Minecraft Fabric launcher with profiles, inherited default mods, quickplay slots, and offline username support.

## Features

- CustomTkinter desktop UI.
- Rotatable Steve skin preview controlled with right mouse drag.
- Fabric launch support with automatic Fabric install on first launch.
- Portable Minecraft data folder in `.minecraft/` next to the launcher.
- Profile system with a shared `Default` profile.
- Profiles are mod packs only; they do not auto-join servers.
- Mods from `Default` are inherited by every other profile and shown as grey inherited entries.
- Custom mods from local files or Fabric mods from Modrinth.
- Up to four saved quickplay entries for profile + server launches.
- Local log rotation in `logs/`.
- No setup wizard and no automatic optimization pack downloads.
- PyInstaller export script for building a standalone EXE with the project icon.

## Supported Versions

| Version | Fabric |
| --- | --- |
| 1.16.2 | supported |
| 1.17.1 | supported |
| 1.18.2 | supported |
| 1.20.2 | supported |
| 1.21.2 | supported |
| 1.21.8 | supported |
| 1.21.10 | supported |
| 1.21.11 | supported |
| 26.1.2 | supported |

Fabric installation still depends on the version being available through `minecraft-launcher-lib` and Fabric's public metadata.

## Run From Source

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Build EXE

```powershell
python export_to_exe.py
```

The executable is created in `dist/EnchantedLauncher.exe`. You can override the output name:

```powershell
python export_to_exe.py --name EnchantedLauncherDev
```

## Runtime Files

The launcher creates these local files and folders next to the app:

- `launcher_config.json`
- `.minecraft/`
- `profiles/`
- `cache/`
- `logs/`
- `mods/`

These are intentionally ignored by Git.

## License

This project is licensed under the MIT License. See `LICENSE.md`.
