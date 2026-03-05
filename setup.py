"""
setup.py  -  FarmAuto Interactive Configuration Tool
=====================================================
Run this script from Minescript chat:  \\setup
"""

import os
import math
import json
import threading
import time
import minescript
from minescript import EventQueue, EventType
from lib_screen import Screen
from config_lib import Config

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "farmauto_config.json")

CROPS = [
    "PestFarming", "Wheat", "Carrot", "Potato", "Pumpkin", "Sugar_cane", 
    "Melon", "Cactus", "Cocoa", "Mushroom_red", "Mushroom_brown", 
    "Nether_wart", "Sunflower", "Wild_rose"
]

KEY_F8  = 297
KEY_F9  = 298
KEY_F10 = 299
KEY_F11 = 300

def msg(text: str) -> None:
    minescript.echo(text)

def _get_pos_and_angles() -> tuple:
    x, y, z = minescript.player_position()
    yaw, pitch = minescript.player_orientation()
    return (round(x, 3), round(y, 3), round(z, 3), round(yaw, 3), round(pitch, 3))

# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM COMPACT JSON SAVER
# ─────────────────────────────────────────────────────────────────────────────
def save_compact_config(filepath: str, cfg: Config) -> None:
    """ Sauvegarde le fichier JSON de manière très compactée et lisible """
    data = {
        "hoe_slot": cfg.get("hoe_slot", 2),
        "vacuum_slot": cfg.get("vacuum_slot", 1),
        "vacuum_radius": cfg.get("vacuum_radius", 14.0),
        "auto_kill_on_path": cfg.get("auto_kill_on_path", True),
        "auto_verify_tab": cfg.get("auto_verify_tab", True),
        "farm_orientation": cfg.get("farm_orientation", "horizontal"),
        "fishing_rod_slot": cfg.get("fishing_rod_slot", 4),
        "pest_cooldown": cfg.get("pest_cooldown", 300),
        "pest_plot_name": cfg.get("pest_plot_name", "3"),
        "farms": cfg.get("farms", {})
    }
    
    out = "{\n"
    
    # 1. Variables globales
    top_keys = ["hoe_slot", "vacuum_slot", "vacuum_radius", "auto_kill_on_path", 
                "auto_verify_tab", "farm_orientation", "fishing_rod_slot", 
                "pest_cooldown", "pest_plot_name"]
    for k in top_keys:
        if k in data:
            val = json.dumps(data[k])
            out += f'  "{k}": {val},\n'
            
    # 2. Fermes et Waypoints compactés
    out += '  "farms": {\n'
    
    farms = data.get("farms", {})
    farm_keys = list(farms.keys())
    for i, f_name in enumerate(farm_keys):
        f_data = farms[f_name]
        out += f'    "{f_name}": {{\n'
        out += '      "waypoints": [\n'
        
        wps = f_data.get("waypoints", [])
        for j, wp in enumerate(wps):
            # Formate chaque dictionnaire sur une seule ligne (ex: {"type": "start", "x": 10, ...})
            wp_str = json.dumps(wp, separators=(', ', ': '))
            if j < len(wps) - 1:
                out += f'        {wp_str},\n'
            else:
                out += f'        {wp_str}\n'
                
        out += '      ],\n'
        out += f'      "yaw": {f_data.get("yaw", 0.0)},\n'
        out += f'      "pitch": {f_data.get("pitch", 0.0)}\n'
        
        if i < len(farm_keys) - 1:
            out += '    },\n'
        else:
            out += '    }\n'
            
    out += '  }\n}'
    
    # Écriture dans le fichier
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(out)

