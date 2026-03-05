"""
FarmAuto.py  –  Dynamic Farming Macro with PestFarming Mode
===============================================================
Run from Minescript chat:  \\FarmAuto
"""

import os
import math
import random
import re
import threading
import time

import minescript
from minescript import EventQueue, EventType
from config_lib import Config

# ─────────────────────────────────────────────────────────────────────────────
# Config loading
# ─────────────────────────────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "farmauto_config.json")

_cfg = Config(CONFIG_FILE)

HOE_SLOT          = int(_cfg.get("hoe_slot",          3))
VACUUM_SLOT       = int(_cfg.get("vacuum_slot",        2))
FISHING_ROD_SLOT  = int(_cfg.get("fishing_rod_slot",   4))
PEST_COOLDOWN     = int(_cfg.get("pest_cooldown",      300))
PEST_PLOT_NAME    = str(_cfg.get("pest_plot_name",     "3"))
VACUUM_RADIUS     = float(_cfg.get("vacuum_radius",    14.0))
AUTO_KILL_ON_PATH = bool(_cfg.get("auto_kill_on_path", True))
AUTO_VERIFY_TAB   = bool(_cfg.get("auto_verify_tab",  True))
FARMS_CFG: dict   = _cfg.get("farms", {})

# ─────────────────────────────────────────────────────────────────────────────
# Message helpers
# ─────────────────────────────────────────────────────────────────────────────
beforeMessage = ""
afterMessage  = ""

def msg(text: str, before: str = None, after: str = None) -> None:
    if before is None: before = beforeMessage
    if after is None:  after = afterMessage
    minescript.echo(before + text + after)

# ─────────────────────────────────────────────────────────────────────────────
# Smooth camera
# ─────────────────────────────────────────────────────────────────────────────
CONFIRM_YAW_PITCH = False

def look(target_yaw: float, target_pitch: float, duration: float = 0.22, steps: int = 70) -> None:
    try:
        sy, sp = minescript.player_orientation()
    except Exception:
        return

    def angle_diff(a, b): return (b - a + 180) % 360 - 180

    dy = angle_diff(sy, target_yaw)
    dp = target_pitch - sp

    if abs(dy) < 1.0 and abs(dp) < 1.0:
        minescript.player_set_orientation(target_yaw, target_pitch)
        return

    step_time = duration / steps
    power = 5

    for i in range(1, steps + 1):
        t = i / steps
        if t < 0.5: s = 0.5 * (2 * t) ** power
        else:       s = 1 - 0.5 * (2 * (1 - t)) ** power

        jitter = (1 - abs(0.5 - t) * 2) * 0.2
        minescript.player_set_orientation(
            sy + dy * s + random.uniform(-jitter, jitter),
            sp + dp * s + random.uniform(-jitter * 0.7, jitter * 0.7),
        )
        time.sleep(step_time)

    if CONFIRM_YAW_PITCH:
        minescript.player_set_orientation(target_yaw, target_pitch)

# ─────────────────────────────────────────────────────────────────────────────
# Java bridge (Tab list access)
# ─────────────────────────────────────────────────────────────────────────────
try:
    from system.lib.java import JavaClass
    Minecraft = JavaClass("net.minecraft.client.Minecraft")
    mc = Minecraft.getInstance()
except Exception:
    Minecraft = None
    mc = None

# ─────────────────────────────────────────────────────────────────────────────
# Dynamic waypoint table
# ─────────────────────────────────────────────────────────────────────────────
WAYPOINTS: dict[str, tuple] = {}
for _crop, _data in FARMS_CFG.items():
    _pts = _data.get("waypoints", [])
    if not _pts: continue
    _start = _pts[0]
    WAYPOINTS[_crop] = (
        (_start["x"], _start["y"], _start["z"]),
        (_data.get("yaw", 0.0), _data.get("pitch", 0.0)),
        _pts,
    )

WAYPOINT_RADIUS_SQ = 3.0 ** 2

# ─────────────────────────────────────────────────────────────────────────────
# Constants & Timing
# ─────────────────────────────────────────────────────────────────────────────
DETECTION_RADIUS    = 16.0
DETECTION_RADIUS_SQ = DETECTION_RADIUS ** 2

PEST_NAMES = ["Field Mouse", "Fly", "Cricket", "Locust", "Rat", "Earthworm", "Mite", "Moth", "Slug", "Beetle", "Firefly", "Praying Mantis", "Dragonfly", "Mosquito"]

