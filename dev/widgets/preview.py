#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Grating Sweep Normalizer & Plotter
==================================

What it does
------------
- Reads spectra from:
  - multiple separate *grating* folders (one folder per grating)
  - 1 *light reference* folder (angle-swept, one file per angle)
  - 1 *dark reference* folder (single file)
- Normalizes each grating spectrum by angle using:
      normalized = (sample - dark) / (light_at_same_angle - dark)
- Interpolates references to match each sample's wavelength grid if needed.
- Generates **19 plots** (angles 45°..135° with 5° steps). Each plot contains **4 curves**
  (one per grating), saved as PNGs and collected into a single multipage PDF.

Expected folder layout
----------------------
base_dir/
  Grating_A/
    ... files for angles (e.g., Sweep_0_45deg__VIS__*.txt, Sweep_1_50deg__VIS__*.txt, ...)
  Grating_B/
    ...
  Grating_C/
    ...
  Grating_D/
    ...
  Light_Reference/
    ... angle-swept files (one per angle): e.g., Sweep_0_45deg__VIS__*.txt
  Dark_Reference/
    ... single file: e.g., Spectrum_0_VIS__*.txt

Filename assumptions
--------------------
- Each spectrum is a plain text file with a header line that includes exactly:
      >>>>>Begin Spectral Data<<<<<
  followed by CSV rows:
      Wavelength [nm], Intensity [counts]
- Angle is discoverable from a filename substring like "45deg" or "45deg__".
  (We extract the leading integer.)
- If multiple files exist for the same angle, we will choose the most recently
  modified file unless --pick-first is used.


Notes
-----
- If a light reference for a particular angle is missing, the script can optionally
  use the **nearest available angle** with --allow-nearest-ref.
- Any missing grating file at a given angle is skipped (with a warning). The figure
  is still produced with whatever curves are available.
- Normalization denominator values <= 0 are masked to avoid division issues.



