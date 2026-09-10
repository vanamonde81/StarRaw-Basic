##############################################
# StarRaw Basic (Charcoal theme) — Siril Python Script
# Adobe Camera Raw "Basic" panel emulation
# Light  : Exposure / Contrast / Highlights / Shadows / Whites / Blacks
# Effects: Clarity / Dehaze
# Color  : Temperature / Tint / Vibrance / Saturation
##############################################
#
# Requirements: Siril 1.3+, sirilpy, PyQt6, numpy, opencv-python
#
# Usage:
#   1. Open/load an image in Siril.
#   2. Run this script. The current image is loaded automatically.
#   3. Adjust the sliders — the preview and the RGB histogram
#      update in real time.
#   4. Press APPLY to write the adjustment back to Siril
#      (overwrites the loaded image, with undo support).
#
# GUI layout:
#   Left  : zoomable preview (mouse wheel zoom, drag pan,
#           SPACE = compare with original, double-click = fit)
#   Right : histogram + Light / Effects / Color sliders + buttons
#   Bottom: status bar (image info, zoom, version)

import sys
import traceback

try:
    import sirilpy as s
    from sirilpy import LogColor
except ImportError:
    print("Error: sirilpy module not found. Run this script from Siril.")
    sys.exit(1)

try:
    s.ensure_installed("PyQt6", "numpy", "opencv-python")
except AttributeError:
    print("Warning: sirilpy.ensure_installed not found. Assuming dependencies are met.")

import numpy as np
import cv2

from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QWidget, QLabel, QPushButton, QMessageBox,
                             QProgressBar, QGraphicsView, QGraphicsScene,
                             QGraphicsPixmapItem, QDoubleSpinBox, QSpinBox,
                             QGridLayout, QSizePolicy, QFrame, QScrollArea, QDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QEvent, QRectF, QPointF
from PyQt6.QtGui import (QImage, QPixmap, QKeyEvent, QPainter, QPen, QColor,
                         QPainterPath, QBrush, QIcon, QPolygonF, QLinearGradient)

VERSION = "1.05"
VERSION_DATE = "2026/09/11"

# ---------------------
#  THEME & STYLING
# ---------------------
# Every colour / font of the GUI is defined here. Edit THEME to restyle
# the whole application; nothing else in the file hard-codes a colour.

THEME = {
    # --- Deep charcoal (fully neutral, low glare) --------------------------
    "font_ui":       '"Segoe UI", "Inter", sans-serif',
    "font_title":    '"Segoe UI", "Inter", sans-serif',
    "fs_base":       "10pt",
    "fs_small":      "8pt",
    "fs_section":    "8pt",
    "fs_title":      "13pt",
    "title_weight":  "normal",
    "section_ls":    "1.8px",
    "radius":        "3px",
    "radius_sm":     "2px",

    "accent":        "#9a9a9a",
    "accent_dim":    "#4a4a4a",

    "win_bg":        "#101010",
    "panel_bg":      "#141414",
    "panel_border":  "#262626",
    "canvas_bg":     "#080808",
    "status_bg":     "#0c0c0c",

    "text":          "#b0b0b0",
    "text_dim":      "#5e5e5e",
    "text_disabled": "#454545",
    "title_color":   "#c8c8c8",
    "value_color":   "#d8d8d8",

    "ctrl_bg":       "#1e1e1e",
    "ctrl_border":   "#2e2e2e",
    "btn_bg":        "#1e1e1e",
    "btn_bg_hover":  "#2a2a2a",
    "btn_border":    "#333333",
    "apply_bg":      "#4a4a4a",
    "apply_bg_hover":"#5c5c5c",
    "apply_border":  "#7a7a7a",
    "apply_text":    "#f0f0f0",
    "close_bg":      "#1e1e1e",
    "close_bg_hover":"#2a2a2a",
    "close_border":  "#333333",
    "close_text":    "#b0b0b0",

    "tip_bg":        "#1e1e1e",
    "tip_text":      "#d8d8d8",

    "hist_bg":       "#0a0a0a",
    "hist_frame":    "#232323",
    "hist_grid":     "#1e1e1e",
    "hist_axis":     "#2e2e2e",
    "hist_label":    "#5e5e5e",
    "hist_mono":     "#b0b0b0",
    "hist_r":        "#c04a4a",
    "hist_g":        "#4aae4a",
    "hist_b":        "#5a7fd0",

    # Color-group groove gradients (left -> right), ACR style
    "grad_temperature":  ["#3a6fd8", "#7a7a7a", "#e8c830"],
    "grad_tint":         ["#3c9a3c", "#7a7a7a", "#c04ac0"],
    "grad_vibrance":     ["#6a6a6a", "#6a9a9a", "#c8a050", "#d06060"],
    "grad_saturation":   ["#6a6a6a", "#6a9a9a", "#c8a050", "#d06060"],
    "groove":            "#2e2e2e",
    "groove_off":        "#222222",
    "tick":              "#545454",
    "handle":            "#0a0a0a",
    "handle_hover":      "#2a2a2a",
    "handle_border":     "#b8b8b8",
    "handle_off":        "#1e1e1e",
    "handle_border_off": "#333333",

    "blink":         "#d8d8d8",
}

ACCENT = THEME["accent"]