PLOT_COORDS = {
    "21": (-192, 80, -192), "13": (-96, 80, -192), "9":  (0,  80, -192), "14": (96,   80, -192), "22": (192, 80, -192),
    "15": (-192, 80, -96),  "5":  (-96, 80, -96),  "1":  (0,  80, -96),  "6":  (96,   80, -96),  "16": (192, 80, -96),
    "10": (-192, 80, 0),    "2":  (-96, 80, 0),    "Barn": (0, 80, 0),   "The Barn": (0, 80, 0), "3":  (96,   80, 0),    "11": (192, 80, 0),
    "17": (-192, 80, 96),   "7":  (-96, 80, 96),   "4":  (0,  80, 96),   "8":  (96,   80, 96),   "18": (192, 80, 96),
    "23": (-192, 80, 192),  "19": (-96, 80, 192),  "12": (0,  80, 192),  "20": (96,   80, 192),  "24": (192, 80, 192),
}

LOOP_SLEEP          = 0.04
DROP_DOWN_DELAY     = 0.2
ENTITY_CACHE_TTL    = 0.2
PEST_INFO_CACHE_TTL = 1.5
PEST_CHECK_INTERVAL = 0.2
_STRIP_FORMAT = re.compile(r"§.")

# ─────────────────────────────────────────────────────────────────────────────
# Caches
# ─────────────────────────────────────────────────────────────────────────────
_entity_cache: list = []
_entity_cache_time: float = 0.0

def _invalidate_entity_cache() -> None:
    global _entity_cache_time
    _entity_cache_time = 0.0

def _get_entities_cached() -> list:
    global _entity_cache, _entity_cache_time
    now = time.monotonic()
    if now - _entity_cache_time < ENTITY_CACHE_TTL: return _entity_cache
    try:
        _entity_cache = minescript.entities()
        _entity_cache_time = now
    except Exception:
        _entity_cache = []
    return _entity_cache

_pest_info_cache: tuple = ("0", [])
_pest_info_cache_time: float = 0.0

def _invalidate_pest_cache() -> None:
    global _pest_info_cache_time
    _pest_info_cache_time = 0.0

def get_tablist_lines() -> list:
    if mc is None: return []
    try:
        minescript.set_default_executor(minescript.script_loop)
        connection = mc.getConnection()
        if not connection: return []
        players = connection.getOnlinePlayers()
        lines = []
        for info in players:
            comp = info.getTabListDisplayName()
            if comp: lines.append(comp.getString())
        return lines
    except Exception: return []

def _get_pest_info_fresh() -> tuple:
    tab_lines = get_tablist_lines()
    total = "0"
    plots: list[str] = []
    for line in tab_lines:
        line = _STRIP_FORMAT.sub("", line).strip()
        if "Alive:" in line:
            parts = line.split("Alive:", 1)
            m = re.search(r"\d+", parts[1])
            total = m.group() if m else parts[1].strip()
        elif "Plots:" in line:
            parts = line.split("Plots:", 1)
            plots = [p.strip() for p in parts[1].strip().split(",") if p.strip()]
    return total, plots

def get_pest_info() -> tuple:
    global _pest_info_cache, _pest_info_cache_time
    now = time.monotonic()
    if now - _pest_info_cache_time < PEST_INFO_CACHE_TTL: return _pest_info_cache
    result = _get_pest_info_fresh()
    _pest_info_cache = result
    _pest_info_cache_time = now
    return result

def run_pest_check() -> None:
    _invalidate_pest_cache()
    total, plots = get_pest_info()
    if total == "0" or not total: msg("§aAlive Pests: 0")
    else:
        text = f"§cAlive Pests: {total}"
        for p in plots: text += f"\nPlot {p}"
        msg(text)

# ─────────────────────────────────────────────────────────────────────────────
# Fishing Rod
# ─────────────────────────────────────────────────────────────────────────────

def use_fishing_rod() -> None:
    msg("§b[Action] Casting Fishing Rod...")
    minescript.player_inventory_select_slot(FISHING_ROD_SLOT)
    time.sleep(0.2)
    minescript.player_press_use(True)
    time.sleep(0.1)
    minescript.player_press_use(False)
    time.sleep(0.5)

# ─────────────────────────────────────────────────────────────────────────────
# Background Chat Listener for PestFarming
# ───────────────────────────────────────────────────────²──────────────────────
def tail_chat_for_pests(stop_event: threading.Event, pest_spawn_event: threading.Event, plot_info: list):
    exec_dir = os.path.dirname(os.path.abspath(__file__))
    mc_dir = os.path.dirname(os.path.dirname(os.path.dirname(exec_dir)))
    log_path = os.path.join(mc_dir, "logs", "latest.log")
    
    if not os.path.exists(log_path):
        msg(f"§c[ChatListener] Error: Cannot find log file at {log_path}. Pest detection failed.")
        return
        
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        f.seek(0, os.SEEK_END)
        while not stop_event.is_set():
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue
            
            clean_line = _STRIP_FORMAT.sub("", line).strip()
            
            if "Pest" in clean_line and "Plot -" in clean_line:
                num_match = re.search(r"([0-9]+)[^a-zA-Z]*Pest", clean_line)
                pest_count = num_match.group(1) if num_match else "1"
                
                plot_match = re.search(r"in Plot - ([a-zA-Z0-9_]+)", clean_line)
                if plot_match:
                    plot_name = plot_match.group(1).strip()
                    plot_info.clear()
                    plot_info.append(plot_name)
                    plot_info.append(pest_count)
                    msg(f"§a[ChatListener] {pest_count} PEST(S) DETECTED IN PLOT: {plot_name}!")
                    pest_spawn_event.set()