# ─────────────────────────────────────────────────────────────────────────────
# SETUP STEPS
# ─────────────────────────────────────────────────────────────────────────────
def step1_global_vars(cfg: Config) -> bool:
    result = {"confirmed": False}
    scr = Screen("FarmAuto Setup - Step 1: Global Variables", width=420, height=430)
    PAD, ROW, LW, IW, y = 14, 30, 180, 80, 14

    scr.add_label(text="Hoe Slot (0-8):", width=LW, height=22, x=PAD, y=y)
    inp_hoe = scr.text_input(text=str(cfg.get("hoe_slot", 2)), width=IW, height=22, x=PAD + LW + 6, y=y)
    y += ROW

    scr.add_label(text="Vacuum Slot (0-8):", width=LW, height=22, x=PAD, y=y)
    inp_vac = scr.text_input(text=str(cfg.get("vacuum_slot", 1)), width=IW, height=22, x=PAD + LW + 6, y=y)
    y += ROW

    scr.add_label(text="Fishing Rod Slot (0-8):", width=LW, height=22, x=PAD, y=y)
    inp_rod = scr.text_input(text=str(cfg.get("fishing_rod_slot", 4)), width=IW, height=22, x=PAD + LW + 6, y=y)
    y += ROW

    scr.add_label(text="Pest Spawn Cooldown (sec):", width=LW, height=22, x=PAD, y=y)
    inp_cd = scr.text_input(text=str(cfg.get("pest_cooldown", 300)), width=IW, height=22, x=PAD + LW + 6, y=y)
    y += ROW

    scr.add_label(text="Pest Base Plot Name:", width=LW, height=22, x=PAD, y=y)
    inp_base = scr.text_input(text=str(cfg.get("pest_plot_name", "3")), width=IW, height=22, x=PAD + LW + 6, y=y)
    y += ROW

    scr.add_label(text="Vacuum Radius (blocks):", width=LW, height=22, x=PAD, y=y)
    inp_radius = scr.text_input(text=str(cfg.get("vacuum_radius", 14.0)), width=IW, height=22, x=PAD + LW + 6, y=y)
    y += ROW

    cb_kill = scr.add_checkbox(text="Auto-Kill Pests on Path", width=260, height=24, x=PAD, y=y)
    cb_kill._value.set(cfg.get("auto_kill_on_path", True))
    y += ROW

    cb_tab = scr.add_checkbox(text="Auto-Verify Tab for Pests", width=260, height=24, x=PAD, y=y)
    cb_tab._value.set(cfg.get("auto_verify_tab", True))
    y += ROW

    scr.add_label(text='(Tab OFF: disables auto-scan; F10 manual hunt still works)', width=380, height=18, x=PAD, y=y, fg="#888888", font=("TkDefaultFont", 8))
    y += 26
    scr.add_label(text="─" * 54, width=390, height=14, x=PAD, y=y)
    y += 18

    def on_confirm():
        try:
            hs, vs, fr = int(inp_hoe.value), int(inp_vac.value), int(inp_rod.value)
            vr, pc = float(inp_radius.value), int(inp_cd.value)
            assert 1 <= hs <= 9 and 1 <= vs <= 9 and 1 <= fr <= 9 and vr > 0 and pc > 0
        except Exception:
            scr.add_label(text="Error: slots must be 1-9; radius/cooldown > 0", width=380, height=18, x=PAD, y=y + 30, fg="red")
            return
        cfg.set("hoe_slot", hs)
        cfg.set("vacuum_slot", vs)
        cfg.set("fishing_rod_slot", fr)
        cfg.set("pest_cooldown", pc)
        cfg.set("pest_plot_name", inp_base.value)
        cfg.set("vacuum_radius", vr)
        cfg.set("auto_kill_on_path", bool(cb_kill.value))
        cfg.set("auto_verify_tab", bool(cb_tab.value))
        result["confirmed"] = True
        scr.close()

    scr.add_button(on_click=on_confirm, text="Next →  (Step 2)", width=180, height=28, x=PAD, y=y)
    scr.add_button(on_click=scr.close, text="Cancel", width=90, height=28, x=PAD + 190, y=y)
    scr.show()
    return result["confirmed"]

def _recording_session(crop_name: str) -> dict | None:
    points: list[dict] = []
    msg(f"\n§b[Setup] Recording for §e{crop_name}§b.")
    if crop_name == "PestFarming":
        msg("§d[Info] For PestFarming, the bot will automatically loop End -> Start.")
    msg("§7  F8  → Start   |  F9  → Turn   |  F10 → End   |  F11 → Undo")

    done_event = threading.Event()
    def listener():
        with EventQueue() as eq:
            eq.register_key_listener()
            while not done_event.is_set():
                try: ev = eq.get(timeout=0.1)
                except Exception: continue
                if ev.type != EventType.KEY or ev.action != 1: continue

                if ev.key == KEY_F8:
                    if any(p["type"] == "start" for p in points):
                        msg("§c[Setup] Start already recorded. Press F11 to undo.")
                        continue
                    px, py, pz, yaw, pitch = _get_pos_and_angles()
                    points.append({"type": "start", "x": px, "y": py, "z": pz, "yaw": yaw, "pitch": pitch})
                    msg(f"§a[Setup] START recorded → ({px:.1f}, {py:.1f}, {pz:.1f})")

                elif ev.key == KEY_F9:
                    if not any(p["type"] == "start" for p in points):
                        msg("§c[Setup] Record START (F8) first.")
                        continue
                    px, py, pz, yaw, pitch = _get_pos_and_angles()
                    idx = sum(1 for p in points if p["type"] == "turn") + 1
                    points.append({"type": "turn", "x": px, "y": py, "z": pz, "yaw": yaw, "pitch": pitch})
                    msg(f"§e[Setup] TURN {idx} recorded → ({px:.1f}, {py:.1f}, {pz:.1f})")

                elif ev.key == KEY_F10:
                    if not any(p["type"] == "start" for p in points):
                        msg("§c[Setup] Record START (F8) first.")
                        continue
                    px, py, pz, yaw, pitch = _get_pos_and_angles()
                    points.append({"type": "end", "x": px, "y": py, "z": pz, "yaw": yaw, "pitch": pitch})
                    msg(f"§c[Setup] END recorded → ({px:.1f}, {py:.1f}, {pz:.1f})")
                    done_event.set()

                elif ev.key == KEY_F11:
                    if points:
                        removed = points.pop()
                        msg(f"§d[Setup] Undone: {removed['type'].upper()}")
                    else:
                        msg("§c[Setup] Nothing to undo.")

    t = threading.Thread(target=listener, daemon=True)
    t.start()
    t.join() 
    if not points or not any(p["type"] == "end" for p in points): return None
    return points

