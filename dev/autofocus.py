"""
Autofocus -- coarse-fine Z sweep for MicroView microscopes.

Works with any camera + stage combination that exposes the standard
MicroView duck-typed API:

    camera_frame.current_image  -> PIL.Image (updated by the GUI loop)
    camera_frame.camera         -> MyCamera  (for disabling auto-exposure)
    stage.get_position()        -> float     (mm)
    stage.move_to(pos_mm)       -> float     (mm, clamped)

Safety
------
* The sweep range is pre-clamped to the stage's configured software safety
  limit so the objective can never crash into the sample.
* The stage's own ``move_to()`` applies a second clamping layer.
* Autofocus can be cancelled at any time via ``stop()``.
"""

import time
import threading
import os
import datetime

import numpy as np

from dev.debugHelp import debugp


# ── Focus metrics ────────────────────────────────────────────────────────
#
# All metrics return a *higher* value for sharper images.
#
# For brightfield microscopy on low-contrast samples, normalized_variance
# is by far the most robust default (Sun et al. 2004).  Plain Laplacian
# variance is included for comparison but is easily fooled by vignetting,
# shadows, and brightness changes that come with large Z sweeps.

def _prepare_grey(pil_image, roi_fraction=0.5, blur=True):
    """Convert to greyscale, central-crop, and optionally box-blur.

    The 3×3 box blur suppresses single-pixel sensor noise so the
    sharpness metrics react to real image structure, not to noise.
    """
    grey = np.asarray(pil_image.convert("L"), dtype=np.float64)

    h, w = grey.shape
    dh = int(h * (1 - roi_fraction) / 2)
    dw = int(w * (1 - roi_fraction) / 2)
    if dh > 0 or dw > 0:
        grey = grey[dh:h - dh, dw:w - dw]

    if blur:
        # Pure-numpy 3×3 box blur (separable would be marginally faster,
        # but at half-resolution the direct form is plenty fast).
        grey = (
            grey[:-2, :-2] + grey[:-2, 1:-1] + grey[:-2, 2:] +
            grey[1:-1, :-2] + grey[1:-1, 1:-1] + grey[1:-1, 2:] +
            grey[2:, :-2] + grey[2:, 1:-1] + grey[2:, 2:]
        ) / 9.0

    return grey


def _is_unusable(grey, dark_threshold=5.0, saturation_fraction=0.30):
    """Reject frames that are mostly dark or mostly clipped.

    Such frames produce artificially-high or artificially-low scores
    that mislead the search.
    """
    mean = grey.mean()
    if mean < dark_threshold:
        return True
    saturated = float((grey >= 250).mean())
    if saturated > saturation_fraction:
        return True
    return False


def normalized_variance(pil_image, roi_fraction=0.5):
    """Brightness-invariant variance.  Robust default for microscopy.

    Score = sum((I - mean)^2) / mean.  Because it is normalised by the
    mean intensity, it is unaffected by vignetting / illumination shifts
    that occur during a large Z sweep -- the failure mode that fools
    plain Laplacian variance.
    """
    grey = _prepare_grey(pil_image, roi_fraction)
    if _is_unusable(grey):
        return 0.0
    mean = grey.mean()
    if mean < 1e-3:
        return 0.0
    return float(((grey - mean) ** 2).sum() / mean)


def laplacian_variance(pil_image, roi_fraction=0.5):
    """Variance of the discrete Laplacian (your original metric).

    Kept for comparison.  Sensitive to noise and brightness changes;
    prefer ``normalized_variance`` for microscopy.
    """
    grey = _prepare_grey(pil_image, roi_fraction, blur=False)
    if _is_unusable(grey):
        return 0.0
    laplacian = (
        grey[:-2, 1:-1]
        + grey[2:, 1:-1]
        + grey[1:-1, :-2]
        + grey[1:-1, 2:]
        - 4 * grey[1:-1, 1:-1]
    )
    return float(np.var(laplacian))


def tenengrad(pil_image, roi_fraction=0.5):
    """Mean squared Sobel gradient magnitude.

    More robust to single-pixel noise than the Laplacian because it
    uses 3-point finite differences rather than the 4-point Laplacian.
    """
    grey = _prepare_grey(pil_image, roi_fraction)
    if _is_unusable(grey):
        return 0.0
    gx = grey[1:-1, 2:] - grey[1:-1, :-2]
    gy = grey[2:, 1:-1] - grey[:-2, 1:-1]
    return float(np.mean(gx * gx + gy * gy))


