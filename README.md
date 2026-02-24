# 🚜 FarmAuto - Universal Dynamic Farming Macro

**FarmAuto** is a highly optimized, next-gen farming macro for the Hypixel SkyBlock Garden, built using the [Minescript](https://minescript.net/) mod.

Unlike traditional macros that rely on hardcoded X/Z limits, **FarmAuto** uses a **dynamic waypoint system**. You record your path once, and the bot calculates relative angles to walk it perfectly. This means it works flawlessly with **ANY farm layout** (horizontal, vertical, diagonal, or custom shapes) for all 13 crops!

It also includes a built-in, highly optimized **3D Pest Hunter** that flies, tracks, chain-kills, and does smart corner-sweeps without lagging your game.

---

## ⚠️ Disclaimer & Status

* **Beta Phase:** This script is currently in beta. It has been heavily tested on **Minecraft 1.21.10 on Windows 11** (though it should theoretically work on Linux).
* **No Failsafes:** Please note that there are currently **NO anti-ban failsafes** (admin checks, bedrock detection, etc.). **Use this macro at your own risk!**
* **Layouts:** Tested mainly on horizontal farm layouts, but the dynamic setup system allows it to adapt to vertical or custom shapes.

---

## ✨ Key Features

* 🗺️ **Universal Navigation Engine:** Connects the dots! Record your path, and the bot calculates relative angles to walk it perfectly.
* 🖥️ **Interactive Setup GUI:** Comes with a built-in graphical user interface (`\setup`) to easily configure your settings, slots, and crops without touching the code.
* 🦟 **Optimized 3D Pest Hunter:** Caches entity and Tab list data to avoid FPS drops. Sweeps plot corners smartly if a pest is hidden by render distance limits.
* 🧹 **On-Path Pest Clearing:** Automatically vacuums pests that cross your vision cone while farming without interrupting the macro.

---

## 🛠️ Installation & Dependencies

To run FarmAuto, you must have the **Minescript** mod installed.

1. Download this repository.
2. Navigate to your Minecraft instance folder: `...\minecraft\minescript\system\exec\`
3. Place the following files inside the `exec` folder:
   * `FarmAuto.py` (The main macro)
   * `setup.py` (The configuration wizard)
   * `config_lib.py` (Dependency: handles JSON saving)
   * `lib_screen.py` (Dependency: handles the GUI windows)
   * `minescript_plus.py` (Dependency: advanced background keybinds and utilities - make sure you have v0.17.0+ if possible)

---

## ⚙️ Configuration (`setup.py`)

Before starting the macro, you need to configure your tool slots and record your farm paths.

1. Launch Minecraft and go to your Garden.
2. Type `\setup` in the chat.
3. **Step 1 (Global Variables):** Use the GUI to set your Hoe slot, Vacuum slot, Vacuum radius, and Pest Hunter toggles.
4. **Step 2 (Record Farms):** Select a crop to record. Stand at the beginning of your farm and use the following keybinds to draw the path:
   * `F8`: Record the **Start** point.
   * `F9`: Record a **Turn/Change** point (press this at the end of each row/lane).
   * `F10`: Record the **End** point (finishes the recording).
   * `F11`: Undo your last point if you made a mistake.
5. The GUI will then ask you to select the locked Camera Angle (Yaw/Pitch) for that farm.
6. Click **Save & Finish**!

---

## 🚀 How to Use (`FarmAuto.py`)

Once configured, your paths are saved in `farmauto_config.json`.

1. Type `\FarmAuto` in the chat to launch the background macro service.
2. Stand near the **Start** point of the crop you want to farm.
3. Press **`F8`** to start the bot.
4. Press **`F7`** to Stop the bot or Exit the script.
5. Press **`F10`** to manually trigger a full 3D Pest Hunt sweep of your Garden.
6. Press **`F9`** to print the current Pest status in the chat.

---

## 🤝 Call for Contributions

If anyone knows how to properly add **3D block highlighting** (rendering visual boxes on blocks using `WorldRender`) with the current Minescript version, please feel free to open a Pull Request! 

I would love to integrate 3D rendering into the `setup.py` phase to make the waypoint configuration more visual and user-friendly. Feedback and optimizations on the pathfinding math are also highly welcome.
