<p align="center">
  <img src="../docs/pictures/tripico_logo_hardware.png" width="110" alt="TriPico Hardware Logo"/>
</p>

<h1 align="center">Hardware Build Guide</h1>
<p align="center"><strong>PCB + Front Panel + Wiring Integration</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/Design-KiCad-314CB6?style=for-the-badge&logo=kicad&logoColor=white" alt="KiCad Badge"/>
  <img src="https://img.shields.io/badge/Mechanical-Panel%20%26%20Enclosure-92400E?style=for-the-badge" alt="Mechanical Badge"/>
  <img src="https://img.shields.io/badge/Assembly-Prototype%20to%20Bench-065F46?style=for-the-badge" alt="Assembly Badge"/>
</p>

# 🏗️ Hardware Build Guide

> PCB design, front-panel enclosure, mechanical integration, and electrical bring-up.

This guide covers the complete hardware design and assembly workflow:

## Picture Insertion Block: Hardware Assembly Overview

```md
![Hardware assembly overview](../docs/pictures/hw_overview_assembly.jpg)
```

- **KiCad project** (complete schematic + PCB layout)
- **Front panel enclosure files** (SVG vector artwork + OpenSCAD 3D extrusion script)

This guide is intentionally conservative where assembly details depend on your specific choices (connectors, wiring gauge, fuse ratings, etc.).

## 📋 What Is In This Folder

## Picture Insertion Block: Repository Hardware Assets

```md
![Hardware files map](../docs/pictures/hw_repo_assets_map.jpg)
```

- kicad/
  - tripico-psu.kicad_sch: electrical schematic
  - tripico-psu.kicad_pcb: PCB layout
  - tripico-psu.kicad_pro and tripico-psu.kicad_prl: project settings

- enclosure/
  - front_panel_inkscape.svg: editable panel design
  - front_panel_polygon.svg: panel path used for extrusion
  - front_panel.scad: OpenSCAD extrusion script

## 🎯 Suggested Physical Architecture

## Picture Insertion Block: Front Panel Layout

```md
![Front panel layout](../docs/pictures/hw_front_panel_layout.jpg)
```

Based on the files and pictures, the build appears to include:

- A main PCB with one Raspberry Pi Pico and analog/power stages
- Front-panel controls and indicators:
  - Main power switch
  - Range selector for current measurement shunts
  - Push-pull channel enable switches (A/B/C)
  - Channel output terminals
  - Status LEDs and safety indication
- External supply input connector

Use the schematic and PCB net labels as the source of truth for wiring.

## 🔨 Build Workflow

### 1) PCB Fabrication And Assembly

### Picture Insertion Block: PCB Render And Assembled Board

```md
![PCB render and assembled board](../docs/pictures/hw_pcb_render_and_real_board.jpg)
```

1. Open kicad/tripico-psu.kicad_pro in KiCad.
2. Run ERC/DRC and inspect any warnings before fabrication.
3. Generate Gerbers and drill files from the PCB editor.
4. Assemble components according to the schematic and footprints.

### 2) Front Panel Fabrication

### Picture Insertion Block: Panel Fabrication

```md
![Panel fabrication process](../docs/pictures/hw_panel_fabrication_steps.jpg)
```

1. Edit enclosure/front_panel_inkscape.svg for labels/hole placement.
2. Use enclosure/front_panel_polygon.svg with OpenSCAD:

```scad
linear_extrude(height = 0.5) import("front_panel_polygon.svg");
```

3. Export for your process (laser/CNC/print) as needed.

### 3) Mechanical Integration

### Picture Insertion Block: Internal Wiring

```md
![Internal wiring and mounting](../docs/pictures/hw_internal_wiring.jpg)
```

1. Mount PCB in enclosure.
2. Mount panel hardware (switches, jacks, LEDs).
3. Route and secure wiring between panel and PCB connectors.

### 4) Electrical Bring-Up

### Picture Insertion Block: Bring-Up Checklist Bench Setup

```md
![Electrical bring up bench setup](../docs/pictures/hw_bringup_bench_setup.jpg)
```

1. Perform continuity checks before power-on.
2. Bring up with current-limited bench supply first.
3. Verify rails, relay behavior, and panel switch detection.
4. Flash firmware and test serial communication with host software.

## ✅ Wiring Checklist (To Complete)

## Picture Insertion Block: Final Wiring Diagram

```md
![Final wiring diagram](../docs/pictures/hw_final_wiring_diagram.jpg)
```

Use this section as your own integration checklist:

- External power input connector pinout: TODO
- Output terminal mapping for channels A/B/C: TODO
- Panel LED wiring and polarity: TODO
- Push-pull switch wiring reference: TODO
- Range selector switch wiring reference: TODO
- Safety relay coil and contact wiring: TODO
- Fuse/protection devices and ratings: TODO

## ⚠️ Safety Notes

- Use an inline fuse on the external supply input.
- Keep high-current traces/wires short and appropriately sized.
- Verify grounding strategy between analog sensing and power paths.
- Confirm enclosure insulation and strain relief before regular use.

## Assets For Documentation

Project image: docs/pictures/global_view.jpg

You can extend this README with BOM, exact connector references, and final wiring photos as you finalize your hardware revision.