# Registry so the AutoFocus class can be configured with a string.
FOCUS_METRICS = {
    "normalized_variance": normalized_variance,
    "laplacian_variance": laplacian_variance,
    "tenengrad": tenengrad,
}


# ── Stage safety helper ──────────────────────────────────────────────────

def _get_stage_safety_limit_mm(stage):
    """Read the stage's software safety limit in mm.

    Checks attributes used by both ``MyMCM301Stage`` and ``MyStage``.
    Returns ``None`` when no limit is configured.
    """
    # MyMCM301Stage stores the limit directly in mm
    limit = getattr(stage, '_safety_limit_mm', None)
    if limit is not None:
        return float(limit)

    # MyStage stores the limit in µm
    limit_um = getattr(stage, '_position_limit_um', None)
    if limit_um is not None:
        return float(limit_um) / 1000.0

    return None


# ── Autofocus engine ─────────────────────────────────────────────────────

class AutoFocus:
    """Coarse-fine Z-sweep autofocus.

    Parameters
    ----------
    camera_frame : CameraFrame
        The GUI camera frame whose ``.current_image`` is read for scoring
        and whose ``.camera`` is used to manage auto-exposure.
    stage : MyStage | MyMCM301Stage
        Any stage object exposing ``get_position()`` / ``move_to()``.
    sweep_range_mm : float
        Half-range of the coarse sweep (±) around the current Z position.
    coarse_step_mm : float
        Step size for the coarse pass.
    fine_step_mm : float
        Step size for the fine pass.
    settle_time_s : float
        Delay after each move to let vibrations damp and a fresh frame arrive.
    on_progress : callable(step, total, z_mm, score) or None
        Called after each focus measurement.
    on_complete : callable(best_z_mm, best_score) or None
        Called when autofocus finishes successfully.
    on_error : callable(exception) or None
        Called if autofocus encounters an error.
    """

    def __init__(
        self,
        camera_frame,
        stage,
        sweep_range_mm=0.1,
        coarse_step_mm=0.010,
        fine_step_mm=0.001,
        settle_time_s=0.30,
        metric="tenengrad", #normalized_variance
        save_curve_dir=None,
        on_progress=None,
        on_complete=None,
        on_error=None,
    ):
        self._camera_frame = camera_frame
        self._stage = stage
        self._sweep_range_mm = float(sweep_range_mm)
        self._coarse_step_mm = float(coarse_step_mm)
        self._fine_step_mm = float(fine_step_mm)
        self._settle_time_s = float(settle_time_s)

        if callable(metric):
            self._metric = metric
            self._metric_name = getattr(metric, "__name__", "custom")
        else:
            if metric not in FOCUS_METRICS:
                raise ValueError(
                    f"Unknown metric {metric!r}. "
                    f"Choose from {list(FOCUS_METRICS)} or pass a callable."
                )
            self._metric = FOCUS_METRICS[metric]
            self._metric_name = metric

        # Directory into which the focus curve CSV will be auto-written
        # at the end of every run (success, error, or cancellation).
        self._save_curve_dir = save_curve_dir

        self._on_progress = on_progress
        self._on_complete = on_complete
        self._on_error = on_error

        self._stop_event = threading.Event()
        # Diagnostic record of the full focus curve from the last run:
        # list of (z_mm, score, pass_name) tuples.
        self.curve = []
        # Path of the most recently saved curve CSV (for callers to log).
        self.last_csv_path = None

    # ── public ────────────────────────────────────────────────────────

    def run(self):
        """Execute the autofocus sweep (blocking -- call from a worker thread).

        The routine:
        1. Disables auto-exposure so brightness stays stable.
        2. Clamps the sweep window to the stage safety limit.
        3. Performs a *coarse* sweep over the full window.
        4. Performs a *fine* sweep around the coarse-best position.
        5. Moves to the best-focus Z and re-enables auto-exposure if needed.
        """
        auto_exposure_was_on = getattr(self._camera_frame.camera, 'auto_exposure_enabled', False)
        self.curve = []  # reset diagnostic log
        # Defined here so the error/finally blocks can reference it even
        # if we abort before reading the stage position.
        origin_z = None
        origin_safe = False

        try:
            # Disable auto-exposure during sweep
            if auto_exposure_was_on:
                self._camera_frame.camera.set_auto_exposure(False)
                debugp("AutoFocus", "Auto-exposure disabled for sweep")

            # Re-zero the stage at the current physical position so the
            # symmetric ±safety bounds are anchored to the user's chosen
            # starting Z.  set_zero() only adjusts the software offset --
            # the stage does not physically move.  Without this, a fresh
            # program launch can leave get_position() reporting a value
            # well outside the safety limit, which would force us to
            # abort.
            if hasattr(self._stage, 'set_zero'):
                try:
                    self._stage.set_zero()
                    debugp("AutoFocus",
                           "Stage zeroed at current position before sweep")
                except Exception as exc:
                    debugp("AutoFocus", f"set_zero() failed: {exc}")

            origin_z = self._stage.get_position()
            safety = _get_stage_safety_limit_mm(self._stage)
            debugp("AutoFocus",
                   f"Starting at Z={origin_z:.4f} mm, "
                   f"range=±{self._sweep_range_mm:.3f} mm, "
                   f"metric={self._metric_name}")

            # ── CRITICAL safety guard ────────────────────────────────
            # The stage uses symmetric ±safety bounds relative to the
            # user-set zero.  On a fresh start the user may not have
            # zeroed the stage yet, so get_position() can be anywhere
            # in the encoder range.  If we proceeded, the sweep window
            # would clamp to one side of zero (lo > hi), and the stage
            # would silently jump to the safety boundary - exactly the
            # "stage moves far down" symptom.  Refuse to run instead.
            if safety is not None and abs(origin_z) > safety:
                raise RuntimeError(
                    f"Stage is at {origin_z:.4f} mm, outside the safety "
                    f"limit of ±{safety:.3f} mm. "
                    f"Set the stage zero (or home it) before autofocus."
                )
            # Origin is now known to be inside the safety bounds, so it
            # is safe to use as a fallback target on cancel / error.
            origin_safe = True

            # Score the starting frame so we can refuse to move if the
            # search can't actually beat the user's starting position.
            origin_image = self._grab_fresh_frame()
            origin_score = self._metric(origin_image) if origin_image is not None else 0.0
            debugp("AutoFocus", f"Origin score = {origin_score:.1f}")

            # ── Clamp sweep to safety limits ──────────────────────────
            lo = origin_z - self._sweep_range_mm
            hi = origin_z + self._sweep_range_mm
            if safety is not None:
                lo = max(lo, -safety)
                hi = min(hi, safety)
                debugp("AutoFocus",
                       f"Sweep clamped to [{lo:.4f}, {hi:.4f}] mm "
                       f"(safety ±{safety:.3f} mm)")

            # Defence in depth: this should be impossible after the
            # origin-z guard above, but if it ever happens we abort
            # rather than feed an inverted window to np.linspace.
            if lo > hi:
                raise RuntimeError(
                    f"Sweep window invalid after safety clamp "
                    f"(lo={lo:.4f} > hi={hi:.4f})."
                )

            # ── Coarse pass ───────────────────────────────────────────
            coarse_positions = self._make_positions(lo, hi, self._coarse_step_mm)
            total_steps = len(coarse_positions)
            debugp("AutoFocus",
                   f"Coarse pass: {total_steps} positions, "
                   f"step={self._coarse_step_mm * 1000:.0f} µm")

            coarse_scores = self._sweep(coarse_positions, step_offset=0,
                                        total=total_steps, pass_name="coarse")
            if self._stop_event.is_set():
                if origin_safe:
                    self._stage.move_to(origin_z)
                debugp("AutoFocus", "Cancelled during coarse pass")
                return

            best_coarse_idx = int(np.argmax(coarse_scores))
            best_coarse_z = coarse_positions[best_coarse_idx]
            debugp("AutoFocus",
                   f"Coarse best: Z={best_coarse_z:.4f} mm, "
                   f"score={coarse_scores[best_coarse_idx]:.1f}")

            # ── Fine pass ─────────────────────────────────────────────
            fine_lo = max(lo, best_coarse_z - self._coarse_step_mm * 2)
            fine_hi = min(hi, best_coarse_z + self._coarse_step_mm * 2)
            fine_positions = self._make_positions(fine_lo, fine_hi,
                                                  self._fine_step_mm)
            total_fine = len(fine_positions)
            debugp("AutoFocus",
                   f"Fine pass: {total_fine} positions, "
                   f"step={self._fine_step_mm * 1000:.0f} µm")

            fine_scores = self._sweep(fine_positions,
                                      step_offset=total_steps,
                                      total=total_steps + total_fine,
                                      pass_name="fine")
            if self._stop_event.is_set():
                if origin_safe:
                    self._stage.move_to(origin_z)
                debugp("AutoFocus", "Cancelled during fine pass")
                return

            best_fine_idx = int(np.argmax(fine_scores))
            best_z = fine_positions[best_fine_idx]
            best_score = fine_scores[best_fine_idx]

            # ── Sanity check: refuse to move if we can't beat origin ─
            # A small tolerance so we don't shuffle by sub-pixel noise.
            if best_score < origin_score * 1.05:
                debugp("AutoFocus",
                       f"Best score {best_score:.1f} did not beat origin "
                       f"{origin_score:.1f} -- staying at origin Z={origin_z:.4f} mm")
                self._stage.move_to(origin_z)
                if self._on_complete:
                    self._on_complete(origin_z, origin_score)
                return

            # ── Move to best focus ────────────────────────────────────
            self._stage.move_to(best_z)
            debugp("AutoFocus",
                   f"Done – best focus at Z={best_z:.4f} mm "
                   f"(score={best_score:.1f}, origin was {origin_score:.1f})")

            if self._on_complete:
                self._on_complete(best_z, best_score)

        except Exception as exc:
            debugp("AutoFocus", f"Error: {exc}")
            # Only attempt a return-to-origin if we already verified
            # the origin position is inside the safety bounds.  Calling
            # move_to(origin_z) on an unsafe origin would itself be
            # silently clamped and shove the stage to the safety wall.
            if origin_safe:
                try:
                    self._stage.move_to(origin_z)
                except Exception:
                    pass
            if self._on_error:
                self._on_error(exc)
        finally:
            # Always try to save the focus curve, even on error / cancel.
            self._auto_save_curve()
            # Restore auto-exposure if it was on
            if auto_exposure_was_on:
                self._camera_frame.camera.set_auto_exposure(True)
                debugp("AutoFocus", "Auto-exposure re-enabled")

    def _auto_save_curve(self):
        """Write the focus curve to ``<save_curve_dir>/Autofocus/focus_curve_*.csv``.

        Creates the ``Autofocus`` sub-folder if needed.  Silently no-ops if
        no save directory was configured or the curve is empty.
        """
        if not self._save_curve_dir or not self.curve:
            return
        try:
            af_dir = os.path.join(self._save_curve_dir, "Autofocus")
            os.makedirs(af_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(af_dir, f"focus_curve_{ts}.csv")
            self.save_curve_csv(path)
            self.last_csv_path = path
            debugp("AutoFocus", f"Focus curve saved to {path}")
        except Exception as exc:
            debugp("AutoFocus", f"Could not save focus curve: {exc}")

    def stop(self):
        """Request cancellation of the autofocus sweep."""
        self._stop_event.set()

    # ── private ───────────────────────────────────────────────────────

    @staticmethod
    def _make_positions(lo, hi, step):
        """Generate an array of Z positions from *lo* to *hi* (inclusive)."""
        n = max(int(round((hi - lo) / step)), 1) + 1
        return np.linspace(lo, hi, n)

    def _grab_fresh_frame(self):
        """Block until a frame arrives that was captured *after* this call.

        Waits up to 2 s.  Returns the new PIL.Image, or None on timeout.
        """
        old = getattr(self._camera_frame, 'current_image', None)
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if self._stop_event.is_set():
                return None
            img = getattr(self._camera_frame, 'current_image', None)
            if img is not None and img is not old:
                return img
            time.sleep(0.01)
        # Timeout — return whatever is there (may be stale)
        debugp("AutoFocus", "Warning: fresh-frame timeout, scoring stale image")
        return getattr(self._camera_frame, 'current_image', None)

    def _sweep(self, positions, step_offset, total, pass_name="sweep"):
        """Move to each position, score, and return the scores array."""
        scores = np.zeros(len(positions))
        for i, z in enumerate(positions):
            if self._stop_event.is_set():
                return scores

            self._stage.move_to(float(z))
            time.sleep(self._settle_time_s)

            # Wait for a frame that was captured after the stage settled
            image = self._grab_fresh_frame()
            if image is None:
                scores[i] = 0.0
            else:
                scores[i] = self._metric(image)

            self.curve.append((float(z), float(scores[i]), pass_name))
            debugp("AutoFocus",
                   f"  {pass_name} z={z:.4f} mm  score={scores[i]:.2f}")

            if self._on_progress:
                self._on_progress(step_offset + i + 1,
                                  total,
                                  float(z),
                                  float(scores[i]))

        return scores

    def save_curve_csv(self, path):
        """Write the last run's focus curve to a CSV for plotting/debug."""
        with open(path, "w", encoding="utf-8") as f:
            f.write("z_mm,score,pass\n")
            for z, s, p in self.curve:
                f.write(f"{z:.6f},{s:.6f},{p}\n")