# ─────────────────────────────────────────────────────────────────────────────
# Safety helpers
# ─────────────────────────────────────────────────────────────────────────────
def release_all_keys() -> None:
    minescript.player_press_forward(False)
    minescript.player_press_backward(False)
    minescript.player_press_left(False)
    minescript.player_press_right(False)
    minescript.player_press_attack(False)
    minescript.player_press_use(False)
    minescript.player_press_jump(False)
    try: minescript.player_press_sprint(False)
    except Exception: pass
    try: minescript.player_press_sneak(False)
    except Exception: pass

def warp_garden() -> None:
    release_all_keys()
    minescript.execute("/warp garden")
    time.sleep(1.5)
    minescript.player_press_sneak(True)
    time.sleep(0.1)
    minescript.player_press_sneak(False)

def _dist_sq(p1, p2) -> float: return (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2 + (p1[2] - p2[2]) ** 2
def get_distance(p1, p2) -> float: return math.sqrt(_dist_sq(p1, p2))

def aim_at(target_pos) -> None:
    try:
        p_pos = minescript.player_position()
        dx = target_pos[0] - p_pos[0]
        dy = target_pos[1] - (p_pos[1] + 1.2)
        dz = target_pos[2] - p_pos[2]
        dist_h = math.sqrt(dx ** 2 + dz ** 2)
        yaw   = math.degrees(math.atan2(-dx, dz))
        pitch = -math.degrees(math.atan2(dy, dist_h))
        minescript.player_set_orientation(yaw, pitch)
    except Exception: pass

# ─────────────────────────────────────────────────────────────────────────────
# In-path lightweight pest kill
# ─────────────────────────────────────────────────────────────────────────────
_VISION_HALF_ANGLE = 180.0
_VISION_RADIUS     = 10.0
_last_pest_check: float = 0.0

def get_all_pests(radius: float) -> list:
    try: p_pos = minescript.player_position()
    except Exception: return []
    r_sq = radius * radius
    found = []
    for ent in _get_entities_cached():
        if ent.name and any(name in ent.name for name in PEST_NAMES):
            if _dist_sq(p_pos, ent.position) <= r_sq: found.append(ent)
    return found

def find_nearest_pest(radius: float = DETECTION_RADIUS):
    pests = get_all_pests(radius)
    if not pests: return None
    try:
        p_pos = minescript.player_position()
        return min(pests, key=lambda p: _dist_sq(p_pos, p.position))
    except Exception: return None

def _pest_in_vision_cone() -> bool:
    try:
        p_pos = minescript.player_position()
        yaw, _ = minescript.player_orientation()
    except Exception: return False
    yaw_rad = math.radians(yaw)
    fx, fz = -math.sin(yaw_rad), math.cos(yaw_rad)
    r_sq = _VISION_RADIUS ** 2
    for ent in _get_entities_cached():
        if not (ent.name and any(n in ent.name for n in PEST_NAMES)): continue
        ep = ent.position
        if _dist_sq(p_pos, ep) > r_sq: continue
        dx, dz = ep[0] - p_pos[0], ep[2] - p_pos[2]
        dlen = math.sqrt(dx * dx + dz * dz) or 1e-9
        dot = (dx / dlen) * fx + (dz / dlen) * fz
        angle = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
        if angle <= _VISION_HALF_ANGLE: return True
    return False

def check_and_kill_pests(yaw_origin: float, pitch_origin: float, stop_event: threading.Event) -> bool:
    if not AUTO_KILL_ON_PATH: return False
    global _last_pest_check
    now = time.monotonic()
    if now - _last_pest_check < PEST_CHECK_INTERVAL: return False
    _last_pest_check = now
    _invalidate_entity_cache()
    if not _pest_in_vision_cone(): return False
    target = find_nearest_pest(radius=_VISION_RADIUS)
    if not target: return False

    msg("§cPest in path! Stopping to vacuum.")
    release_all_keys()
    minescript.player_inventory_select_slot(VACUUM_SLOT)
    time.sleep(0.1)
    while target and not stop_event.is_set():
        aim_at(target.position)
        minescript.player_press_use(True)
        time.sleep(0.08)
        _invalidate_entity_cache()
        target = find_nearest_pest(radius=_VISION_RADIUS)
    minescript.player_press_use(False)
    if stop_event.is_set(): return True

    msg("§aPest cleared. Resuming.")
    minescript.player_inventory_select_slot(HOE_SLOT)
    look(yaw_origin, pitch_origin)
    minescript.player_press_attack(True)
    time.sleep(0.1)
    return True

# ─────────────────────────────────────────────────────────────────────────────
# Pest Hunter 3D 
# ─────────────────────────────────────────────────────────────────────────────
def ascend_to_79(stop_event: threading.Event) -> None:
    try:
        if minescript.player_position()[1] < 78:
            minescript.player_press_jump(True)
            while minescript.player_position()[1] < 78 and not stop_event.is_set(): time.sleep(0.03)
            minescript.player_press_jump(False)
    except Exception: pass

def fly_to_2d(tx: float, tz: float, stop_event: threading.Event, sprint: bool = False) -> None:
    try: minescript.player_press_sprint(sprint)
    except Exception: pass
    minescript.player_press_forward(True)
    while not stop_event.is_set():
        try:
            p = minescript.player_position()
            dx, dz = tx - p[0], tz - p[2]
            if dx ** 2 + dz ** 2 <= 25.0: break
            yaw = math.degrees(math.atan2(-dx, dz))
            minescript.player_set_orientation(yaw, 0.0)
        except Exception: pass
        time.sleep(LOOP_SLEEP)
    minescript.player_press_forward(False)
    if sprint:
        try: minescript.player_press_sprint(False)
        except Exception: pass

def _kill_target_chain(target, stop_event: threading.Event) -> int:
    kills = 0
    while target and not stop_event.is_set():
        aim_at(target.position)
        minescript.player_press_use(True)
        try:
            if _dist_sq(minescript.player_position(), target.position) <= 16.0: minescript.player_press_forward(False)
            else: minescript.player_press_forward(True)
        except Exception: pass
        time.sleep(0.08)
        _invalidate_entity_cache()
        prev_uuid = getattr(target, "uuid", None)
        target    = find_nearest_pest(radius=90.0)
        if target is None or getattr(target, "uuid", None) != prev_uuid: kills += 1
    minescript.player_press_forward(False)
    minescript.player_press_use(False)
    return kills

def _rescan_tab_fresh() -> tuple:
    _invalidate_pest_cache()
    return get_pest_info()

def action_hunt_pests(stop_event: threading.Event, known_total: str | None = None, known_plots: list | None = None, return_to_garden: bool = True) -> None:
    if known_total is not None and known_plots is not None:
        total_str, infested_plots = known_total, known_plots
    else:
        msg("§e[Pest Hunter] Scanning Tab…")
        total_str, infested_plots = _rescan_tab_fresh()
    if total_str == "0" or not infested_plots:
        msg("§a[Pest Hunter] Tab is clear! No pests to hunt.")
        return
    try: global_total = int(total_str)
    except ValueError: global_total = 1
    msg(f"§a[Pest Hunter] {global_total} pest(s) on plots: {', '.join(infested_plots)}. Hunting…")
    minescript.player_inventory_select_slot(VACUUM_SLOT)
    try:
        if minescript.player_position()[1] < 79:
            minescript.player_press_jump(True);  time.sleep(0.1)
            minescript.player_press_jump(False); time.sleep(0.1)
            minescript.player_press_jump(True);  time.sleep(0.1)
            minescript.player_press_jump(False); time.sleep(0.2)
    except Exception: pass
    global_kills = 0
    def remaining_global() -> int: return max(0, global_total - global_kills)
    plots_to_visit = list(infested_plots)
    
    while plots_to_visit and not stop_event.is_set():
        try:
            px, py, pz = minescript.player_position()
            def dist_plot(p_num):
                if p_num in PLOT_COORDS:
                    cx, cy, cz = PLOT_COORDS[p_num]
                    return (px - cx) ** 2 + (pz - cz) ** 2
                return float("inf")
            plots_to_visit.sort(key=dist_plot)
        except Exception: pass
        target_plot = plots_to_visit[0]
        
        if target_plot not in PLOT_COORDS:
            msg(f"§e[Pest Hunter] Custom plot '{target_plot}' detected. Scanning globally...")
            ascend_to_79(stop_event)
            _invalidate_entity_cache()
            target = find_nearest_pest(radius=250.0)
            
            if not target:
                for angle in [0, 90, 180, -90]:
                    minescript.player_set_orientation(angle, 0.0)
                    time.sleep(0.3)
                    _invalidate_entity_cache()
                    target = find_nearest_pest(radius=250.0)
                    if target: break
                    
            if target:
                msg("§a[Pest Hunter] Found pest for custom plot! Engaging...")
                kills = _kill_target_chain(target, stop_event)
                global_kills += kills
                plots_to_visit.pop(0)
                continue
            else:
                msg("§c[Pest Hunter] Could not locate pest for custom plot. Skipping.")
                plots_to_visit.pop(0)
                continue

        tx, ty, tz = PLOT_COORDS[target_plot]
        msg(f"§c[Pest Hunter] → Plot {target_plot} ({remaining_global()} pest(s) remaining)…")
        ascend_to_79(stop_event)
        fly_to_2d(tx, tz, stop_event, sprint=True)
        if stop_event.is_set(): break
        plot_kills = 0
        all_corners = [(tx + 25, tz - 25), (tx + 25, tz + 25), (tx - 25, tz + 25), (tx - 25, tz - 25)]
        unvisited_corners = list(all_corners)
        _invalidate_entity_cache()
        target = find_nearest_pest(radius=90.0)
        
        while not stop_event.is_set():
            if target:
                kills_this_chain = _kill_target_chain(target, stop_event)
                plot_kills   += kills_this_chain
                global_kills += kills_this_chain
                if kills_this_chain > 0: msg(f"§a[Pest Hunter] {kills_this_chain} kill(s). Plot: {plot_kills}. Global rem: {remaining_global()}.")
                if stop_event.is_set(): break
                ascend_to_79(stop_event)
                _invalidate_entity_cache()
                target = find_nearest_pest(radius=90.0)
                if target: continue
                if remaining_global() <= 0:
                    msg("§a[Pest Hunter] Kill tracker says all pests eliminated.")
                    plots_to_visit.clear(); break
                if not unvisited_corners:
                    msg("§e[Pest Hunter] Full sweep done, no pest. Re-reading Tab…")
                    fresh_total_str, fresh_plots = _rescan_tab_fresh()
                    try:
                        tab_total = int(fresh_total_str)
                        if tab_total < remaining_global(): global_kills += remaining_global() - tab_total
                    except ValueError: tab_total = 0
                    if fresh_total_str == "0" or tab_total == 0:
                        msg("§a[Pest Hunter] Tab clear after sweep. Done.")
                        plots_to_visit.clear(); break
                    if target_plot not in fresh_plots:
                        msg(f"§a[Pest Hunter] Plot {target_plot} clean per Tab.")
                        plots_to_visit.pop(0)
                        for fp in fresh_plots:
                            if fp not in plots_to_visit and fp in PLOT_COORDS: plots_to_visit.append(fp)
                        break
                    msg(f"§c[Pest Hunter] Plot {target_plot} still listed. Returning center…")
                    fly_to_2d(tx, tz, stop_event, sprint=False)
                    unvisited_corners = list(all_corners)
                    _invalidate_entity_cache()
                    target = find_nearest_pest(radius=90.0)
                    if target: continue
                    msg(f"§c[Pest Hunter] Not found after reset. Skipping plot {target_plot}.")
                    plots_to_visit.pop(0); break
                msg(f"§e[Pest Hunter] Resuming corner sweep ({len(unvisited_corners)} left) for plot {target_plot}…")
                target = None
            else:
                if not unvisited_corners:
                    msg("§e[Pest Hunter] Full sweep, no pest. Re-reading Tab…")
                    fresh_total_str, fresh_plots = _rescan_tab_fresh()
                    try:
                        tab_total = int(fresh_total_str)
                        if tab_total < remaining_global(): global_kills += remaining_global() - tab_total
                    except ValueError: tab_total = 0
                    if fresh_total_str == "0" or tab_total == 0:
                        msg("§a[Pest Hunter] Tab clear after sweep. Done.")
                        plots_to_visit.clear(); break
                    if target_plot not in fresh_plots:
                        msg(f"§a[Pest Hunter] Plot {target_plot} clean per Tab.")
                        plots_to_visit.pop(0)
                        for fp in fresh_plots:
                            if fp not in plots_to_visit and fp in PLOT_COORDS: plots_to_visit.append(fp)
                        break
                    msg(f"§c[Pest Hunter] Plot {target_plot} still listed. Returning center…")
                    fly_to_2d(tx, tz, stop_event, sprint=False)
                    unvisited_corners = list(all_corners)
                    _invalidate_entity_cache()
                    target = find_nearest_pest(radius=90.0)
                    if target: continue
                    msg(f"§c[Pest Hunter] Not found after reset. Skipping plot {target_plot}.")
                    plots_to_visit.pop(0); break
                try:
                    pp = minescript.player_position()
                    unvisited_corners.sort(key=lambda c: (c[0] - pp[0]) ** 2 + (c[1] - pp[2]) ** 2)
                except Exception: pass
                cx, cz = unvisited_corners[0]
                corners_total = len(all_corners)
                corners_done  = corners_total - len(unvisited_corners)
                msg(f"§e[Pest Hunter] Corner {corners_done + 1}/{corners_total} of plot {target_plot}…")
                try: minescript.player_press_sprint(True)
                except Exception: pass
                minescript.player_press_forward(True)
                while not stop_event.is_set():
                    _invalidate_entity_cache()
                    target = find_nearest_pest(radius=80.0)
                    if target:
                        msg("§a[Pest Hunter] Pest spotted during sweep! Engaging…")
                        break
                    try:
                        p = minescript.player_position()
                        dx, dz = cx - p[0], cz - p[2]
                        if dx ** 2 + dz ** 2 <= 25.0: break
                        yaw = math.degrees(math.atan2(-dx, dz))
                        minescript.player_set_orientation(yaw, 0.0)
                    except Exception: pass
                    time.sleep(LOOP_SLEEP)
                minescript.player_press_forward(False)
                try: minescript.player_press_sprint(False)
                except Exception: pass
                if stop_event.is_set(): break
                if target: unvisited_corners.pop(0); continue
                unvisited_corners.pop(0)

    if not stop_event.is_set() and return_to_garden:
        msg("§a[Pest Hunter] Mission accomplished.")
        warp_garden()

# ─────────────────────────────────────────────────────────────────────────────
# NEW UNIVERSAL NAVIGATION ENGINE (WITH WALL-HUGGING STABILIZATION)
# ─────────────────────────────────────────────────────────────────────────────
def Maps_waypoints(yaw: float, pitch: float, waypoint_list: list, stop_event: threading.Event, infinite_loop: bool = False, pest_spawn_event: threading.Event = None, start_index: int = 1, next_rod_cast_time: float = 0.0) -> tuple[int, float]:
    """
    Au lieu de se baser uniquement sur une distance approximative, cet algorithme
    presse les touches jusqu'à ce que le joueur heurte le mur/la culture (stabilisation X/Z).
    C'est la méthode de speedrun la plus fiable pour coller la hitbox des plantes.
    """
    minescript.player_inventory_select_slot(HOE_SLOT)
    minescript.player_press_attack(True)
    
    i = start_index

    # --- CALCUL VECTORIEL DES TOUCHES (basé sur le Yaw) ---
    rad = math.radians(yaw)
    fx, fz = -math.sin(rad), math.cos(rad)              # Vecteur Avant (W)
    rad_r = math.radians(yaw + 90)                      
    rx, rz = -math.sin(rad_r), math.cos(rad_r)          # Vecteur Droite (D)

    try:
        while not stop_event.is_set():
            if i >= len(waypoint_list):
                if infinite_loop:
                    i = 1
                else:
                    break
            
            target_wp = waypoint_list[i]
            tx, ty, tz = target_wp["x"], target_wp["y"], target_wp["z"]
            
            # Variables pour la détection de collision avec le mur
            stuck_ticks = 0
            try:
                prev_p = minescript.player_position()
                prev_px, prev_pz = prev_p[0], prev_p[2]
            except:
                prev_px, prev_pz = 0, 0
                
            while not stop_event.is_set():
                if pest_spawn_event and pest_spawn_event.is_set():
                    return i, next_rod_cast_time
                
                # Vérification du timer de cooldown au beau milieu du champ
                if next_rod_cast_time > 0 and time.monotonic() >= next_rod_cast_time:
                    minescript.player_press_forward(False)
                    minescript.player_press_backward(False)
                    minescript.player_press_right(False)
                    minescript.player_press_left(False)
                    minescript.player_press_attack(False)
                    
                    use_fishing_rod()
                    next_rod_cast_time = 0.0 # Désactive l'alerte pour ce cycle
                    
                    look(yaw, pitch)
                    minescript.player_inventory_select_slot(HOE_SLOT)
                    minescript.player_press_attack(True)

                if check_and_kill_pests(yaw, pitch, stop_event):
                    look(yaw, pitch)
                    minescript.player_inventory_select_slot(HOE_SLOT)
                    minescript.player_press_attack(True)

                try:
                    p_pos = minescript.player_position()
                    px, py, pz = p_pos[0], p_pos[1], p_pos[2]
                except Exception:
                    continue
                
                dx = tx - px
                dz = tz - pz
                dist_2d = math.sqrt(dx**2 + dz**2)
                
                # --- L'IDÉE DE GÉNIE : VÉRIFICATION DE LA STABILISATION (COLLISION) ---
                # Si la position du joueur ne change plus (il a tapé la bordure de la culture)
                if abs(px - prev_px) < 0.005 and abs(pz - prev_pz) < 0.005:
                    stuck_ticks += 1
                else:
                    stuck_ticks = 0
                    
                prev_px, prev_pz = px, pz
                
                # Le waypoint est validé SI :
                # 1. On est très près de l'objectif (0.3 blocs)
                # 2. OU ALORS on est relativement proche (< 2.0 blocs) MAIS on vient de heurter le mur (stabilisé pendant 3 ticks).
                if dist_2d <= 0.6 or (dist_2d <= 2.0 and stuck_ticks >= 2):
                    break 
                
                # --- CALCUL INTELLIGENT DE LA TOUCHE ---
                # On projette le vecteur destination sur les touches pour un résultat 100% universel
                fwd_val = dx * fx + dz * fz
                right_val = dx * rx + dz * rz
                
                # Dès qu'il y a un infime décalage (0.1), le bot appuie sur la touche 
                # pour te forcer contre le mur sans hésiter.
                minescript.player_press_forward(fwd_val > 0.1)
                minescript.player_press_backward(fwd_val < -0.1)
                minescript.player_press_right(right_val > 0.1)
                minescript.player_press_left(right_val < -0.1)
                
                time.sleep(LOOP_SLEEP)
            
            # Relâchement propre avant de calculer le prochain virage
            time.sleep(0.2)
            minescript.player_press_forward(False)
            minescript.player_press_backward(False)
            minescript.player_press_right(False)
            minescript.player_press_left(False)
            
            if stop_event.is_set() or (pest_spawn_event and pest_spawn_event.is_set()):
                return i, next_rod_cast_time

            prev_wp = waypoint_list[i-1] if i > 0 else waypoint_list[0]
            if target_wp["y"] < prev_wp["y"] - 0.5:
                time.sleep(DROP_DOWN_DELAY)

            i += 1

    finally:
        minescript.player_press_attack(False)
        release_all_keys()
        if not stop_event.is_set() and not infinite_loop and not (pest_spawn_event and pest_spawn_event.is_set()):
            warp_garden()
            
    return i, next_rod_cast_time

# ─────────────────────────────────────────────────────────────────────────────
# Generic farm loop & PestFarming Supervisor
# ─────────────────────────────────────────────────────────────────────────────
def farm_generic(crop_name: str, stop_event: threading.Event) -> None:
    if crop_name not in WAYPOINTS:
        msg(f"§c[FarmAuto] No config for {crop_name}. Run setup.py first.")
        return

    _start_pos, (yaw, pitch), _waypoint_list = WAYPOINTS[crop_name]

    try:
        minescript.player_press_forward(True)
        time.sleep(0.05)
        minescript.player_press_forward(False)
        look(yaw, pitch)
        minescript.execute("/sethome")
        msg(f"§aStarting farm: §e{crop_name}")

        # --- PEST FARMING SPECIAL MODE ---
        if crop_name == "PestFarming":
            pest_spawn_event = threading.Event()
            plot_info = []
            
            chat_thread = threading.Thread(target=tail_chat_for_pests, args=(stop_event, pest_spawn_event, plot_info), daemon=True)
            chat_thread.start()

            current_wp_index = 1
            next_rod_cast_time = time.monotonic()

            while not stop_event.is_set():
                
                # 1. Avance sur le chemin en utilisant la mémoire, et check le cooldown en mouvement
                current_wp_index, next_rod_cast_time = Maps_waypoints(yaw, pitch, _waypoint_list, stop_event, infinite_loop=True, pest_spawn_event=pest_spawn_event, start_index=current_wp_index, next_rod_cast_time=next_rod_cast_time)
                
                # 2. Exécution si une pest est apparue
                if pest_spawn_event.is_set() and len(plot_info) >= 2:
                    
                    next_rod_cast_time = time.monotonic() + PEST_COOLDOWN
                    
                    target_plot = plot_info[0]
                    target_amount = plot_info[1]
                    pest_spawn_event.clear()
                    
                    msg("§a[PestFarming] EXECUTING PEST KILL SEQUENCE...")
                    
                    look(yaw, pitch)
                    minescript.execute("/sethome")
                    time.sleep(0.5)
                    
                    use_fishing_rod()
                        
                    if target_plot == PEST_PLOT_NAME:
                        msg(f"§e[PestFarming] Pests spawned in base plot {target_plot}. Teleporting...")
                        minescript.execute(f"/plotteleport {PEST_PLOT_NAME}")
                        time.sleep(1.5)
                        action_hunt_pests(stop_event, known_total=target_amount, known_plots=[target_plot], return_to_garden=False)
                    else:
                        msg(f"§e[PestFarming] Pests spawned in plot {target_plot}. Flying there...")
                        action_hunt_pests(stop_event, return_to_garden=False)
                    
                    warp_garden()
                    look(yaw, pitch)
                    
        # --- NORMAL FARMING MODE ---
        else:
            current_wp_index = 1
            while not stop_event.is_set():
                if AUTO_VERIFY_TAB:
                    _invalidate_pest_cache()
                    total, plots = get_pest_info()
                    if total != "0" and plots:
                        msg(f"§c[Auto-Hunt] {total} pest(s) detected! Launching cleaner…")
                        action_hunt_pests(stop_event, known_total=total, known_plots=plots, return_to_garden=True)
                        if stop_event.is_set():
                            break
                        look(yaw, pitch)
                        minescript.player_inventory_select_slot(HOE_SLOT)
                        time.sleep(0.5)
                        
                        current_wp_index = 1

                if stop_event.is_set():
                    break

                current_wp_index, _ = Maps_waypoints(yaw, pitch, _waypoint_list, stop_event, start_index=current_wp_index)
                if current_wp_index >= len(_waypoint_list):
                    break

    finally:
        release_all_keys()

# ─────────────────────────────────────────────────────────────────────────────
# Waypoint detection 
# ─────────────────────────────────────────────────────────────────────────────
def get_nearest_crop() -> str | None:
    try:
        px, py, pz = minescript.player_position()
    except Exception:
        return None
    for crop, (start_pos, _, _) in WAYPOINTS.items():
        wx, wy, wz = start_pos
        if (px - wx) ** 2 + (py - wy) ** 2 + (pz - wz) ** 2 <= WAYPOINT_RADIUS_SQ:
            return crop
    return None

# ─────────────────────────────────────────────────────────────────────────────
# Key constants
# ─────────────────────────────────────────────────────────────────────────────
KEY_F7  = 296
KEY_F8  = 297
KEY_F9  = 298
KEY_F10 = 299

def main():
    if not FARMS_CFG:
        msg("§c[FarmAuto] No farms configured! Run §esetup.py §cfirst.")
        return

    configured_crops = list(WAYPOINTS.keys())

    banner = (
        f"§bFarmAuto  §7(Universal Navigation)\n"
        f"§7Configured crops: §a{', '.join(configured_crops)}\n"
        f"§7Hoe slot: §a{HOE_SLOT}  §7Vacuum slot: §a{VACUUM_SLOT}  §7Radius: §a{VACUUM_RADIUS}bl\n"
        f"§7Auto-kill on path: §a{AUTO_KILL_ON_PATH}  §7Auto-verify tab: §a{AUTO_VERIFY_TAB}\n"
        f"§eFarm: F8  §7(stand on start waypoint)\n"
        f"§ePest Info: F9   §ePest Hunter: F10\n"
        f"§cStop/Exit: F7"
    )
    msg(banner, "\n\n", "\n\n")

    stop_event  = None
    logic_thread = None

    with EventQueue() as eq:
        eq.register_key_listener()

        while True:
            event = eq.get()
            if event.type == EventType.KEY and event.action == 1:
                
                # F8: START FARM 
                if event.key == KEY_F8:
                    if logic_thread and logic_thread.is_alive():
                        msg("§c[Error] Task already running. Press F7 first.")
                    else:
                        crop_name = get_nearest_crop()
                        if crop_name:
                            stop_event   = threading.Event()
                            logic_thread = threading.Thread(
                                target=farm_generic,
                                args=(crop_name, stop_event),
                                daemon=True,
                            )
                            logic_thread.start()
                        else:
                            msg("§e[Info] Not near any configured waypoint.")

                # F7: STOP / EXIT
                elif event.key == KEY_F7:
                    if logic_thread and logic_thread.is_alive():
                        msg("§cStopping current task…")
                        stop_event.set()
                        logic_thread.join(timeout=5)
                        logic_thread = None
                        stop_event   = None
                        msg("§aTask stopped.")
                    else:
                        msg("§cExiting FarmAuto.")
                        break

                # F9: PEST INFO 
                elif event.key == KEY_F9:
                    if logic_thread and logic_thread.is_alive():
                        msg("§c[Error] Pest check ignored: bot is active.")
                    else:
                        run_pest_check()

                # F10: PEST HUNTER 
                elif event.key == KEY_F10:
                    if logic_thread and logic_thread.is_alive():
                        msg("§c[Error] Task already running. Press F7 first.")
                    else:
                        stop_event   = threading.Event()
                        logic_thread = threading.Thread(
                            target=action_hunt_pests,
                            args=(stop_event,),
                            daemon=True,
                        )
                        logic_thread.start()

if __name__ == "__main__":
    main()