DARK_STYLESHEET = """
QMainWindow, QWidget {{ background-color: {win_bg}; color: {text}; font-family: {font_ui}; font-size: {fs_base}; }}
QToolTip {{ background-color: {tip_bg}; color: {tip_text}; border: 1px solid {accent}; padding: 3px; }}

QWidget#Panel {{ background-color: {panel_bg}; border: 1px solid {panel_border}; border-radius: {radius}; }}
QLabel {{ color: {text}; background: transparent; }}
QLabel#Section {{ color: {accent}; font-family: {font_ui}; font-size: {fs_section}; font-weight: bold; letter-spacing: {section_ls}; }}
QLabel#Title {{ font-family: {font_title}; font-size: {fs_title}; font-weight: {title_weight}; color: {title_color}; }}
QLabel#Hint {{ color: {text_dim}; font-size: {fs_small}; }}
QFrame#SectionLine {{ background-color: {panel_border}; max-height: 1px; min-height: 1px; border: none; }}

QDoubleSpinBox, QSpinBox {{
    background-color: {ctrl_bg}; color: {value_color}; border: 1px solid {ctrl_border};
    border-radius: {radius_sm}; padding: 1px 6px; min-width: 52px; max-width: 60px;
    font-family: {font_ui}; font-size: {fs_small};
}}
QDoubleSpinBox:disabled, QSpinBox:disabled {{ color: {text_disabled}; }}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; border: none; }}

QPushButton {{ background-color: {btn_bg}; color: {text}; border: 1px solid {btn_border};
               border-radius: {radius}; padding: 6px 10px; font-family: {font_ui}; font-weight: bold; }}
QPushButton:hover {{ background-color: {btn_bg_hover}; border-color: {accent}; }}
QPushButton#ApplyButton {{ background-color: {apply_bg}; color: {apply_text}; border: 1px solid {apply_border}; }}
QPushButton#ApplyButton:hover {{ background-color: {apply_bg_hover}; }}
QPushButton#CloseButton {{ background-color: {close_bg}; color: {close_text}; border: 1px solid {close_border}; }}
QPushButton#CloseButton:hover {{ background-color: {close_bg_hover}; }}
QPushButton#SmallButton {{ padding: 2px 8px; font-weight: normal; font-size: {fs_small}; }}
QPushButton#HelpButton {{ padding: 0px; border-radius: 10px; font-size: {fs_small};
                          background-color: transparent; color: {text_dim}; border: 1px solid {panel_border}; }}
QPushButton#HelpButton:hover {{ color: {text}; border-color: {accent}; }}

QWidget#StatusBar {{ background-color: {status_bg}; border-top: 1px solid {panel_border}; }}
QWidget#StatusBar QLabel {{ color: {text_dim}; font-size: {fs_small}; background: transparent; }}

QProgressBar {{ background-color: {ctrl_bg}; border: none; border-radius: 2px; }}
QProgressBar::chunk {{ background-color: {accent}; border-radius: 2px; }}

QScrollArea#SliderScroll {{ background: transparent; border: none; }}
QScrollArea#SliderScroll > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: {panel_bg}; width: 8px; margin: 0; border: none; }}
QScrollBar::handle:vertical {{ background: {accent_dim}; min-height: 24px; border-radius: 4px; }}
QScrollBar::handle:vertical:hover {{ background: {accent}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; border: none; background: none; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
""".format(**THEME)

# =============================================================================
#  CORE MATH — Camera Raw "Basic" panel emulation
# =============================================================================

