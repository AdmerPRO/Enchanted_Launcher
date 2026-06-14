from __future__ import annotations

from typing import Literal

import customtkinter as ctk


DialogTone = Literal["info", "warning", "error"]


class Dialog:
    COLORS = {
        "info": "#1f6aa5",
        "warning": "#b58b00",
        "error": "#9b2c2c",
    }

    @staticmethod
    def show(parent: ctk.CTk, title: str, message: str, tone: DialogTone = "info") -> None:
        Dialog._build(parent, title, message, tone, confirm=False)

    @staticmethod
    def confirm(parent: ctk.CTk, title: str, message: str) -> bool:
        return bool(Dialog._build(parent, title, message, "warning", confirm=True))

    @staticmethod
    def _build(
        parent: ctk.CTk,
        title: str,
        message: str,
        tone: DialogTone,
        confirm: bool,
    ) -> bool | None:
        result = {"value": False}
        window = ctk.CTkToplevel(parent)
        window.title(title)
        window.geometry("430x210")
        window.resizable(False, False)
        window.transient(parent)
        window.grab_set()

        x = parent.winfo_x() + max((parent.winfo_width() - 430) // 2, 0)
        y = parent.winfo_y() + max((parent.winfo_height() - 210) // 2, 0)
        window.geometry(f"+{x}+{y}")

        body = ctk.CTkFrame(window, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(
            body,
            text=title,
            text_color=Dialog.COLORS[tone],
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", pady=(0, 8))

        ctk.CTkLabel(
            body,
            text=message,
            justify="left",
            wraplength=380,
        ).pack(fill="x", anchor="w")

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(side="bottom", fill="x", pady=(18, 0))

        def close(value: bool) -> None:
            result["value"] = value
            window.grab_release()
            window.destroy()

        if confirm:
            ctk.CTkButton(buttons, text="Cancel", command=lambda: close(False)).pack(
                side="right",
                padx=(8, 0),
            )
            ctk.CTkButton(
                buttons,
                text="Continue",
                fg_color=Dialog.COLORS[tone],
                command=lambda: close(True),
            ).pack(side="right")
        else:
            ctk.CTkButton(buttons, text="OK", command=lambda: close(True)).pack(side="right")

        parent.wait_window(window)
        return result["value"] if confirm else None
