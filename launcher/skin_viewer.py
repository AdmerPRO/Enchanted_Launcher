from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import customtkinter as ctk
from PIL import Image


Point3D = tuple[float, float, float]
UvRegion = tuple[int, int, int, int]


@dataclass(frozen=True)
class Cuboid:
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float
    uv: dict[str, UvRegion]


@dataclass(frozen=True)
class Face:
    points: tuple[Point3D, Point3D, Point3D, Point3D]
    uv: UvRegion


class SteveSkinViewer(ctk.CTkFrame):
    def __init__(self, master, skin_path: Path, width: int = 230, height: int = 250) -> None:
        super().__init__(master, width=width, height=height, fg_color="#171c22", corner_radius=8)
        self.width = width
        self.height = height
        self.skin_path = skin_path
        self.skin = self.load_skin(skin_path)
        self.yaw = -22.0
        self.drag_start_x = 0
        self.drag_start_yaw = self.yaw

        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self,
            text="SKIN",
            text_color="#8d99a6",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, pady=(16, 0))

        self.canvas = ctk.CTkCanvas(
            self,
            width=width,
            height=height - 40,
            highlightthickness=0,
            bg="#171c22",
        )
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.canvas.bind("<ButtonPress-3>", self.on_right_press)
        self.canvas.bind("<B3-Motion>", self.on_right_drag)
        self.canvas.bind("<Configure>", lambda _event: self.draw())

        self.draw()

    def on_right_press(self, event) -> None:
        self.drag_start_x = event.x
        self.drag_start_yaw = self.yaw

    def on_right_drag(self, event) -> None:
        self.yaw = (self.drag_start_yaw + (event.x - self.drag_start_x) * 0.8) % 360
        self.draw()

    def draw(self) -> None:
        self.canvas.delete("all")
        canvas_w = max(self.canvas.winfo_width(), 1)
        canvas_h = max(self.canvas.winfo_height(), 1)
        scale = min(canvas_w / 28, canvas_h / 38)
        offset_x = canvas_w / 2
        offset_y = canvas_h - 18

        quads = []
        for face in self.model_faces():
            quads.extend(self.textured_quads(face, scale, offset_x, offset_y))

        for depth, coords, color in sorted(quads, key=lambda item: item[0]):
            self.canvas.create_polygon(coords, fill=color, outline=color)

        self.canvas.create_text(
            canvas_w / 2,
            canvas_h - 8,
            text="PPM + drag",
            fill="#6f7c8d",
            font=("Segoe UI", 9),
        )

    def textured_quads(
        self,
        face: Face,
        scale: float,
        offset_x: float,
        offset_y: float,
    ) -> list[tuple[float, list[float], str]]:
        u0, v0, u1, v1 = face.uv
        columns = max(abs(u1 - u0), 1)
        rows = max(abs(v1 - v0), 1)
        quads = []

        for row in range(rows):
            for column in range(columns):
                color = self.sample_color(
                    self.texture_coord(u0, u1, column),
                    self.texture_coord(v0, v1, row),
                )
                if color is None:
                    continue

                s0 = column / columns
                s1 = (column + 1) / columns
                t0 = row / rows
                t1 = (row + 1) / rows
                corners = (
                    self.interpolate(face.points, s0, t0),
                    self.interpolate(face.points, s1, t0),
                    self.interpolate(face.points, s1, t1),
                    self.interpolate(face.points, s0, t1),
                )
                projected = [self.project(point, scale, offset_x, offset_y) for point in corners]
                depth = sum(point[2] for point in projected) / len(projected)
                coords = [coord for x, y, _depth in projected for coord in (x, y)]
                quads.append((depth, coords, color))

        return quads

    @staticmethod
    def texture_coord(start: int, end: int, offset: int) -> int:
        if end >= start:
            return start + offset
        return start - offset - 1

    def sample_color(self, skin_u: int, skin_v: int) -> str | None:
        if self.skin is None:
            return "#ffffff"

        width, height = self.skin.size
        x = min(max(int((skin_u + 0.5) / 64 * width), 0), width - 1)
        y = min(max(int((skin_v + 0.5) / 64 * height), 0), height - 1)
        red, green, blue, alpha = self.skin.getpixel((x, y))
        if alpha < 16:
            return None
        return f"#{red:02x}{green:02x}{blue:02x}"

    def interpolate(
        self,
        points: tuple[Point3D, Point3D, Point3D, Point3D],
        s: float,
        t: float,
    ) -> Point3D:
        top_left, top_right, bottom_right, bottom_left = points
        return (
            top_left[0] * (1 - s) * (1 - t)
            + top_right[0] * s * (1 - t)
            + bottom_right[0] * s * t
            + bottom_left[0] * (1 - s) * t,
            top_left[1] * (1 - s) * (1 - t)
            + top_right[1] * s * (1 - t)
            + bottom_right[1] * s * t
            + bottom_left[1] * (1 - s) * t,
            top_left[2] * (1 - s) * (1 - t)
            + top_right[2] * s * (1 - t)
            + bottom_right[2] * s * t
            + bottom_left[2] * (1 - s) * t,
        )

    def project(self, point: Point3D, scale: float, offset_x: float, offset_y: float) -> tuple[float, float, float]:
        x, y, z = point
        radians = math.radians(self.yaw)
        rotated_x = x * math.cos(radians) - z * math.sin(radians)
        rotated_z = x * math.sin(radians) + z * math.cos(radians)
        screen_x = offset_x + rotated_x * scale
        screen_y = offset_y - y * scale + rotated_z * scale * 0.18
        return screen_x, screen_y, rotated_z

    def model_faces(self) -> Iterable[Face]:
        cuboids = (
            Cuboid(-4, 24, -4, 4, 32, 4, self.head_uv()),
            Cuboid(-4, 12, -2, 4, 24, 2, self.body_uv()),
            Cuboid(-8, 12, -2, -4, 24, 2, self.right_arm_uv()),
            Cuboid(4, 12, -2, 8, 24, 2, self.left_arm_uv()),
            Cuboid(-4, 0, -2, 0, 12, 2, self.right_leg_uv()),
            Cuboid(0, 0, -2, 4, 12, 2, self.left_leg_uv()),
        )
        for cuboid in cuboids:
            yield from self.cuboid_faces(cuboid)

    def cuboid_faces(self, cuboid: Cuboid) -> Iterable[Face]:
        x0, y0, z0 = cuboid.min_x, cuboid.min_y, cuboid.min_z
        x1, y1, z1 = cuboid.max_x, cuboid.max_y, cuboid.max_z
        face_points = {
            "front": ((x0, y1, z1), (x1, y1, z1), (x1, y0, z1), (x0, y0, z1)),
            "back": ((x1, y1, z0), (x0, y1, z0), (x0, y0, z0), (x1, y0, z0)),
            "left": ((x0, y1, z0), (x0, y1, z1), (x0, y0, z1), (x0, y0, z0)),
            "right": ((x1, y1, z1), (x1, y1, z0), (x1, y0, z0), (x1, y0, z1)),
            "top": ((x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)),
            "bottom": ((x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0)),
        }
        for name, points in face_points.items():
            yield Face(points, cuboid.uv[name])

    def load_skin(self, skin_path: Path) -> Image.Image | None:
        try:
            return Image.open(skin_path).convert("RGBA")
        except Exception as error:
            print(f"[SKIN] Failed to load {skin_path}: {error}")
            return None

    @staticmethod
    def head_uv() -> dict[str, UvRegion]:
        return {
            "top": (8, 0, 16, 8),
            "bottom": (16, 0, 24, 8),
            "right": (8, 8, 0, 16),
            "front": (8, 8, 16, 16),
            "left": (24, 8, 16, 16),
            "back": (24, 8, 32, 16),
        }

    @staticmethod
    def body_uv() -> dict[str, UvRegion]:
        return {
            "top": (20, 16, 28, 20),
            "bottom": (28, 16, 36, 20),
            "right": (20, 20, 16, 32),
            "front": (20, 20, 28, 32),
            "left": (32, 20, 28, 32),
            "back": (32, 20, 40, 32),
        }

    @staticmethod
    def right_arm_uv() -> dict[str, UvRegion]:
        return {
            "top": (44, 16, 48, 20),
            "bottom": (48, 16, 52, 20),
            "right": (44, 20, 40, 32),
            "front": (44, 20, 48, 32),
            "left": (52, 20, 48, 32),
            "back": (52, 20, 56, 32),
        }

    def left_arm_uv(self) -> dict[str, UvRegion]:
        if self.skin is not None and self.skin.size[1] >= 64:
            return {
                "top": (36, 48, 40, 52),
                "bottom": (40, 48, 44, 52),
                "right": (36, 52, 32, 64),
                "front": (36, 52, 40, 64),
                "left": (44, 52, 40, 64),
                "back": (44, 52, 48, 64),
            }
        return self.right_arm_uv()

    @staticmethod
    def right_leg_uv() -> dict[str, UvRegion]:
        return {
            "top": (4, 16, 8, 20),
            "bottom": (8, 16, 12, 20),
            "right": (4, 20, 0, 32),
            "front": (4, 20, 8, 32),
            "left": (12, 20, 8, 32),
            "back": (12, 20, 16, 32),
        }

    def left_leg_uv(self) -> dict[str, UvRegion]:
        if self.skin is not None and self.skin.size[1] >= 64:
            return {
                "top": (20, 48, 24, 52),
                "bottom": (24, 48, 28, 52),
                "right": (20, 52, 16, 64),
                "front": (20, 52, 24, 64),
                "left": (28, 52, 24, 64),
                "back": (28, 52, 32, 64),
            }
        return self.right_leg_uv()