class RawCore:

    LUT_SIZE = 65536
    TONE_KEYS = ('exposure', 'contrast', 'highlights', 'shadows', 'whites', 'blacks')

    @staticmethod
    def normalize_input(img_data):
        input_dtype = img_data.dtype
        img_float = img_data.astype(np.float32)
        if np.issubdtype(input_dtype, np.integer):
            if input_dtype == np.uint8:
                return img_float / 255.0
            elif input_dtype == np.uint16:
                return img_float / 65535.0
            else:
                return img_float / float(np.iinfo(input_dtype).max)
        elif np.issubdtype(input_dtype, np.floating):
            current_max = np.max(img_data)
            if current_max <= 1.0 + 1e-5:
                return img_float
            if current_max <= 65535.0:
                return img_float / 65535.0
            return img_float
        return img_float

    # --- smooth helpers -----------------------------------------------------

    @staticmethod
    def _smoothstep(e0, e1, x):
        t = np.clip((x - e0) / (e1 - e0 + 1e-9), 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)

    # --- tone curve (1D LUT) ------------------------------------------------

    @staticmethod
    def build_lut(exposure, contrast, highlights, shadows, whites, blacks):
        """
        Builds a 1D tone LUT emulating the ACR Basic panel.
        Input domain: [0,1]. Output: [0,1] float32.

        Region weights are deliberately wide, so every slider bleeds
        noticeably into the neighbouring tonal regions (ACR-like
        behaviour) instead of acting on a narrow band only.

        Order of operations (approximating ACR):
          Exposure -> Whites/Blacks (endpoint) -> Highlights/Shadows
          (region recovery/lift) -> Contrast (midtone S-curve)
        """
        x = np.linspace(0.0, 1.0, RawCore.LUT_SIZE, dtype=np.float32)

        # 1) Exposure: photographic stops, linear multiply + soft shoulder.
        gain = 2.0 ** exposure
        y = x * gain
        if gain > 1.0:
            knee = 0.80
            m = y > knee
            if np.any(m):
                t = np.clip((y[m] - knee) / (gain - knee), 0.0, 1.0)
                p = 1.0 + 1.5 * (gain - 1.0)
                y[m] = knee + (1.0 - knee) * (1.0 - (1.0 - t) ** p)
        y = np.clip(y, 0.0, 1.0)

        # 2) Whites: white point — wide ramp reaching well into the midtones
        w = whites / 100.0
        w_weight = RawCore._smoothstep(0.10, 1.0, y) ** 1.5
        y = y + w * 0.22 * w_weight

        # 3) Blacks: black point — wide ramp reaching up to the midtones
        b = blacks / 100.0
        b_weight = (1.0 - RawCore._smoothstep(0.0, 0.75, y)) ** 1.5
        y = y + b * 0.22 * b_weight
        y = np.clip(y, 0.0, 1.0)

        # 4) Highlights: broad bump centred at ~0.72 (sigma 0.28)
        h = highlights / 100.0
        h_weight = np.exp(-((y - 0.72) ** 2) / (2 * 0.28 ** 2))
        y = y + h * 0.20 * h_weight

        # 5) Shadows: broad bump centred at ~0.26 (sigma 0.28)
        sh = shadows / 100.0
        s_weight = np.exp(-((y - 0.26) ** 2) / (2 * 0.28 ** 2))
        y = y + sh * 0.20 * s_weight
        y = np.clip(y, 0.0, 1.0)

        # 6) Contrast: smooth S-curve around 0.5
        c = contrast / 100.0
        if c > 0:
            s_curve = y * y * (3.0 - 2.0 * y)
            y = y + c * 0.9 * (s_curve - y)
        elif c < 0:
            y = y + (-c) * 0.6 * (0.5 - y)
        y = np.clip(y, 0.0, 1.0)

        # Enforce monotonicity (running max) to avoid tone reversal artifacts
        y = np.maximum.accumulate(y)
        return y.astype(np.float32)

    @staticmethod
    def apply_lut(img, lut):
        """Apply 1D LUT per channel to a float [0,1] image (2D or HxWx3)."""
        idx = np.clip(img * (RawCore.LUT_SIZE - 1), 0, RawCore.LUT_SIZE - 1).astype(np.uint16)
        return lut[idx]

    # --- colour (White balance) ---------------------------------------------

    @staticmethod
    def apply_white_balance(img, temperature, tint):
        """
        Temperature / Tint on an HxWx3 float [0,1] image.

        Temperature: (+) warmer  -> R up, B down;  (-) cooler -> B up, R down.
        Tint       : (+) magenta -> G down;        (-) green  -> G up.
        Implemented as per-channel gains normalized so that Rec.709
        luminance of a neutral grey stays unchanged (only hue shifts).
        """
        te = temperature / 100.0
        ti = tint / 100.0
        if te == 0.0 and ti == 0.0:
            return img

        k_temp = 0.35      # strength of full-scale temperature shift
        k_tint = 0.30      # strength of full-scale tint shift
        gr = 1.0 + k_temp * te
        gb = 1.0 - k_temp * te
        gg = 1.0 - k_tint * ti
        # keep luminance of grey constant
        norm = 0.2126 * gr + 0.7152 * gg + 0.0722 * gb
        gains = np.array([gr, gg, gb], dtype=np.float32) / np.float32(norm)
        out = img * gains
        return np.clip(out, 0.0, 1.0).astype(np.float32)

    # --- colour (Presence) --------------------------------------------------

    @staticmethod
    def apply_color(img, vibrance, saturation):
        """
        Vibrance / Saturation on an HxWx3 float [0,1] image.

        Saturation: uniform chroma scaling around Rec.709 luminance.
        Vibrance : adaptive chroma scaling — pixels that are already
                   saturated are affected less (weight = 1 - sat),
                   which protects strong colours and star cores.
        """
        v = vibrance / 100.0
        sa = saturation / 100.0
        if v == 0.0 and sa == 0.0:
            return img

        lum = (0.2126 * img[..., 0] + 0.7152 * img[..., 1]
               + 0.0722 * img[..., 2])[..., None]
        out = img

        if v != 0.0:
            mx = img.max(axis=2)
            mn = img.min(axis=2)
            sat = (mx - mn) / (mx + 1e-6)          # HSV-style saturation
            if v < 0:
                weight = np.ones_like(sat)          # negative: plain desaturate
            else:
                weight = (1.0 - sat)
            factor = (1.0 + v * 1.2 * weight)[..., None]
            out = lum + (out - lum) * factor

        if sa != 0.0:
            out = lum + (out - lum) * (1.0 + sa)

        return np.clip(out, 0.0, 1.0).astype(np.float32)

    # --- effects (Clarity / Dehaze) -----------------------------------------

    @staticmethod
    def _luma(img):
        """Rec.709 luminance (2D) of a 2D or HxWx3 float image."""
        if img.ndim == 2:
            return np.ascontiguousarray(img, dtype=np.float32)
        return (0.2126 * img[..., 0] + 0.7152 * img[..., 1]
                + 0.0722 * img[..., 2]).astype(np.float32)

    @staticmethod
    def _big_blur(img2d, sigma):
        """Gaussian blur with a large sigma; downsampled for speed."""
        img2d = np.ascontiguousarray(img2d, dtype=np.float32)
        h, w = img2d.shape
        ds = max(1, int(sigma / 6.0))
        if ds > 1:
            small = cv2.resize(img2d, (max(4, w // ds), max(4, h // ds)),
                               interpolation=cv2.INTER_AREA)
            small = cv2.GaussianBlur(small, (0, 0), sigma / ds)
            return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
        return cv2.GaussianBlur(img2d, (0, 0), sigma)

    @staticmethod
    def _veil(ch2d):
        """
        Low-frequency 'haze' estimate of one channel (dark-channel style):
        downsample to ~400 px, local minimum (removes stars / small bright
        detail), wide Gaussian blur, upsample back.
        Radii are relative to the image size, so preview and final
        apply behave identically.
        """
        ch2d = np.ascontiguousarray(ch2d, dtype=np.float32)
        h, w = ch2d.shape
        ds = max(1, int(round(max(h, w) / 400.0)))
        sw, sh = max(8, w // ds), max(8, h // ds)
        small = cv2.resize(ch2d, (sw, sh), interpolation=cv2.INTER_AREA)
        small = cv2.erode(small, np.ones((5, 5), np.uint8))
        small = cv2.GaussianBlur(small, (0, 0), 0.06 * max(sw, sh))
        return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)

    @staticmethod
    def apply_clarity(img, clarity):
        """
        Clarity: midtone local contrast (large-radius unsharp mask on
        luminance). Radius = 2.5 % of the longer image side.
        A midtone weight (peak at 0.5, zero at 0 and 1) protects deep
        shadows and bright cores (stars) from halos and clipping.
        Colour is preserved by scaling RGB with new_lum / lum.
        """
        c = clarity / 100.0
        if c == 0.0:
            return img
        lum = RawCore._luma(img)
        h, w = lum.shape
        sigma = 0.025 * max(h, w)
        blur = RawCore._big_blur(lum, sigma)
        detail = lum - blur
        mid = np.sqrt(np.clip(4.0 * lum * (1.0 - lum), 0.0, 1.0))
        gain = 0.85 if c > 0 else 0.55
        new_lum = np.clip(lum + c * gain * detail * mid, 0.0, 1.0)
        if img.ndim == 2:
            return new_lum.astype(np.float32)
        ratio = (new_lum / (lum + 1e-6))[..., None]
        return np.clip(img * ratio, 0.0, 1.0).astype(np.float32)

    @staticmethod
    def apply_dehaze(img, dehaze):
        """
        Dehaze: estimates the low-frequency veil per channel (see _veil)
        and removes (+) or adds (-) it.

          (+) out = (img - s) / (1 - s),   s = d * 0.85 * veil
              -> local background subtraction with white-point renormalisation;
                 also neutralises colour casts of the veil / skyglow.
          (-) out = img + s * (0.85 - img), s = |d| * (0.15 + 0.6 * veil)
              -> blends toward a light-grey haze.
        """
        d = dehaze / 100.0
        if d == 0.0:
            return img
        if img.ndim == 2:
            veil = RawCore._veil(img)
        else:
            veil = np.stack([RawCore._veil(img[..., i]) for i in range(3)],
                            axis=-1)
        veil = np.clip(veil, 0.0, 1.0)
        if d > 0:
            s = np.clip(d * 0.85 * veil, 0.0, 0.95)
            out = (img - s) / (1.0 - s)
        else:
            s = np.clip(-d * (0.15 + 0.6 * veil), 0.0, 0.95)
            out = img + s * (0.85 - img)
        return np.clip(out, 0.0, 1.0).astype(np.float32)

    @staticmethod
    def process(img, params):
        tone = {k: params[k] for k in RawCore.TONE_KEYS}
        lut = RawCore.build_lut(**tone)
        out = RawCore.apply_lut(img, lut)
        out = RawCore.apply_dehaze(out, params.get('dehaze', 0))
        out = RawCore.apply_clarity(out, params.get('clarity', 0))
        if out.ndim == 3:
            out = RawCore.apply_white_balance(out, params.get('temperature', 0),
                                              params.get('tint', 0))
            out = RawCore.apply_color(out, params.get('vibrance', 0),
                                      params.get('saturation', 0))
        return out


# =============================================================================
#  WORKER THREAD (final apply)
# =============================================================================

class ProcessingWorker(QThread):
    result_ready = pyqtSignal(object)

    def __init__(self, img, params):
        super().__init__()
        self.img = img
        self.p = params

    def run(self):
        try:
            res = RawCore.process(self.img, self.p)
            self.result_ready.emit(res)
        except Exception as e:
            print(f"Error in worker: {e}")
            self.result_ready.emit(None)


# =============================================================================
#  HISTOGRAM WIDGET (per-channel RGB overlay, single plot)
# =============================================================================

class HistogramWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(130)
        self.setMaximumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.hist_r = None
        self.hist_g = None
        self.hist_b = None
        self.is_mono = False

    def set_histograms(self, hr, hg=None, hb=None):
        self.hist_r = hr
        self.hist_g = hg
        self.hist_b = hb
        self.is_mono = (hg is None)
        self.update()

    @staticmethod
    def _prep(h):
        """Smooth + sqrt scaling + normalize for display."""
        if h is None:
            return None
        h = h.astype(np.float32)
        kernel = np.array([1, 2, 3, 2, 1], dtype=np.float32)
        kernel /= kernel.sum()
        h = np.convolve(h, kernel, mode='same')
        h = np.sqrt(h)
        mx = h.max()
        if mx > 0:
            h /= mx
        return h

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        pad_top = 6
        pad_bot = 16
        base = h - pad_bot
        plot_h = base - pad_top

        painter.fillRect(0, 0, w, h, QColor(THEME["hist_bg"]))
        painter.setPen(QPen(QColor(THEME["hist_frame"]), 1))
        painter.drawRect(0, 0, w - 1, h - 1)

        # quarter grid
        painter.setPen(QPen(QColor(THEME["hist_grid"]), 1, Qt.PenStyle.DashLine))
        for i in range(1, 4):
            gx = int(w * i / 4)
            painter.drawLine(gx, 2, gx, base)
        painter.setPen(QPen(QColor(THEME["hist_axis"]), 1))
        painter.drawLine(1, base, w - 2, base)

        # axis labels
        painter.setPen(QColor(THEME["hist_label"]))
        f = painter.font(); f.setPointSize(7); painter.setFont(f)
        for i, t in enumerate(("0", "0.25", "0.5", "0.75")):
            painter.drawText(int(w * i / 4) + 4, h - 4, t)
        painter.drawText(w - 10, h - 4, "1")

        def draw_channel(hist, color, fill_alpha=50):
            if hist is None:
                return
            d = self._prep(hist)
            n = len(d)
            step = (w - 2) / (n - 1)
            path = QPainterPath()
            path.moveTo(1, base)
            for i, val in enumerate(d):
                path.lineTo(1 + i * step, base - val * plot_h)
            path.lineTo(w - 1, base)
            path.closeSubpath()
            fill = QColor(color)
            fill.setAlpha(fill_alpha)
            painter.fillPath(path, QBrush(fill))
            painter.setPen(QPen(QColor(color), 1.4))
            line = QPainterPath()
            line.moveTo(1, base - d[0] * plot_h)
            for i, val in enumerate(d):
                line.lineTo(1 + i * step, base - val * plot_h)
            painter.drawPath(line)

        if self.is_mono:
            draw_channel(self.hist_r, THEME["hist_mono"], 70)
        else:
            draw_channel(self.hist_r, THEME["hist_r"])
            draw_channel(self.hist_g, THEME["hist_g"])
            draw_channel(self.hist_b, THEME["hist_b"])


# =============================================================================
#  GUI HELPERS
# =============================================================================

class BipolarSlider(QWidget):
    """
    Custom-painted horizontal slider. Accent bar runs from the centre
    (default value) to the handle, ACR/Lightroom style.
    Double-click = reset. Wheel = step. Drag = set.
    """
    valueChanged = pyqtSignal(int)

    HANDLE_R = 6
    GROOVE_H = 4

    def __init__(self, minimum=-100, maximum=100, default_val=0, parent=None,
                 gradient=None):
        super().__init__(parent)
        self._min = minimum
        self._max = maximum
        self._val = default_val
        self.default_val = default_val
        self._gradient = list(gradient) if gradient else None
        self._hover = False
        self._pressed = False
        self.setFixedHeight(20)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # --- API (QSlider-like) ---
    def setRange(self, lo, hi):
        self._min, self._max = lo, hi
        self.update()

    def value(self):
        return self._val

    def setValue(self, v):
        v = int(max(self._min, min(self._max, v)))
        if v != self._val:
            self._val = v
            self.update()
            self.valueChanged.emit(v)

    # --- geometry ---
    def _track(self):
        m = self.HANDLE_R + 1
        return m, self.width() - m

    def _val_to_x(self, v):
        x0, x1 = self._track()
        return x0 + (v - self._min) / (self._max - self._min) * (x1 - x0)

    def _x_to_val(self, x):
        x0, x1 = self._track()
        t = (x - x0) / max(1, (x1 - x0))
        return int(round(self._min + t * (self._max - self._min)))

    # --- painting ---
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x0, x1 = self._track()
        cy = self.height() / 2
        gh = self.GROOVE_H

        p.setPen(Qt.PenStyle.NoPen)
        cx = self._val_to_x(self.default_val)
        hx = self._val_to_x(self._val)

        if self._gradient and self.isEnabled():
            grad = QLinearGradient(x0, 0, x1, 0)
            n = len(self._gradient)
            for i, col in enumerate(self._gradient):
                grad.setColorAt(i / (n - 1), QColor(col))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(x0, cy - gh / 2, x1 - x0, gh), 2, 2)
        else:
            p.setBrush(QColor(THEME["groove"] if self.isEnabled() else THEME["groove_off"]))
            p.drawRoundedRect(QRectF(x0, cy - gh / 2, x1 - x0, gh), 2, 2)
            if self.isEnabled():
                p.setBrush(QColor(ACCENT))
                p.drawRoundedRect(QRectF(min(cx, hx), cy - gh / 2, abs(hx - cx), gh), 2, 2)

        p.setPen(QPen(QColor(THEME["tick"]), 1))
        p.drawLine(int(cx), int(cy - 5), int(cx), int(cy + 5))

        if self.isEnabled():
            fill = (THEME["handle_hover"] if (self._hover or self._pressed)
                    else THEME["handle"])
            border = ACCENT if (self._hover or self._pressed) else THEME["handle_border"]
        else:
            fill, border = THEME["handle_off"], THEME["handle_border_off"]
        p.setPen(QPen(QColor(border), 1))
        p.setBrush(QColor(fill))
        r = self.HANDLE_R
        p.drawEllipse(QRectF(hx - r, cy - r, 2 * r, 2 * r))

    # --- interaction ---
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._pressed = True
            self.setValue(self._x_to_val(e.position().x()))
            e.accept()

    def mouseMoveEvent(self, e):
        self._hover = True
        if self._pressed:
            self.setValue(self._x_to_val(e.position().x()))
        self.update()

    def mouseReleaseEvent(self, e):
        self._pressed = False
        self.update()

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.setValue(self.default_val)
            e.accept()

    def wheelEvent(self, e):
        if not self.isEnabled():
            return
        step = 1 if abs(self._max - self._min) <= 200 else 5
        self.setValue(self._val + (step if e.angleDelta().y() > 0 else -step))
        e.accept()

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()


def make_section(title):
    """'TITLE ─────────' header widget."""
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 6, 0, 2)
    lay.setSpacing(8)
    lbl = QLabel(title.upper())
    lbl.setObjectName("Section")
    line = QFrame()
    line.setObjectName("SectionLine")
    line.setFrameShape(QFrame.Shape.HLine)
    lay.addWidget(lbl)
    lay.addWidget(line, 1)
    return w


