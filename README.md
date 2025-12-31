# VTT Toolkit (vtt_toolkit.py + vtt_toolkit_gui.py)

A lightweight toolkit to **clean / split / merge / compress** WebVTT (`.vtt`) subtitle files.
Designed for batch workflows such as: fix messy timestamps → split into 10-minute parts → (translate elsewhere) → merge back → compress into more readable sentences.

---

## What’s included

### `vtt_toolkit.py` (CLI)
Command-line tool that provides these features:

- **clean**: validate and normalize VTT timestamps; optionally fix common non-standard formats and output a `_fixed.vtt`
- **split**: split a long VTT into smaller parts (e.g., every 10 minutes)
- **merge**: merge multiple VTT part files into one VTT (supports filename patterns)
- **compress**: merge adjacent short cues into more readable subtitle lines
- **cleansplit**: one-click clean + split
  
### `vtt_toolkit_gui.py` (GUI)
A simple desktop GUI wrapper that lets you run the same operations with buttons:
- Clean + Split
- Clean
- Split
- Merge
- Compress
- Merge + Compress

> Note: The GUI calls `vtt_toolkit.py` under the hood, so both files should be available.

---

## Requirements

- Python 3.9+ (3.11 recommended)
- No external dependencies required (uses standard library only)

---

## Quick start (CLI)

Go to the folder containing `vtt_toolkit.py`:

```powershell
cd "C:\path\to\your\folder"
