"""Erzeugt Gehäuse, Platine und Layout-Plan für die ESP32-Handheld-Konsole.

Alle Maße in mm. Ursprung = Mitte des Gehäuses, Z = 0 = Unterseite.
Aufruf: python3 generate.py  ->  schreibt stl/*.stl und layout.png
"""
from pathlib import Path

import manifold3d as m
import numpy as np
import trimesh

m.set_circular_segments(64)
OUT = Path(__file__).parent / "stl"

# ---------------------------------------------------------------- Parameter
CASE_W, CASE_D, CASE_R = 160, 80, 14     # Außenmaß + Eckenradius
WALL = 2.0
BOTTOM_H = 20.0                          # Unterschale: Boden bis Platinenauflage
TOP_H = 10.0                             # Oberschale
PLATE = 2.0                              # Dicke Boden / Deckel
PCB_T = 1.6
PCB_Z = BOTTOM_H - 1.0                   # Platine liegt auf den Säulen

DISPLAY_MODULE = (60, 35)                # Display-Platine (rotes Teil)
DISPLAY_WINDOW = (54, 30)                # sichtbarer Ausschnitt im Deckel
DISPLAY_POS = (0, 10)

BTN_HOLE = 6.6                           # für 6x6x12 mm Taster
DPAD_POS = (-55, 12)
ABXY_POS = (55, 12)
BTN_SPACING = 10
START_SELECT = [(-11, -25), (11, -25)]

SPEAKER_POS, SPEAKER_D = (-52, -22), 28

ESP32_SIZE = (28, 55)                    # DevKit hochkant, USB nach hinten
ESP32_POS = (0, CASE_D / 2 - WALL - ESP32_SIZE[1] / 2 - 1)
USB_CUTOUT = 12                          # Schlitzbreite in der Rückwand

SWITCH_POS_X, SWITCH_CUTOUT = 40, (9, 4.5)

BATTERY_BOX = (32, 58)                   # 2x AA-Halter pro Seite
BATTERY_POS = [(-61, 0), (61, 0)]

POSTS = [(sx * 36, sy * 31) for sx in (-1, 1) for sy in (-1, 1)]
POST_D, SCREW_D = 6.0, 2.2               # M2.5-Schrauben


# ---------------------------------------------------------------- Helfer
def rounded_rect(w, d, r):
    return m.CrossSection.square((w - 2 * r, d - 2 * r), center=True).offset(r, m.JoinType.Round)


def box(w, d, h, x=0, y=0, z=0):
    return m.Manifold.cube((w, d, h), center=False).translate((x - w / 2, y - d / 2, z))


def cyl(d, h, x=0, y=0, z=0):
    return m.Manifold.cylinder(h, d / 2, d / 2).translate((x, y, z))


def button_positions(cx, cy):
    s = BTN_SPACING
    return [(cx, cy + s), (cx, cy - s), (cx - s, cy), (cx + s, cy)]


ALL_BUTTONS = button_positions(*DPAD_POS) + button_positions(*ABXY_POS) + START_SELECT


def shell(height, open_top):
    outer = rounded_rect(CASE_W, CASE_D, CASE_R).extrude(height)
    inner = rounded_rect(CASE_W - 2 * WALL, CASE_D - 2 * WALL, CASE_R - WALL).extrude(height)
    return outer - inner.translate((0, 0, PLATE if open_top else -PLATE))


# ---------------------------------------------------------------- Unterschale
def bottom_shell():
    part = shell(BOTTOM_H, open_top=True)
    for x, y in POSTS:
        part += cyl(POST_D, PCB_Z, x, y)
        part -= cyl(SCREW_D, PCB_Z, x, y, PLATE)
    # Führungsrippen für die Batteriehalter
    for x, y in BATTERY_POS:
        w, d = BATTERY_BOX
        part += box(w + 2.4, d + 2.4, 4, x, y, PLATE) - box(w, d, 4, x, y, PLATE)
    # USB-Ausschnitt in der Rückwand (oberer Rand)
    # ESP32 hängt kopfüber an Buchsenleisten unter der Platine -> USB sitzt tief
    part -= box(USB_CUTOUT, 10, BOTTOM_H, ESP32_POS[0], CASE_D / 2, 4)
    # Schiebeschalter
    sw, sh = SWITCH_CUTOUT
    part -= box(sw, 10, sh, SWITCH_POS_X, CASE_D / 2, PCB_Z - sh - 3)
    return part


# ---------------------------------------------------------------- Oberschale
def top_shell():
    part = shell(TOP_H, open_top=False)       # Deckel oben bei z = TOP_H
    top = TOP_H - PLATE
    gap = top - PCB_T - 1.0                     # Platine reicht in die Oberschale
    for x, y in POSTS:
        part += cyl(POST_D, gap, x, y, top - gap)
        part -= cyl(SCREW_D, gap, x, y, top - gap)
    ww, wd = DISPLAY_WINDOW
    part -= box(ww, wd, 10, *DISPLAY_POS, top - 1)
    for x, y in ALL_BUTTONS:
        part -= cyl(BTN_HOLE, 10, x, y, top - 1)
    # Lautsprechergitter
    sx, sy = SPEAKER_POS
    for r, n in [(0, 1), (4.5, 6), (9, 12)]:
        for a in np.linspace(0, 2 * np.pi, n, endpoint=False):
            part -= cyl(2.2, 10, sx + r * np.cos(a), sy + r * np.sin(a), top - 1)
    return part