class ThemedDialog(QDialog):
    """QDialog whose native (Windows) title bar follows the app theme."""

    def showEvent(self, event):
        super().showEvent(event)
        style_windows_titlebar(self, THEME["win_bg"], THEME["title_color"])
        # DWM sometimes ignores the first call on a freshly created HWND
        QTimer.singleShot(0, lambda: style_windows_titlebar(
            self, THEME["win_bg"], THEME["title_color"]))


def show_help_dialog(parent, panel_hex, text_hex, border_hex, accent_hex):
    dlg = ThemedDialog(parent)
    dlg.setWindowTitle("Controls")
    dlg.setModal(True)
    dlg.setMinimumWidth(460)
    dlg.setStyleSheet("QDialog { background-color: %s; }" % panel_hex)

    rows = [
        ("Mouse wheel over preview", "Zoom in / out"),
        ("Drag on preview", "Pan"),
        ("Double-click on preview", "Fit to window"),
        ("Hold SPACE", "Show the original image; histogram and sliders "
                        "temporarily revert to their defaults"),
        ("Double-click a slider", "Reset that slider"),
        ("Mouse wheel over a slider", "Step the value"),
        ("Reset", "All sliders to default"),
    ]
    row_tpl = (
        '<tr><td style="padding:5px 14px 5px 0; color:%s; '
        'border-bottom:1px solid %s; white-space:nowrap;">%s</td>'
        '<td style="padding:5px 0; color:%s; '
        'border-bottom:1px solid %s;">%s</td></tr>'
    )
    cells = "".join(
        row_tpl % (text_hex, border_hex, action, text_hex, border_hex, effect)
        for action, effect in rows
    )
    html = (
        '<div style="font-family: Segoe UI, sans-serif; font-size: 12px;">'
        '<table cellspacing="0" cellpadding="0" style="border-collapse:collapse; width:100%%;">'
        '<tr>'
        '<th style="text-align:left; padding:0 14px 6px 0; color:%s; '
        'border-bottom:1px solid %s;">Action</th>'
        '<th style="text-align:left; padding:0 0 6px 0; color:%s; '
        'border-bottom:1px solid %s;">Effect</th>'
        '</tr>%s</table></div>'
    ) % (accent_hex, accent_hex, accent_hex, accent_hex, cells)

    lbl = QLabel(html)
    lbl.setTextFormat(Qt.TextFormat.RichText)
    lbl.setWordWrap(True)

    btn_close = QPushButton("Close")
    btn_close.clicked.connect(dlg.accept)
    btn_close.setDefault(True)

    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(18, 16, 18, 14)
    lay.setSpacing(12)
    title = QLabel("Controls")
    title.setStyleSheet("color:%s; font-size:14px; font-weight:600;" % text_hex)
    lay.addWidget(title)
    lay.addWidget(lbl)
    btn_row = QHBoxLayout()
    btn_row.addStretch()
    btn_row.addWidget(btn_close)
    lay.addLayout(btn_row)

    dlg.exec()