def _choose_angle(points: list[dict]) -> tuple[float, float]:
    result = {"yaw": None, "pitch": None}
    
    # Moyenne circulaire pour le Yaw
    sum_sin = sum(math.sin(math.radians(p["yaw"])) for p in points)
    sum_cos = sum(math.cos(math.radians(p["yaw"])) for p in points)
    avg_yaw = math.degrees(math.atan2(sum_sin, sum_cos))
    
    # Moyenne classique pour le Pitch
    avg_pitch = sum(p["pitch"] for p in points) / len(points)
    
    avg_yaw = round(avg_yaw, 1)
    avg_pitch = round(avg_pitch, 1)

    scr = Screen("FarmAuto Setup - Locked Angle", width=420, height=170)
    PAD, y = 14, 14
    
    scr.add_label(text="Select the locked Yaw/Pitch for this farm:", width=390, height=22, x=PAD, y=y)
    y += 30

    def on_average():
        result["yaw"], result["pitch"] = avg_yaw, avg_pitch
        scr.close()

    btn_text = f"Use Average  (Yaw: {avg_yaw}° | Pitch: {avg_pitch}°)"
    scr.add_button(on_click=on_average, text=btn_text, width=392, height=28, x=PAD, y=y)
    y += 36

    scr.add_label(text="- or enter custom values -", width=390, height=18, x=PAD, y=y, fg="#888888")
    y += 24

    scr.add_label(text="Yaw:", width=35, height=22, x=PAD, y=y)
    inp_yaw = scr.text_input(text=str(avg_yaw), width=60, height=22, x=PAD + 35, y=y)
    
    scr.add_label(text="Pitch:", width=40, height=22, x=PAD + 110, y=y)
    inp_pitch = scr.text_input(text=str(avg_pitch), width=60, height=22, x=PAD + 150, y=y)

    def on_custom():
        try:
            result["yaw"], result["pitch"] = float(inp_yaw.value), float(inp_pitch.value)
            scr.close()
        except ValueError: pass

    scr.add_button(on_click=on_custom, text="Use Custom", width=100, height=26, x=PAD + 230, y=y)
    
    scr.show()
    return float(result["yaw"] if result["yaw"] is not None else 0.0), float(result["pitch"] if result["pitch"] is not None else 0.0)

def step2_farm_layouts(cfg: Config) -> bool:
    farms: dict = cfg.get("farms", {})
    orientation_result = {"value": None}

    def ask_orientation():
        scr = Screen("FarmAuto Setup - Farm Orientation", width=340, height=140)
        scr.add_label(text="Are your Garden farms Horizontal or Vertical?", width=310, height=22, x=14, y=14)
        def on_h(): orientation_result["value"] = "horizontal"; scr.close()
        def on_v(): orientation_result["value"] = "vertical"; scr.close()
        scr.add_button(on_click=on_h, text="Horizontal", width=130, height=30, x=14,  y=56)
        scr.add_button(on_click=on_v, text="Vertical",   width=130, height=30, x=160, y=56)
        scr.show()

    ask_orientation()
    if orientation_result["value"] is None: return False
    cfg.set("farm_orientation", orientation_result["value"])

    for crop in CROPS:
        already_configured = crop in farms
        action_result = {"action": None}

        def build_crop_screen(c=crop, ac=already_configured):
            scr = Screen(f"FarmAuto Setup - {c}", width=340, height=160)
            state_txt = "§a[Configured]" if ac else "[Not configured]"
            scr.add_label(text=f"{c}  {state_txt.replace('§a', '')}", width=310, height=22, x=14, y=14)
            def on_create(): action_result["action"] = "create" if not ac else "modify"; scr.close()
            def on_skip(): action_result["action"] = "skip"; scr.close()
            def on_quit(): action_result["action"] = "quit"; scr.close()
            scr.add_button(on_click=on_create, text="Modify" if ac else "Create", width=90, height=28, x=14,  y=60)
            scr.add_button(on_click=on_skip, text="Pass (Skip)", width=110, height=28, x=114, y=60)
            scr.add_button(on_click=on_quit, text="Done - Save Now", width=130, height=28, x=190, y=104)
            scr.show()

        build_crop_screen()
        action = action_result["action"]
        if action == "quit": break
        if action == "skip":
            msg(f"§7[Setup] Skipped {crop}.")
            continue
        if action in ("create", "modify"):
            msg(f"\n§b[Setup] Starting recording for §e{crop}§b.")
            points = _recording_session(crop)
            if not points:
                msg(f"§c[Setup] Recording aborted for {crop}.")
                continue
            yaw, pitch = _choose_angle(points)
            waypoint_list = [{"type": p["type"], "x": p["x"], "y": p["y"], "z": p["z"]} for p in points]
            farms[crop] = {"waypoints": waypoint_list, "yaw": yaw, "pitch": pitch}
            cfg.set("farms", farms)
            msg(f"§a[Setup] §e{crop}§a saved with {len(waypoint_list)} point(s), yaw={yaw:.1f}°, pitch={pitch:.1f}°.")
    cfg.set("farms", farms)
    return True

