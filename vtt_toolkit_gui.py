#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Simple GUI wrapper for vtt_toolkit.py (Tkinter).

Place this file in the SAME folder as vtt_toolkit.py, then run:
  python vtt_toolkit_gui.py

If vtt_toolkit.py is elsewhere, the GUI will let you browse to it.
"""

import sys
import os
import threading
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "VTT Toolkit GUI (clean / split / merge / compress)"


def _quote(arg: str) -> str:
    if any(c in arg for c in [' ', '\t', '"']):
        return f'"{arg}"'
    return arg


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("900x650")
        self.minsize(860, 600)

        self.tool_path = tk.StringVar(value=str(self._default_tool_path()))
        self.python_path = tk.StringVar(value=sys.executable)

        self._build_ui()

    def _default_tool_path(self) -> Path:
        here = Path(__file__).resolve().parent
        return here / "vtt_toolkit.py"

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="Python:").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.python_path, width=70).grid(row=0, column=1, sticky="we", padx=6)
        ttk.Button(top, text="Browse...", command=self._browse_python).grid(row=0, column=2)

        ttk.Label(top, text="vtt_toolkit.py:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(top, textvariable=self.tool_path, width=70).grid(row=1, column=1, sticky="we", padx=6, pady=(8, 0))
        ttk.Button(top, text="Browse...", command=self._browse_tool).grid(row=1, column=2, pady=(8, 0))

        top.columnconfigure(1, weight=1)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._tab_cleansplit(nb)
        self._tab_clean(nb)
        self._tab_split(nb)
        self._tab_mergecompress(nb)
        self._tab_merge(nb)
        self._tab_compress(nb)
        self._tab_cleancompresssplit(nb)

        log_frame = ttk.Frame(self)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        ttk.Label(log_frame, text="Log:").pack(anchor="w")
        self.log = tk.Text(log_frame, height=12, wrap="word")
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btns, text="Clear Log", command=self._clear_log).pack(side="left")
        ttk.Button(btns, text="Open Working Folder", command=self._open_cwd).pack(side="left", padx=8)

        self._log_line("Tip: If you used relative paths like out_dir=parts, the output folder is created under your CURRENT working directory.")
        self._log_line(f"Current working directory: {Path.cwd()}")

    # ----- Tabs -----
    def _tab_clean(self, nb):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Clean (check/fix)")

        self.clean_in = tk.StringVar()
        self.clean_fix = tk.BooleanVar(value=True)

        ttk.Label(tab, text="Input VTT:").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(tab, textvariable=self.clean_in, width=80).grid(row=0, column=1, sticky="we", padx=8, pady=8)
        ttk.Button(tab, text="Browse...", command=lambda: self._pick_file(self.clean_in)).grid(row=0, column=2, padx=8, pady=8)

        ttk.Checkbutton(tab, text="Fix/normalize timestamps (writes *_fixed.vtt)", variable=self.clean_fix).grid(row=1, column=1, sticky="w", padx=8, pady=6)

        ttk.Button(tab, text="Run Clean", command=self._run_clean).grid(row=2, column=1, sticky="w", padx=8, pady=10)

        tab.columnconfigure(1, weight=1)

    def _tab_split(self, nb):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Split")

        self.split_in = tk.StringVar()
        self.split_outdir = tk.StringVar()
        self.split_minutes = tk.IntVar(value=10)
        self.split_rebase = tk.BooleanVar(value=False)

        ttk.Label(tab, text="Input VTT:").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(tab, textvariable=self.split_in, width=80).grid(row=0, column=1, sticky="we", padx=8, pady=8)
        ttk.Button(tab, text="Browse...", command=lambda: self._pick_file(self.split_in)).grid(row=0, column=2, padx=8, pady=8)

        ttk.Label(tab, text="Output folder (out_dir):").grid(row=1, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(tab, textvariable=self.split_outdir, width=80).grid(row=1, column=1, sticky="we", padx=8, pady=8)
        ttk.Button(tab, text="Browse...", command=lambda: self._pick_dir(self.split_outdir)).grid(row=1, column=2, padx=8, pady=8)

        sub = ttk.Frame(tab)
        sub.grid(row=2, column=1, sticky="w", padx=8, pady=6)
        ttk.Label(sub, text="Minutes per part:").pack(side="left")
        ttk.Spinbox(sub, from_=1, to=240, textvariable=self.split_minutes, width=6).pack(side="left", padx=8)
        ttk.Checkbutton(sub, text="Rebase each part to start at 00:00", variable=self.split_rebase).pack(side="left", padx=8)

        ttk.Button(tab, text="Run Split", command=self._run_split).grid(row=3, column=1, sticky="w", padx=8, pady=10)

        tab.columnconfigure(1, weight=1)

    def _tab_cleansplit(self, nb):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Clean + Split (one click)")

        self.cs_in = tk.StringVar()
        self.cs_outdir = tk.StringVar()
        self.cs_minutes = tk.IntVar(value=10)
        self.cs_rebase = tk.BooleanVar(value=False)

        ttk.Label(tab, text="Input VTT:").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(tab, textvariable=self.cs_in, width=80).grid(row=0, column=1, sticky="we", padx=8, pady=8)
        ttk.Button(tab, text="Browse...", command=lambda: self._pick_file(self.cs_in)).grid(row=0, column=2, padx=8, pady=8)

        ttk.Label(tab, text="Output folder (out_dir):").grid(row=1, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(tab, textvariable=self.cs_outdir, width=80).grid(row=1, column=1, sticky="we", padx=8, pady=8)
        ttk.Button(tab, text="Browse...", command=lambda: self._pick_dir(self.cs_outdir)).grid(row=1, column=2, padx=8, pady=8)

        sub = ttk.Frame(tab)
        sub.grid(row=2, column=1, sticky="w", padx=8, pady=6)
        ttk.Label(sub, text="Minutes per part:").pack(side="left")
        ttk.Spinbox(sub, from_=1, to=240, textvariable=self.cs_minutes, width=6).pack(side="left", padx=8)
        ttk.Checkbutton(sub, text="Rebase each part to start at 00:00", variable=self.cs_rebase).pack(side="left", padx=8)

        ttk.Button(tab, text="Run Clean + Split", command=self._run_cleansplit).grid(row=3, column=1, sticky="w", padx=8, pady=10)

        tab.columnconfigure(1, weight=1)

    def _tab_merge(self, nb):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Merge")

        self.merge_partsdir = tk.StringVar()
        self.merge_pattern = tk.StringVar(value="*.vtt")
        self.merge_out = tk.StringVar()

        ttk.Label(tab, text="Parts folder (parts_dir):").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(tab, textvariable=self.merge_partsdir, width=80).grid(row=0, column=1, sticky="we", padx=8, pady=8)
        ttk.Button(tab, text="Browse...", command=lambda: self._pick_dir(self.merge_partsdir)).grid(row=0, column=2, padx=8, pady=8)

        ttk.Label(tab, text="Filename pattern:").grid(row=1, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(tab, textvariable=self.merge_pattern, width=40).grid(row=1, column=1, sticky="w", padx=8, pady=8)
        ttk.Label(tab, text='(e.g., "*english.vtt" or "*.vtt")').grid(row=1, column=1, sticky="e", padx=8, pady=8)

        ttk.Label(tab, text="Output merged VTT:").grid(row=2, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(tab, textvariable=self.merge_out, width=80).grid(row=2, column=1, sticky="we", padx=8, pady=8)
        ttk.Button(tab, text="Save as...", command=lambda: self._save_file(self.merge_out)).grid(row=2, column=2, padx=8, pady=8)

        ttk.Button(tab, text="Run Merge", command=self._run_merge).grid(row=3, column=1, sticky="w", padx=8, pady=10)

        tab.columnconfigure(1, weight=1)

    def _tab_compress(self, nb):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Compress")

        self.comp_in = tk.StringVar()
        self.comp_out = tk.StringVar()
        self.comp_gap = tk.IntVar(value=500)
        self.comp_maxchars = tk.IntVar(value=130)

        ttk.Label(tab, text="Input VTT:").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(tab, textvariable=self.comp_in, width=80).grid(row=0, column=1, sticky="we", padx=8, pady=8)
        ttk.Button(tab, text="Browse...", command=lambda: self._pick_file(self.comp_in)).grid(row=0, column=2, padx=8, pady=8)

        ttk.Label(tab, text="Output compressed VTT:").grid(row=1, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(tab, textvariable=self.comp_out, width=80).grid(row=1, column=1, sticky="we", padx=8, pady=8)
        ttk.Button(tab, text="Save as...", command=lambda: self._save_file(self.comp_out)).grid(row=1, column=2, padx=8, pady=8)

        sub = ttk.Frame(tab)
        sub.grid(row=2, column=1, sticky="w", padx=8, pady=6)
        ttk.Label(sub, text="gap_ms:").pack(side="left")
        ttk.Spinbox(sub, from_=0, to=10000, textvariable=self.comp_gap, width=7).pack(side="left", padx=6)
        ttk.Label(sub, text="max_chars:").pack(side="left", padx=(10, 0))
        ttk.Spinbox(sub, from_=20, to=500, textvariable=self.comp_maxchars, width=7).pack(side="left", padx=6)

        ttk.Button(tab, text="Run Compress", command=self._run_compress).grid(row=3, column=1, sticky="w", padx=8, pady=10)

        tab.columnconfigure(1, weight=1)

    def _tab_mergecompress(self, nb):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Merge + Compress")

        self.mc_partsdir = tk.StringVar()
        self.mc_pattern = tk.StringVar(value="*english.vtt")
        self.mc_out = tk.StringVar()
        self.mc_gap = tk.IntVar(value=500)
        self.mc_maxchars = tk.IntVar(value=130)

        ttk.Label(tab, text="Parts folder (parts_dir):").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(tab, textvariable=self.mc_partsdir, width=80).grid(row=0, column=1, sticky="we", padx=8, pady=8)
        ttk.Button(tab, text="Browse...", command=lambda: self._pick_dir(self.mc_partsdir)).grid(row=0, column=2, padx=8, pady=8)

        ttk.Label(tab, text="Filename pattern:").grid(row=1, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(tab, textvariable=self.mc_pattern, width=40).grid(row=1, column=1, sticky="w", padx=8, pady=8)
        ttk.Label(tab, text='(e.g., "*english.vtt" or "*english*.vtt")').grid(row=1, column=1, sticky="e", padx=8, pady=8)

        ttk.Label(tab, text="Output merged+compressed VTT:").grid(row=2, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(tab, textvariable=self.mc_out, width=80).grid(row=2, column=1, sticky="we", padx=8, pady=8)
        ttk.Button(tab, text="Save as...", command=lambda: self._save_file(self.mc_out)).grid(row=2, column=2, padx=8, pady=8)

        sub = ttk.Frame(tab)
        sub.grid(row=3, column=1, sticky="w", padx=8, pady=6)
        ttk.Label(sub, text="gap_ms:").pack(side="left")
        ttk.Spinbox(sub, from_=0, to=10000, textvariable=self.mc_gap, width=7).pack(side="left", padx=6)
        ttk.Label(sub, text="max_chars:").pack(side="left", padx=(10, 0))
        ttk.Spinbox(sub, from_=20, to=500, textvariable=self.mc_maxchars, width=7).pack(side="left", padx=6)

        ttk.Button(tab, text="Run Merge + Compress", command=self._run_mergecompress).grid(row=4, column=1, sticky="w", padx=8, pady=10)

        tab.columnconfigure(1, weight=1)

    def _tab_cleancompresssplit(self, nb):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Clean + Compress + Split")

        self.ccs_in = tk.StringVar()
        self.ccs_outdir = tk.StringVar()
        self.ccs_minutes = tk.IntVar(value=10)
        self.ccs_gap = tk.IntVar(value=500)
        self.ccs_maxchars = tk.IntVar(value=130)
        self.ccs_rebase = tk.BooleanVar(value=False)

        ttk.Label(tab, text="Input VTT:").grid(row=0, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(tab, textvariable=self.ccs_in, width=80).grid(row=0, column=1, sticky="we", padx=8, pady=8)
        ttk.Button(tab, text="Browse...", command=lambda: self._pick_file(self.ccs_in)).grid(row=0, column=2, padx=8, pady=8)

        ttk.Label(tab, text="Output folder (out_dir):").grid(row=1, column=0, sticky="w", padx=8, pady=8)
        ttk.Entry(tab, textvariable=self.ccs_outdir, width=80).grid(row=1, column=1, sticky="we", padx=8, pady=8)
        ttk.Button(tab, text="Browse...", command=lambda: self._pick_dir(self.ccs_outdir)).grid(row=1, column=2, padx=8, pady=8)

        sub1 = ttk.Frame(tab)
        sub1.grid(row=2, column=1, sticky="w", padx=8, pady=6)
        ttk.Label(sub1, text="gap_ms:").pack(side="left")
        ttk.Spinbox(sub1, from_=0, to=10000, textvariable=self.ccs_gap, width=7).pack(side="left", padx=6)
        ttk.Label(sub1, text="max_chars:").pack(side="left", padx=(10, 0))
        ttk.Spinbox(sub1, from_=20, to=500, textvariable=self.ccs_maxchars, width=7).pack(side="left", padx=6)

        sub2 = ttk.Frame(tab)
        sub2.grid(row=3, column=1, sticky="w", padx=8, pady=6)
        ttk.Label(sub2, text="Minutes per part:").pack(side="left")
        ttk.Spinbox(sub2, from_=1, to=240, textvariable=self.ccs_minutes, width=6).pack(side="left", padx=8)
        ttk.Checkbutton(sub2, text="Rebase each part to start at 00:00", variable=self.ccs_rebase).pack(side="left", padx=8)

        ttk.Button(tab, text="Run Clean + Compress + Split", command=self._run_cleancompresssplit).grid(row=4, column=1, sticky="w", padx=8, pady=10)

        tab.columnconfigure(1, weight=1)

    # ----- Browse helpers -----
    def _browse_python(self):
        fp = filedialog.askopenfilename(title="Select python executable", filetypes=[("Python", "python*.exe;python*"), ("All files", "*.*")])
        if fp:
            self.python_path.set(fp)

    def _browse_tool(self):
        fp = filedialog.askopenfilename(title="Select vtt_toolkit.py", filetypes=[("Python", "*.py"), ("All files", "*.*")])
        if fp:
            self.tool_path.set(fp)

    def _pick_file(self, var):
        fp = filedialog.askopenfilename(title="Select VTT file", filetypes=[("WebVTT", "*.vtt"), ("All files", "*.*")])
        if fp:
            var.set(fp)

    def _save_file(self, var):
        fp = filedialog.asksaveasfilename(title="Save output", defaultextension=".vtt", filetypes=[("WebVTT", "*.vtt"), ("All files", "*.*")])
        if fp:
            var.set(fp)

    def _pick_dir(self, var):
        dp = filedialog.askdirectory(title="Select folder")
        if dp:
            var.set(dp)

    # ----- Log helpers -----
    def _log_line(self, s: str):
        self.log.configure(state="normal")
        self.log.insert("end", s + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _open_cwd(self):
        p = Path.cwd()
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(p))  # type: ignore
            elif sys.platform == "darwin":
                subprocess.run(["open", str(p)], check=False)
            else:
                subprocess.run(["xdg-open", str(p)], check=False)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ----- Runner -----
    def _validate_tool(self) -> Path:
        tool = Path(self.tool_path.get()).expanduser()
        if not tool.exists():
            raise FileNotFoundError(f"vtt_toolkit.py not found: {tool}")
        return tool

    def _run_async(self, args_list):
        def worker():
            try:
                py = (self.python_path.get().strip() or sys.executable)
                tool = str(self._validate_tool())
                cmd = [py, tool] + args_list
                self._log_line("\n$ " + " ".join(_quote(x) for x in cmd))
                p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path.cwd()))
                if p.stdout:
                    self._log_line(p.stdout.rstrip())
                if p.stderr:
                    self._log_line(p.stderr.rstrip())
                self._log_line("[Done]" if p.returncode == 0 else f"[Exit code: {p.returncode}]")
            except Exception as e:
                self._log_line(f"[Error] {e}")
        threading.Thread(target=worker, daemon=True).start()

    # ----- Actions -----
    def _run_clean(self):
        in_file = self.clean_in.get().strip()
        if not in_file:
            messagebox.showwarning("Missing", "Select an input VTT.")
            return
        args = ["clean", "--in", in_file]
        if self.clean_fix.get():
            args.append("--fix")
        self._run_async(args)

    def _run_split(self):
        in_file = self.split_in.get().strip()
        out_dir = self.split_outdir.get().strip()
        if not in_file or not out_dir:
            messagebox.showwarning("Missing", "Select input VTT and output folder.")
            return
        args = ["split", "--in", in_file, "--out_dir", out_dir, "--minutes", str(self.split_minutes.get())]
        if self.split_rebase.get():
            args.append("--rebase")
        self._run_async(args)

    def _run_cleansplit(self):
        in_file = self.cs_in.get().strip()
        out_dir = self.cs_outdir.get().strip()
        if not in_file or not out_dir:
            messagebox.showwarning("Missing", "Select input VTT and output folder.")
            return
        args = ["cleansplit", "--in", in_file, "--out_dir", out_dir, "--minutes", str(self.cs_minutes.get())]
        if self.cs_rebase.get():
            args.append("--rebase")
        self._run_async(args)

    def _run_merge(self):
        parts_dir = self.merge_partsdir.get().strip()
        pattern = self.merge_pattern.get().strip() or "*.vtt"
        out_file = self.merge_out.get().strip()
        if not parts_dir or not out_file:
            messagebox.showwarning("Missing", "Select parts_dir and output file.")
            return
        args = ["merge", "--parts_dir", parts_dir, "--pattern", pattern, "--out", out_file]
        self._run_async(args)

    def _run_compress(self):
        in_file = self.comp_in.get().strip()
        out_file = self.comp_out.get().strip()
        if not in_file or not out_file:
            messagebox.showwarning("Missing", "Select input and output files.")
            return
        args = ["compress", "--in", in_file, "--out", out_file, "--gap_ms", str(self.comp_gap.get()), "--max_chars", str(self.comp_maxchars.get())]
        self._run_async(args)

    def _run_mergecompress(self):
        parts_dir = self.mc_partsdir.get().strip()
        pattern = self.mc_pattern.get().strip() or "*english.vtt"
        out_file = self.mc_out.get().strip()
        if not parts_dir or not out_file:
            messagebox.showwarning("Missing", "Select parts_dir and output file.")
            return
        args = ["mergecompress", "--parts_dir", parts_dir, "--pattern", pattern, "--out", out_file,
                "--gap_ms", str(self.mc_gap.get()), "--max_chars", str(self.mc_maxchars.get())]
        self._run_async(args)

    def _run_cleancompresssplit(self):
        in_file = self.ccs_in.get().strip()
        out_dir = self.ccs_outdir.get().strip()
        if not in_file or not out_dir:
           messagebox.showwarning("Missing", "Select input VTT and output folder.")
           return
        args = ["cleancompresssplit", "--in", in_file, "--out_dir", out_dir,
                "--minutes", str(self.ccs_minutes.get()),
                "--gap_ms", str(self.ccs_gap.get()),
                "--max_chars", str(self.ccs_maxchars.get())]
        if self.ccs_rebase.get():
            args.append("--rebase")
        self._run_async(args)

def main():
    App().mainloop()


if __name__ == "__main__":
    main()