# ---------------------------------------------------------------- Platine
def pcb():
    part = rounded_rect(CASE_W - 2 * WALL - 1, CASE_D - 2 * WALL - 1, CASE_R - WALL).extrude(PCB_T)
    for x, y in POSTS:
        part -= cyl(2.7, PCB_T, x, y)
    return part


def save(part, name):
    mesh = part.to_mesh()
    tm = trimesh.Trimesh(mesh.vert_properties[:, :3], mesh.tri_verts)
    tm.export(OUT / name)
    b = tm.bounds
    print(f"{name:22s} {b[1][0]-b[0][0]:6.1f} x {b[1][1]-b[0][1]:5.1f} x {b[1][2]-b[0][2]:5.1f} mm, "
          f"watertight={tm.is_watertight}")


# ---------------------------------------------------------------- Layout-Plan
def layout_png(path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

    fig, ax = plt.subplots(figsize=(12, 6.5))
    ax.add_patch(FancyBboxPatch((-CASE_W / 2 + CASE_R, -CASE_D / 2 + CASE_R), CASE_W - 2 * CASE_R,
                                CASE_D - 2 * CASE_R, boxstyle=f"round,pad={CASE_R}",
                                fc="#e8e8e8", ec="#555", lw=2))

    def rect(size, pos, color, label, ls="-", alpha=0.9, label_dy=0):
        w, d = size
        ax.add_patch(Rectangle((pos[0] - w / 2, pos[1] - d / 2), w, d, fc=color, ec="#333",
                               ls=ls, alpha=alpha))
        ax.text(pos[0], pos[1] + label_dy, label, ha="center", va="center", fontsize=9, weight="bold")

    for pos in BATTERY_POS:
        rect(BATTERY_BOX, pos, "#9fb7a8", "", ls="--", alpha=0.5)
        ax.text(pos[0] + np.sign(pos[0]) * 9, pos[1] - 4.5, "2x AA", ha="center", va="center", fontsize=8,
                style="italic", color="#2f5040")
    rect(ESP32_SIZE, ESP32_POS, "#5aa9e6", "", ls="--", alpha=0.5)
    ax.text(ESP32_POS[0], ESP32_POS[1] - 22, "ESP32\n(unter Display)", ha="center", fontsize=8)
    rect(DISPLAY_MODULE, DISPLAY_POS, "#d9534f", "Display", alpha=0.85)
    ax.add_patch(Circle(SPEAKER_POS, SPEAKER_D / 2, fc="#f0a050", ec="#333"))
    ax.text(*SPEAKER_POS, "Lautsprecher", ha="center", va="center", fontsize=8, weight="bold")
    for x, y in ALL_BUTTONS:
        ax.add_patch(Rectangle((x - 3, y - 3), 6, 6, fc="#222"))
        ax.text(x, y - 6.5, f"{x:g}|{y:g}", ha="center", fontsize=6.5, color="#333")
    for x, y in POSTS:
        ax.add_patch(Circle((x, y), POST_D / 2, fc="white", ec="#333"))
    ax.annotate("USB", (ESP32_POS[0], CASE_D / 2), (ESP32_POS[0] + 12, CASE_D / 2 + 6),
                arrowprops=dict(arrowstyle="->"))
    ax.annotate("Schalter", (SWITCH_POS_X, CASE_D / 2), (SWITCH_POS_X + 10, CASE_D / 2 + 6),
                arrowprops=dict(arrowstyle="->"))
    ax.text(DPAD_POS[0], DPAD_POS[1] + 17, "Steuerkreuz", ha="center", fontsize=9)
    ax.text(ABXY_POS[0], ABXY_POS[1] + 17, "A / B / X / Y", ha="center", fontsize=9)
    ax.text(0, START_SELECT[0][1] - 9, "Select     Start", ha="center", fontsize=9)

    ax.set_xlim(-CASE_W / 2 - 6, CASE_W / 2 + 6)
    ax.set_ylim(-CASE_D / 2 - 6, CASE_D / 2 + 12)
    ax.set_aspect("equal")
    ax.set_xticks(range(-80, 81, 10))
    ax.set_yticks(range(-40, 41, 10))
    ax.grid(alpha=0.3)
    ax.set_title("Neues Layout – Draufsicht (Maße in mm, Mitte = 0|0)")
    fig.tight_layout()
    fig.savefig(path, dpi=130)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    save(bottom_shell(), "gehaeuse_unten.stl")
    save(top_shell(), "gehaeuse_oben.stl")
    save(pcb(), "platine.stl")
    layout_png(Path(__file__).parent / "layout.png")
