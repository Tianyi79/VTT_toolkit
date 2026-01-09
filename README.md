# VTT Toolkit (vtt_toolkit.py + vtt_toolkit_gui.py)

A lightweight toolkit to **clean / split / merge / compress/ wrap(split cues)** WebVTT (`.vtt`) subtitle files.
Designed for batch workflows such as: fix messy timestamps → split into 10-minute parts → (translate elsewhere) → merge back → compress into more readable sentences.

---

## What’s included

### `vtt_toolkit.py` (CLI)
Command-line tool that provides these features:

- **clean**: validate and normalize VTT timestamps; optionally fix common non-standard formats and output a `_fixed.vtt`
- **split**: split a long VTT into smaller parts (e.g., every 10 minutes)
- **merge**: merge multiple VTT part files into one VTT (supports filename patterns)
- **compress**: merge adjacent short cues into more readable subtitle lines
- **Merge + Compress + split**: one-click clean + split
- **wrap**: one click to split long cues to customized length
  
### `vtt_toolkit_gui.py` (GUI)
A simple desktop GUI wrapper that lets you run the same operations with buttons:
- Clean
- Split
- Merge
- Compress
- Merge + Compress + split
- wrap(split cues)

> Note: The GUI calls `vtt_toolkit.py` under the hood, so both files should be available.

---

## Requirements

- Python 3.9+ (3.11 recommended)
- No external dependencies required (uses standard library only)

---

## Quick start (CLI)

1. Go to the folder containing `vtt_toolkit.py`:

```powershell
cd "C:\path\to\your\folder"
```
Examples (Windows PowerShell):
```
  python vtt_toolkit.py clean --in "input.vtt" --fix
```
```
  python vtt_toolkit.py split --in "input_fixed.vtt" --out_dir "parts" --minutes 10
```
```
  python vtt_toolkit.py merge --parts_dir "parts" --pattern "*english.vtt" --out "merged_english.vtt"
```
```
  python vtt_toolkit.py compress --in "merged_english.vtt" --out "merged_english_compressed.vtt"
```
```
  python vtt_toolkit.py wrap --in "input.vtt" --out "output.vtt" --max_chars 130
```
```
  python vtt_toolkit.py cleansplit --in "input.vtt" --out_dir "parts" --minutes 10
```
```
  python vtt_toolkit.py mergecompress --parts_dir "parts" --pattern "*english.vtt" --out "merged_english_compressed.vtt"
```

2. Directly run the `vtt_toolkit_gui.py`:

```powershell
python vtt_toolkit_gui.py