Grating Sweep Normalizer & Plotter (v2)
--------------------------------------
Changes vs v1:
- Plot y-axis as Reflectance (%) = 100 * (sample - dark) / (light - dark)
- Filter wavelengths below a cutoff (default 450 nm) with --min-wavelength
- Slightly thicker lines and small markers for readability
"""


import argparse
import re
import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import os
import subprocess

# Make default line width thinner (half of previous 2.0 => 1.0)
matplotlib.rcParams['lines.linewidth'] = 1.0

ANGLE_RE = re.compile(r'(\d+)\s*deg', re.IGNORECASE)
BEGIN_MARK = ">>>>>Begin Spectral Data<<<<<"

def extract_angle_deg(path: Path) -> Optional[int]:
    m = ANGLE_RE.search(path.name)
    return int(m.group(1)) if m else None

def read_spectrum_txt(path: Path) -> pd.DataFrame:
    wl, it = [], []
    in_data = False
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not in_data:
                if line == BEGIN_MARK:
                    in_data = True
                continue
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2:
                continue
            try:
                w = float(parts[0]); v = float(parts[1])
            except Exception:
                continue
            wl.append(w); it.append(v)
    if not wl:
        raise ValueError(f"No spectral data parsed from {path}")
    df = pd.DataFrame({"wavelength_nm": np.array(wl, dtype=float),
                       "intensity": np.array(it, dtype=float)})
    return df.sort_values("wavelength_nm").reset_index(drop=True)

def choose_latest(paths: List[Path]) -> Optional[Path]:
    return max(paths, key=lambda p: p.stat().st_mtime) if paths else None

def collect_angle_files(folder: Path) -> Dict[int, Path]:
    mapping: Dict[int, Path] = {}
    tmp: Dict[int, List[Path]] = {}
    for p in folder.iterdir():
        if not p.is_file():
            continue
        ang = extract_angle_deg(p)
        if ang is not None:
            tmp.setdefault(ang, []).append(p)
    for ang, lst in tmp.items():
        mapping[ang] = choose_latest(lst)
    return mapping

def interpolate_to(target_wavelengths: np.ndarray, ref_df: pd.DataFrame) -> np.ndarray:
    x = ref_df["wavelength_nm"].to_numpy()
    y = ref_df["intensity"].to_numpy()
    return np.interp(target_wavelengths, x, y, left=y[0], right=y[-1])

def normalize_percent(sample: pd.DataFrame, dark: pd.DataFrame, light: pd.DataFrame,
                      eps: float = 1e-12) -> pd.DataFrame:
    wl = sample["wavelength_nm"].to_numpy()
    s = sample["intensity"].to_numpy()
    d = interpolate_to(wl, dark)
    l = interpolate_to(wl, light)
    denom = (l - d)
    refl = np.where(denom > eps, (s - d) / denom * 100.0, np.nan)
    return pd.DataFrame({"wavelength_nm": wl, "reflectance_pct": refl})

def nearest_angle(available: List[int], desired: int) -> Optional[int]:
    if not available:
        return None
    return min(available, key=lambda a: abs(a - desired))

def main():
    ap = argparse.ArgumentParser(description="Normalize grating spectra to reflectance (%) and plot per angle.")
    ap.add_argument("--base", required=True)
    ap.add_argument("--gratings", nargs="+", required=True)
    ap.add_argument("--light-ref", required=True)
    ap.add_argument("--dark-ref", required=True)
    ap.add_argument("--out", default="plots")
    ap.add_argument("--angles", nargs=3, type=int, metavar=("START","STOP","STEP"),
                    default=[45, 135, 5])
    ap.add_argument("--title-prefix", default="Grating Sweep — Reflectance")
    ap.add_argument("--pick-first", action="store_true")
    ap.add_argument("--allow-nearest-ref", action="store_true")
    ap.add_argument("--save-csv", action="store_true")
    ap.add_argument("--min-wavelength", type=float, default=450.0,
                    help="Discard data below this wavelength (nm). Use 0 to disable. Default: 450.")
    ap.add_argument("--max-wavelength", type=float, default=900.0,
                    help="Discard data above this wavelength (nm). Use 0 to disable. Default: 900.")
    ap.add_argument("--ymin", type=float, default=None, help="Y-axis min (percent).")
    ap.add_argument("--ymax", type=float, default=None, help="Y-axis max (percent).")
    args = ap.parse_args()

    base = Path(args.base).expanduser().resolve()
    out_dir = (base / args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    a0, a1, astep = args.angles
    if astep <= 0:
        ap.error("--angles STEP must be positive")
    angles = list(range(a0, a1 + 1, astep))

    light_dir = (base / args.light_ref)
    if not light_dir.is_dir():
        ap.error(f"Light reference folder not found: {light_dir}")
    light_map = collect_angle_files(light_dir)
    if not light_map:
        ap.error(f"No light reference files with angle found in {light_dir}")

    dark_dir = (base / args.dark_ref)
    if not dark_dir.is_dir():
        ap.error(f"Dark reference folder not found: {dark_dir}")
    dark_files = [p for p in dark_dir.iterdir() if p.is_file()]
    if not dark_files:
        ap.error(f"No dark reference files found in {dark_dir}")
    dark_path = dark_files[0] if args.pick_first else choose_latest(dark_files)
    dark_df = read_spectrum_txt(dark_path)

    grating_paths: List[Tuple[str, Dict[int, Path]]] = []
    for gname in args.gratings:
        gdir = (base / gname)
        if not gdir.is_dir():
            ap.error(f"Grating folder not found: {gdir}")
        amap = collect_angle_files(gdir)
        grating_paths.append((gname, amap))

    pdf_path = out_dir / "grating_sweep_reflectance_plots.pdf"
    pdf = PdfPages(pdf_path)

    for ang in angles:
        fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
        ax.set_title(f"{args.title_prefix} — {ang}°")
        ax.set_xlabel("Wavelength (nm)")
        ax.set_ylabel("Reflectance (%)")

        lpath = light_map.get(ang, None)
        used_ang = ang
        if lpath is None and args.allow_nearest_ref:
            near = nearest_angle(list(light_map.keys()), ang)
            if near is not None:
                lpath = light_map.get(near)
                used_ang = near
        if lpath is None:
            print(f"[WARN] Missing light ref at {ang}°, skipping figure.", file=sys.stderr)
            plt.close(fig)
            continue
        light_df = read_spectrum_txt(lpath)

        plotted_any = False
        for gname, amap in grating_paths:
            spath = amap.get(ang, None)
            if spath is None:
                print(f"[WARN] Missing {gname} sample at {ang}° — skipped.", file=sys.stderr)
                continue
            sample_df = read_spectrum_txt(spath)
            norm_df = normalize_percent(sample_df, dark_df, light_df)

            # wavelength filter
            if args.min_wavelength > 0:
                norm_df = norm_df[norm_df["wavelength_nm"] >= args.min_wavelength]
            if args.max_wavelength > 0:
                norm_df = norm_df[norm_df["wavelength_nm"] <= args.max_wavelength]
            norm_df = norm_df.reset_index(drop=True)
            if norm_df.empty:
                print(f"[WARN] {gname} @ {ang}° empty after wavelength filter.", file=sys.stderr)
                continue

            if args.save_csv:
                csv_path = out_dir / f"{gname}_{ang}deg_reflectance.csv"
                norm_df.to_csv(csv_path, index=False)

            ax.plot(norm_df["wavelength_nm"].to_numpy(),
                    norm_df["reflectance_pct"].to_numpy(),
                    label=gname, linewidth=1.0)
            plotted_any = True

        if not plotted_any:
            plt.close(fig)
            continue

        if args.ymin is not None or args.ymax is not None:
            ax.set_ylim(args.ymin, args.ymax)

        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        png_path = out_dir / f"angle_{ang:03d}deg_reflectance.png"
        fig.savefig(png_path, bbox_inches="tight")
        pdf.savefig(fig)
        plt.close(fig)

    pdf.close()

    manifest = {
        "base": str(base),
        "gratings": args.gratings,
        "light_ref": str(light_dir),
        "dark_ref": str(dark_path),
        "angles": angles,
        "output_dir": str(out_dir),
        "pdf": str(pdf_path),
        "min_wavelength_nm": args.min_wavelength,
        "max_wavelength_nm": args.max_wavelength,
        "notes": "Reflectance (%) = 100 * (sample - dark) / (light_at_same_angle - dark)"
    }
    with (out_dir / "manifest_reflectance.json").open("w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2)

    print(f"[OK] Wrote plots to: {out_dir}")
    print(f"[OK] Combined PDF: {pdf_path}")
    print(f"[OK] Manifest: {out_dir / 'manifest_reflectance.json'}")

def generate_preview_from_sweep(root_dir, out_subdir="preview_plots", min_wavelength=450.0, max_wavelength=900.0):
    """
    Adapted preview generator for the project's SweepRoutine layout.

    Expects:
      root_dir/
        Sweep_1/ (one folder per sample sweep)
          Spectrometer-VIS/  (angle files)
        Sweep_2/
          Spectrometer-VIS/
        ...
        Light_Ref1/
          Spectrometer-VIS/  (angle files)
        Dark_References/
          VIS/               (one or more dark files)

    Only the first Light_Ref* folder and the first dark file are used.
    Outputs PNGs + a combined PDF into: root_dir / out_subdir
    """
    base = Path(root_dir).expanduser().resolve()
    if not base.exists() or not base.is_dir():
        print(f"[preview] sweep root not found: {base}", file=sys.stderr)
        return None

    # find sample sweep folders (Sweep_*)
    sweep_dirs = sorted([d for d in base.iterdir() if d.is_dir() and d.name.lower().startswith("sweep_")])

    # find light ref folders (accept both "Light_Ref*" and "LightRef*" variants, case-insensitive)
    import re
    light_pattern = re.compile(r'^light[_]?ref', re.IGNORECASE)
    light_dirs = sorted([d for d in base.iterdir() if d.is_dir() and light_pattern.match(d.name)])

    # find dark reference parent folder (contains 'dark')
    dark_parents = sorted([d for d in base.iterdir() if d.is_dir() and "dark" in d.name.lower()])

    if not sweep_dirs:
        print(f"[preview] No Sweep_* folders found under {base}", file=sys.stderr)
        return None
    if not light_dirs:
        print(f"[preview] No Light_Ref* folders found under {base}", file=sys.stderr)
        return None
    if not dark_parents:
        print(f"[preview] No Dark_References folder found under {base}", file=sys.stderr)
        return None

    # Prefer Spectrometer-VIS subfolder where present
    def find_spec_subdir(parent: Path) -> Optional[Path]:
        # try known name then fallback to first directory containing "spectrometer" or "vis"
        candidate = parent / "Spectrometer-VIS"
        if candidate.exists() and candidate.is_dir():
            return candidate
        for d in parent.iterdir():
            if d.is_dir() and ("spectrometer" in d.name.lower() or "vis" in d.name.lower()):
                return d
        # fallback: first directory
        for d in parent.iterdir():
            if d.is_dir():
                return d
        return None

    # light reference mapping (angle -> path)
    light_parent = light_dirs[0]
    light_spec = find_spec_subdir(light_parent)
    if not light_spec:
        print(f"[preview] No spectrometer subfolder inside light ref {light_parent}", file=sys.stderr)
        return None
    light_map = collect_angle_files(light_spec)
    if not light_map:
        print(f"[preview] No angle-tagged light reference files found in {light_spec}", file=sys.stderr)
        return None

    # dark file (choose latest file under dark_parents[0] or its spec subdir)
    dark_parent = dark_parents[0]
    dark_spec = find_spec_subdir(dark_parent) or dark_parent
    dark_files = [p for p in dark_spec.iterdir() if p.is_file()]
    if not dark_files:
        print(f"[preview] No dark files found under {dark_spec}", file=sys.stderr)
        return None
    dark_path = choose_latest(dark_files)
    dark_df = read_spectrum_txt(dark_path)

    # for each sweep X, collect its Spectrometer-VIS mapping
    grating_paths: List[Tuple[str, Dict[int, Path]]] = []
    for sd in sweep_dirs:
        spec = find_spec_subdir(sd)
        if not spec:
            # skip if no data
            continue
        amap = collect_angle_files(spec)
        grating_paths.append((sd.name, amap))

    if not grating_paths:
        print(f"[preview] No sample sweep spectrometer data found in sweeps under {base}", file=sys.stderr)
        return None

    # prepare output
    out_dir = (base / out_subdir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "sweep_preview_reflectance_plots.pdf"
    pdf = PdfPages(pdf_path)

    # iterate angles present in light_map (sorted)
    angles = sorted(light_map.keys())
    for ang in angles:
        lpath = light_map.get(ang)
        try:
            light_df = read_spectrum_txt(lpath)
        except Exception as e:
            print(f"[preview] Failed reading light ref {lpath}: {e}", file=sys.stderr)
            continue

        fig, ax = plt.subplots(figsize=(8,5), dpi=150)
        ax.set_title(f"Sweep preview — {ang}°")
        ax.set_xlabel("Wavelength (nm)")
        ax.set_ylabel("Reflectance (%)")

        plotted_any = False
        for name, amap in grating_paths:
            spath = amap.get(ang)
            if spath is None:
                # skip missing sample at this angle
                continue
            try:
                sample_df = read_spectrum_txt(spath)
            except Exception as e:
                print(f"[preview] Failed reading sample {spath}: {e}", file=sys.stderr)
                continue

            norm_df = normalize_percent(sample_df, dark_df, light_df)
            if min_wavelength > 0:
                norm_df = norm_df[norm_df["wavelength_nm"] >= min_wavelength]
            if max_wavelength > 0:
                norm_df = norm_df[norm_df["wavelength_nm"] <= max_wavelength]
            if norm_df.empty:
                continue

            ax.plot(norm_df["wavelength_nm"].to_numpy(), norm_df["reflectance_pct"].to_numpy(), label=name)
            plotted_any = True

        if not plotted_any:
            plt.close(fig)
            continue

        ax.legend(loc="best")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        png_path = out_dir / f"angle_{ang:03d}deg_reflectance.png"
        fig.savefig(png_path, bbox_inches="tight")
        pdf.savefig(fig)
        plt.close(fig)

    pdf.close()

    # write simple manifest
    manifest = {
        "sweep_root": str(base),
        "sweeps": [p.name for p in sweep_dirs],
        "light_ref": str(light_parent),
        "dark_ref": str(dark_path),
        "output_dir": str(out_dir),
        "pdf": str(pdf_path),
    }
    try:
        with (out_dir / "manifest_preview.json").open("w", encoding="utf-8") as mf:
            json.dump(manifest, mf, indent=2)
    except Exception:
        pass

    print(f"[preview] Wrote preview to: {out_dir}")

    # --- open generated PDF automatically (best-effort) ---
    try:
        pdf_str = str(pdf_path)
        if sys.platform.startswith("win"):
            os.startfile(pdf_str)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", pdf_str])
        else:
            # Linux and other Unix-like
            subprocess.Popen(["xdg-open", pdf_str])
    except Exception as e:
        print(f"[preview] Failed to open PDF automatically: {e}", file=sys.stderr)

    return str(out_dir)

if __name__ == "__main__":
    main()