class CollapsibleSection(QWidget):
    """
    'TITLE ───────── v' header that shows/hides its body.
    Click anywhere on the header to toggle.
    """

    def __init__(self, title, expanded=True, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._expanded = expanded

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._header = QWidget()
        self._header.setStyleSheet("background: transparent;")
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.mousePressEvent = self._header_clicked
        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(0, 6, 0, 2)
        hl.setSpacing(8)

        self._arrow = QLabel()
        self._arrow.setObjectName("Section")
        self._lbl = QLabel(title.upper())
        self._lbl.setObjectName("Section")
        line = QFrame()
        line.setObjectName("SectionLine")
        line.setFrameShape(QFrame.Shape.HLine)
        hl.addWidget(self._arrow)
        hl.addWidget(self._lbl)
        hl.addWidget(line, 1)
        outer.addWidget(self._header)

        self.body = QWidget()
        self.body.setStyleSheet("background: transparent;")
        self._body_layout = QVBoxLayout(self.body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(0)
        outer.addWidget(self.body)

        self._sync()

    def add_layout(self, layout):
        self._body_layout.addLayout(layout)

    def _header_clicked(self, event):
        self.toggle()
        event.accept()

    def toggle(self):
        self._expanded = not self._expanded
        self._sync()

    def set_expanded(self, state):
        self._expanded = bool(state)
        self._sync()

    def _sync(self):
        self._arrow.setText("\u25be" if self._expanded else "\u25b8")
        self.body.setVisible(self._expanded)


def make_star_icon(size=256, color="#ffd21e", stroke_frac=0.05):
    """Outlined five-pointed yellow star (no fill) on a transparent background."""
    import math
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    cx = cy = size / 2.0
    r_out = size * 0.46
    r_in = r_out * 0.40
    pts = []
    for i in range(10):
        r = r_out if i % 2 == 0 else r_in
        a = -math.pi / 2 + i * math.pi / 5
        pts.append(QPointF(cx + r * math.cos(a), cy + r * math.sin(a)))
    pen = QPen(QColor(color), size * stroke_frac)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPolygon(QPolygonF(pts))
    p.end()
    icon = QIcon()
    for s_ in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(pm.scaled(s_, s_, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation))
    return icon


def set_windows_app_id(app_id):
    """Windows: separate taskbar identity so the window icon is used."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception as e:
        print(f"AppUserModelID skipped: {e}")


def style_windows_titlebar(widget, bg_hex, text_hex):
    """
    Windows 10/11: paint the native title bar to match the app background.
    Silently does nothing on other platforms or older Windows builds.
    """
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        from ctypes import wintypes

        hwnd = int(widget.winId())
        dwm = ctypes.windll.dwmapi

        def _colorref(h):
            h = h.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return b << 16 | g << 8 | r          # DWM expects 0x00BBGGRR

        # dark mode first (older Win10 builds use attribute 19)
        for attr in (20, 19):
            val = ctypes.c_int(1)
            dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), ctypes.c_int(attr),
                                      ctypes.byref(val), ctypes.sizeof(val))

        # Win11 22000+: explicit caption / text / border colours
        for attr, hexcol in ((35, bg_hex), (36, text_hex), (34, bg_hex)):
            col = ctypes.c_int(_colorref(hexcol))
            dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), ctypes.c_int(attr),
                                      ctypes.byref(col), ctypes.sizeof(col))

        # force non-client area repaint so the new colours show immediately
        SWP_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0020   # NOSIZE|NOMOVE|NOZORDER|FRAMECHANGED
        ctypes.windll.user32.SetWindowPos(wintypes.HWND(hwnd), None, 0, 0, 0, 0, SWP_FLAGS)
    except Exception as e:
        print(f"Title bar styling skipped: {e}")


# =============================================================================
#  MAIN GUI
# =============================================================================

class StarRawGUI(QMainWindow):
    def __init__(self, siril, app):
        super().__init__()
        self.siril = siril
        self.app = app
        self.setWindowTitle("StarRaw Basic")
        self.setStyleSheet(DARK_STYLESHEET)
        self.resize(1280, 840)
        self.setWindowIcon(make_star_icon())

        self.img_full = None       # HxWx3 or HxW float [0,1]
        self.img_proxy = None
        self.comp_proxy = None
        self.is_mono_source = False
        self._current_display_buffer = None

        self.show_original = False
        self._updating = False

        self.debounce = QTimer()
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(80)
        self.debounce.timeout.connect(self.run_preview_logic)

        header_msg = (
            f"\n##############################################\n"
            f"# StarRaw Basic v{VERSION}\n"
            "# ACR Basic panel emulation for Siril\n"
            "##############################################"
        )
        try:
            self.siril.log(header_msg)
        except Exception:
            print(header_msg)

        self.init_ui()
        self.cache_input()

    # -------------------------------------------------------------- UI setup

    def init_ui(self):
        main = QWidget()
        self.setCentralWidget(main)
        outer = QVBoxLayout(main)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QWidget()
        layout = QHBoxLayout(body)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(12)
        outer.addWidget(body, 1)

        # ---------------- LEFT: preview ----------------
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setStyleSheet(
            f"background-color: {THEME['canvas_bg']};"
            f" border: 1px solid {THEME['panel_border']};")
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.view.viewport().installEventFilter(self)
        self.view.installEventFilter(self)
        layout.addWidget(self.view, 1)

        self.pix_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pix_item)
        self.pix_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

        self.lbl_blink = QLabel("ORIGINAL", self.view)
        self.lbl_blink.setStyleSheet(
            f"background-color: rgba(0, 0, 0, 170); color: {THEME['blink']};"
            f" font-size: 11pt; font-weight: bold; padding: 4px 10px;"
            f" border-radius: {THEME['radius']};")
        self.lbl_blink.adjustSize()
        self.lbl_blink.hide()

        # ---------------- RIGHT: control panel ----------------
        panel = QWidget()
        panel.setObjectName("Panel")
        panel.setFixedWidth(360)
        right = QVBoxLayout(panel)
        right.setContentsMargins(12, 10, 12, 12)
        right.setSpacing(4)

        # header row: title
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 4)
        lbl_title = QLabel("StarRaw Basic")
        lbl_title.setObjectName("Title")
        hdr.addWidget(lbl_title)
        hdr.addStretch()
        btn_help = QPushButton("?")
        btn_help.setObjectName("HelpButton")
        btn_help.setFixedSize(20, 20)
        btn_help.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_help.setToolTip("Controls")
        btn_help.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_help.clicked.connect(
            lambda: show_help_dialog(self, THEME["panel_bg"],
                                     THEME["text"], THEME["panel_border"], ACCENT))
        hdr.addWidget(btn_help)
        right.addLayout(hdr)

        # histogram
        right.addWidget(make_section("Histogram"))
        self.hist_widget = HistogramWidget()
        right.addWidget(self.hist_widget)

        # sliders
        self.int_sliders = {}
        self.int_spins = {}

        # scrollable container for the slider groups
        self.slider_scroll = QScrollArea()
        self.slider_scroll.setObjectName("SliderScroll")
        self.slider_scroll.setWidgetResizable(True)
        self.slider_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.slider_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.slider_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.slider_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        slider_host = QWidget()
        slider_host.setStyleSheet("background: transparent;")
        sliders = QVBoxLayout(slider_host)
        sliders.setContentsMargins(0, 0, 4, 0)
        sliders.setSpacing(4)
        self.slider_scroll.setWidget(slider_host)

        self.sec_light = CollapsibleSection("Light", expanded=True)
        grid_tone = QGridLayout()
        grid_tone.setVerticalSpacing(2)
        grid_tone.setHorizontalSpacing(8)
        row = 0

        # Exposure (float, -5.00 .. +5.00)
        grid_tone.addWidget(QLabel("Exposure"), row, 0)
        self.sb_exp = QDoubleSpinBox()
        self.sb_exp.setRange(-5.00, 5.00)
        self.sb_exp.setDecimals(2)
        self.sb_exp.setSingleStep(0.05)
        self.sb_exp.setValue(0.00)
        self.sb_exp.setAlignment(Qt.AlignmentFlag.AlignRight)
        grid_tone.addWidget(self.sb_exp, row, 1)
        row += 1
        self.s_exp = BipolarSlider(-500, 500, 0)
        self.s_exp.setToolTip("Exposure in stops (-5.00 .. +5.00). Double-click = reset.")
        grid_tone.addWidget(self.s_exp, row, 0, 1, 2)
        row += 1

        tone_defs = [
            ("Contrast",   "Midtone contrast S-curve."),
            ("Highlights", "Recover (-) or boost (+) bright regions."),
            ("Whites",     "White point: extend (+) or pull back (-) the upper end."),
            ("Shadows",    "Lift (+) or deepen (-) dark regions."),
            ("Blacks",     "Black point: lift (+) or crush (-) the lower end."),
        ]
        row = self._add_int_sliders(grid_tone, row, tone_defs)
        self.sec_light.add_layout(grid_tone)
        sliders.addWidget(self.sec_light)

        self.sec_effects = CollapsibleSection("Effects", expanded=False)
        grid_fx = QGridLayout()
        grid_fx.setVerticalSpacing(2)
        grid_fx.setHorizontalSpacing(8)
        fx_defs = [
            ("Clarity", "Midtone local contrast: (+) adds punch, (-) softens. Protects highlights and deep shadows."),
            ("Dehaze",  "Remove (+) or add (-) veiling haze / skyglow (local low-frequency background)."),
        ]
        self._add_int_sliders(grid_fx, 0, fx_defs)
        self.sec_effects.add_layout(grid_fx)
        sliders.addWidget(self.sec_effects)

        self.sec_color = CollapsibleSection("Color", expanded=False)
        grid_color = QGridLayout()
        grid_color.setVerticalSpacing(2)
        grid_color.setHorizontalSpacing(8)
        color_defs = [
            ("Temperature", "White balance: (+) warmer (yellow), (-) cooler (blue)."),
            ("Tint",        "White balance: (+) magenta, (-) green."),
            ("Vibrance",   "Adaptive saturation: boosts muted colours more than already saturated ones."),
            ("Saturation", "Uniform saturation of all colours."),
        ]
        self._add_int_sliders(grid_color, 0, color_defs)
        self.sec_color.add_layout(grid_color)
        sliders.addWidget(self.sec_color)
        sliders.addStretch()
        right.addWidget(self.slider_scroll, 1)

        # signal wiring
        self.s_exp.valueChanged.connect(self._exp_slider_changed)
        self.sb_exp.valueChanged.connect(self._exp_spin_changed)
        for name in self.int_sliders:
            self.int_sliders[name].valueChanged.connect(
                lambda v, n=name: self._int_slider_changed(n, v))
            self.int_spins[name].valueChanged.connect(
                lambda v, n=name: self._int_spin_changed(n, v))

        # buttons
        footer = QHBoxLayout()
        footer.setSpacing(8)
        b_def = QPushButton("Reset")
        b_def.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b_def.clicked.connect(self.set_defaults)
        footer.addWidget(b_def)
        footer.addStretch(1)

        b_cls = QPushButton("Close")
        b_cls.setObjectName("CloseButton")
        b_cls.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b_cls.clicked.connect(self.close)
        footer.addWidget(b_cls)

        b_proc = QPushButton("Apply")
        b_proc.setObjectName("ApplyButton")
        b_proc.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b_proc.clicked.connect(self.apply_process)
        footer.addWidget(b_proc)
        right.addLayout(footer)

        layout.addWidget(panel)

        # ---------------- STATUS BAR (custom, 3 zones: left / center / right) ----------------
        status = QWidget()
        status.setObjectName("StatusBar")
        status.setFixedHeight(26)
        sb = QHBoxLayout(status)
        sb.setContentsMargins(10, 0, 10, 0)
        sb.setSpacing(8)

        self.lbl_info = QLabel("")
        sb.addWidget(self.lbl_info, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.pbar = QProgressBar()
        self.pbar.setRange(0, 0)
        self.pbar.setFixedWidth(120)
        self.pbar.setFixedHeight(4)
        self.pbar.setTextVisible(False)
        self.pbar.hide()
        sb.addWidget(self.pbar, 0, Qt.AlignmentFlag.AlignVCenter)

        self.lbl_zoom = QLabel("Zoom —")
        sb.addWidget(self.lbl_zoom, 1, Qt.AlignmentFlag.AlignCenter)

        lbl_ver = QLabel(f"v{VERSION}   {VERSION_DATE}")
        sb.addWidget(lbl_ver, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        outer.addWidget(status, 0)

    def _add_int_sliders(self, grid, row, defs):
        for name, tip in defs:
            grid.addWidget(QLabel(name), row, 0)
            sb = QSpinBox()
            sb.setRange(-100, 100)
            sb.setValue(0)
            sb.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(sb, row, 1)
            row += 1
            sl = BipolarSlider(-100, 100, 0,
                               gradient=THEME.get("grad_" + name.lower()))
            sl.setToolTip(tip + " Double-click = reset.")
            grid.addWidget(sl, row, 0, 1, 2)
            row += 1
            self.int_sliders[name] = sl
            self.int_spins[name] = sb
        return row

    # ------------------------------------------------- slider/spinbox syncing

    def _exp_slider_changed(self, v):
        if self._updating:
            return
        self._updating = True
        self.sb_exp.setValue(v / 100.0)
        self._updating = False
        self.trigger_update()

    def _exp_spin_changed(self, v):
        if self._updating:
            return
        self._updating = True
        self.s_exp.setValue(int(round(v * 100)))
        self._updating = False
        self.trigger_update()

    def _int_slider_changed(self, name, v):
        if self._updating:
            return
        self._updating = True
        self.int_spins[name].setValue(v)
        self._updating = False
        self.trigger_update()

    def _int_spin_changed(self, name, v):
        if self._updating:
            return
        self._updating = True
        self.int_sliders[name].setValue(v)
        self._updating = False
        self.trigger_update()

    # ------------------------------------------------------------ image I/O

    def make_proxy(self, img):
        if img is None:
            return None
        target = 1600
        h, w = img.shape[:2]
        if max(h, w) <= target:
            return img.copy()
        scale = target / max(h, w)
        return cv2.resize(img, (int(w * scale), int(h * scale)),
                          interpolation=cv2.INTER_AREA)

    def cache_input(self):
        try:
            if not self.siril.connected:
                self.siril.connect()
            with self.siril.image_lock():
                img = self.siril.get_image_pixeldata()
            if img is None:
                QMessageBox.warning(self, "No image",
                                    "No image is loaded in Siril.")
                return

            self.is_mono_source = (img.ndim == 2) or \
                                  (img.ndim == 3 and img.shape[0] == 1)

            img = RawCore.normalize_input(img)
            if img.ndim == 3:
                if img.shape[0] in (1, 3):        # CxHxW -> HxWxC
                    img = img.transpose(1, 2, 0)
                if img.shape[2] == 1:
                    img = img[:, :, 0]
            self.img_full = np.ascontiguousarray(img.astype(np.float32))

            self.img_proxy = self.make_proxy(self.img_full)
            self.comp_proxy = self.img_proxy.copy()

            h, w = self.img_full.shape[:2]
            self.scene.setSceneRect(0, 0, w, h)

            # colour sliders only make sense for RGB
            for name in ("Temperature", "Tint", "Vibrance", "Saturation"):
                self.int_sliders[name].setEnabled(not self.is_mono_source)
                self.int_spins[name].setEnabled(not self.is_mono_source)

            mode = "Mono" if self.is_mono_source else "RGB"
            self.lbl_info.setText(f"{w}x{h} px  •  {mode}  •  32-bit float")

            self.calc_histograms(self.comp_proxy)
            self.update_view()
            self.fit_view()

        except Exception as e:
            print(f"Cache Error: {e}")
            traceback.print_exc()

    # -------------------------------------------------------------- pipeline

    def get_current_params(self):
        return {
            'exposure':   self.sb_exp.value(),
            'contrast':   self.int_spins["Contrast"].value(),
            'highlights': self.int_spins["Highlights"].value(),
            'shadows':    self.int_spins["Shadows"].value(),
            'whites':     self.int_spins["Whites"].value(),
            'blacks':     self.int_spins["Blacks"].value(),
            'temperature': self.int_spins["Temperature"].value(),
            'tint':       self.int_spins["Tint"].value(),
            'vibrance':   self.int_spins["Vibrance"].value(),
            'saturation': self.int_spins["Saturation"].value(),
            'clarity':    self.int_spins["Clarity"].value(),
            'dehaze':     self.int_spins["Dehaze"].value(),
        }

    def trigger_update(self):
        if self.img_proxy is None:
            return
        self.debounce.start()

    def run_preview_logic(self):
        params = self.get_current_params()
        self.comp_proxy = RawCore.process(self.img_proxy, params)
        self.calc_histograms(self.comp_proxy)
        self.update_view()

    def calc_histograms(self, img):
        if img is None:
            return
        bins = 256
        if img.ndim == 2:
            h, _ = np.histogram(img, bins=bins, range=(0, 1))
            self.hist_widget.set_histograms(h)
        else:
            hr, _ = np.histogram(img[:, :, 0], bins=bins, range=(0, 1))
            hg, _ = np.histogram(img[:, :, 1], bins=bins, range=(0, 1))
            hb, _ = np.histogram(img[:, :, 2], bins=bins, range=(0, 1))
            self.hist_widget.set_histograms(hr, hg, hb)

    # ---------------------------------------------------------------- display

    def update_view(self):
        if self.show_original:
            display_data = self.img_proxy
            self.lbl_blink.show()
        else:
            display_data = self.comp_proxy
            self.lbl_blink.hide()

        if display_data is None:
            return

        disp = np.clip(display_data * 255, 0, 255).astype(np.uint8)
        disp = np.flipud(disp)

        if disp.ndim == 2:
            disp = np.stack([disp] * 3, axis=-1)

        h, w, c = disp.shape
        if not disp.flags['C_CONTIGUOUS']:
            disp = np.ascontiguousarray(disp)

        self._current_display_buffer = disp
        qimg = QImage(self._current_display_buffer.data, w, h,
                      c * w, QImage.Format.Format_RGB888)
        self.pix_item.setPixmap(QPixmap.fromImage(qimg))

        full_h, full_w = self.img_full.shape[:2]
        self.pix_item.setTransformOriginPoint(0, 0)
        self.pix_item.setScale(full_w / w)
        self._place_blink()

    def _place_blink(self):
        self.lbl_blink.move(12, 12)

    def update_zoom_label(self):
        z = self.view.transform().m11() * 100.0
        self.lbl_zoom.setText(f"Zoom {z:.0f} %")

    # ----------------------------------------------------------- final apply

    def apply_process(self):
        if self.img_full is None:
            return
        self.setEnabled(False)
        self.lbl_info.setText("Processing…")
        self.pbar.show()

        self.apply_worker = ProcessingWorker(self.img_full,
                                             self.get_current_params())
        self.apply_worker.result_ready.connect(self._on_apply_finished)
        self.apply_worker.finished.connect(self.apply_worker.deleteLater)
        self.apply_worker.start()

    def _on_apply_finished(self, res):
        try:
            if res is not None:
                if res.ndim == 3:
                    out = res.transpose(2, 0, 1)
                else:
                    out = res[np.newaxis, ...] if not self.is_mono_source else res
                    if out.ndim == 2:
                        out = out[np.newaxis, ...]
                with self.siril.image_lock():
                    self.siril.undo_save_state("StarRaw Basic")
                    self.siril.set_image_pixeldata(
                        np.ascontiguousarray(out.astype(np.float32)))
                self.siril.log("StarRaw Basic applied successfully.",
                               LogColor.GREEN)
                self.close()
            else:
                raise Exception("Processing failed in the final apply step.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            traceback.print_exc()
        finally:
            self.pbar.hide()
            self.setEnabled(True)

    # ------------------------------------------------------------------ misc

    def set_defaults(self):
        self._updating = True
        self.s_exp.setValue(0)
        self.sb_exp.setValue(0.00)
        for name in self.int_sliders:
            self.int_sliders[name].setValue(0)
            self.int_spins[name].setValue(0)
        self._updating = False
        self.trigger_update()

    def _push_defaults_temp(self):
        """SPACE held: show sliders at default without recomputing."""
        self._saved_params = self.get_current_params()
        self._updating = True
        self.s_exp.setValue(0)
        self.sb_exp.setValue(0.00)
        for name in self.int_sliders:
            self.int_sliders[name].setValue(0)
            self.int_spins[name].setValue(0)
        self._updating = False

    def _pop_defaults_temp(self):
        """SPACE released: restore the saved slider values."""
        sp = getattr(self, "_saved_params", None)
        if sp is None:
            return
        self._updating = True
        self.sb_exp.setValue(sp['exposure'])
        self.s_exp.setValue(int(round(sp['exposure'] * 100)))
        for name in self.int_sliders:
            v = sp[name.lower()]
            self.int_sliders[name].setValue(v)
            self.int_spins[name].setValue(v)
        self._updating = False
        self._saved_params = None

    def showEvent(self, event):
        QTimer.singleShot(0, self.fit_view)
        QTimer.singleShot(0, self._style_titlebar)
        super().showEvent(event)

    def _style_titlebar(self):
        style_windows_titlebar(self, THEME["win_bg"], THEME["title_color"])

    def closeEvent(self, event):
        """Reset Siril's display stretch on exit: visu 0 65535."""
        if not getattr(self, "_visu_done", False):
            self._visu_done = True
            try:
                if not self.siril.connected:
                    self.siril.connect()
                try:
                    self.siril.cmd("visu", "0", "65535")
                except TypeError:
                    self.siril.cmd("visu 0 65535")
            except Exception as e:
                print(f"visu command failed: {e}")
        super().closeEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.show_original = True
            self._push_defaults_temp()
            self.calc_histograms(self.img_proxy)
            self.update_view()
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.show_original = False
            self._pop_defaults_temp()
            self.calc_histograms(self.comp_proxy)
            self.update_view()
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def resizeEvent(self, event):
        self._place_blink()
        super().resizeEvent(event)

    # zoom
    def zoom_in(self):
        self.view.scale(1.2, 1.2)
        self.update_zoom_label()

    def zoom_out(self):
        self.view.scale(1 / 1.2, 1 / 1.2)
        self.update_zoom_label()

    def zoom_1to1(self):
        self.view.resetTransform()
        self.update_zoom_label()

    def fit_view(self):
        if self.pix_item.pixmap() and not self.pix_item.pixmap().isNull():
            self.view.fitInView(self.pix_item, Qt.AspectRatioMode.KeepAspectRatio)
            self.update_zoom_label()

    def eventFilter(self, source, event):
        if source == self.view.viewport():
            if event.type() == QEvent.Type.Wheel:
                if event.angleDelta().y() > 0:
                    self.zoom_in()
                else:
                    self.zoom_out()
                return True
            if event.type() == QEvent.Type.MouseButtonDblClick:
                self.fit_view()
                return True
        return super().eventFilter(source, event)


# =============================================================================
#  ENTRY POINT
# =============================================================================

def main():
    set_windows_app_id("StarRaw.Basic")
    app = QApplication.instance()
    app = app or QApplication(sys.argv)
    app.setWindowIcon(make_star_icon())
    siril = s.SirilInterface()
    try:
        siril.connect()
    except Exception:
        pass
    gui = StarRawGUI(siril, app)
    gui.show()
    app.exec()


if __name__ == "__main__":
    main()