def step3_summary(cfg: Config) -> bool:
    result = {"saved": False}
    farms: dict = cfg.get("farms", {})
    farm_lines = []
    for crop in CROPS:
        if crop in farms:
            f = farms[crop]
            farm_lines.append(f"  {crop:<16} | {len(f.get('waypoints', []))} pts | yaw={f['yaw']:.1f}° pitch={f['pitch']:.1f}°")
        else:
            farm_lines.append(f"  {crop:<16} | (not configured)")

    summary_text = (
        f"Hoe slot:          {cfg.get('hoe_slot', '?')}\n"
        f"Vacuum slot:       {cfg.get('vacuum_slot', '?')}\n"
        f"Rod slot:          {cfg.get('fishing_rod_slot', '?')}\n"
        f"Pest Base Plot:    {cfg.get('pest_plot_name', '?')}\n"
        f"Pest Cooldown:     {cfg.get('pest_cooldown', '?')}s\n"
        f"Vacuum radius:     {cfg.get('vacuum_radius', '?')} blocks\n"
        f"Auto-kill on path: {cfg.get('auto_kill_on_path', '?')}\n"
        "─────────────────────────────────────────\n" + "\n".join(farm_lines)
    )

    win_h = 80 + (summary_text.count("\n") + 1) * 16
    scr = Screen("FarmAuto Setup - Summary & Save", width=560, height=win_h)
    scr.add_label(text=summary_text, width=530, height=win_h - 60, x=14, y=10, justify="left", anchor="nw", font=("Courier", 9))

    def on_save():
        # On utilise notre formateur personnalisé à la place de cfg.save()
        save_compact_config(CONFIG_FILE, cfg)
        result["saved"] = True
        msg(f"§a[Setup] Configuration saved in COMPACT format to {CONFIG_FILE}. Ready to run FarmAuto!")
        scr.close()

    scr.add_button(on_click=on_save, text="Save & Finish", width=150, height=30, x=14,  y=win_h - 46)
    scr.add_button(on_click=scr.close, text="Cancel", width=90,  height=30, x=174, y=win_h - 46)
    scr.show()
    return result["saved"]

def main():
    msg("\n§b╔══════════════════════════════════════╗")
    msg("§b║  §eFarmAuto Setup Wizard §b║")
    msg("§b╚══════════════════════════════════════╝\n")
    msg("§7Step 1 → Global Variables")
    msg("§7Step 2 → Farm Layouts  (F8 Start | F9 Turn | F10 End | F11 Undo)")
    msg("§7Step 3 → Summary & Save\n")

    cfg = Config(CONFIG_FILE)

    msg("§e[Setup] Opening Step 1 window…")
    if not step1_global_vars(cfg):
        msg("§c[Setup] Aborted at Step 1.")
        return
    msg("§a[Setup] Step 1 complete.")

    msg("§e[Setup] Starting Step 2: Farm Layouts…")
    if not step2_farm_layouts(cfg):
        msg("§c[Setup] Aborted at Step 2.")
        return
    msg("§a[Setup] Step 2 complete.")

    msg("§e[Setup] Opening Step 3 summary…")
    if not step3_summary(cfg):
        msg("§c[Setup] Save cancelled. No changes written.")
        return
    msg("§a[Setup] Done! Run §e\\\\FarmAuto §ato start farming.")

if __name__ == "__main__":
    main()