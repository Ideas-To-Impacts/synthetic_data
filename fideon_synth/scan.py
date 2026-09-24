"""
Scanner profiles: turn a digital PDF into the thing that actually arrives.

Each page is rasterised, degraded and re-embedded as an image, leaving no
text layer at all. What varies is *how* it was degraded. A corpus where every
page came through one profile measures one thing; these five are the
different bad days a document has on its way into a pipeline:

    office_flatbed   a clean office scanner - light grain, square on the glass
    fax_bitonal      200 dpi, thresholded to black and white, speckled
    phone_photo      shot on a phone: uneven light, a shadow, a colour cast
    photocopy        a copy of a copy - blotchy, toner streaks, dust
    old_flatbed      visibly skewed, over-compressed, warm paper

They are ordered roughly by how hard they are to read. Handing them out one
per document covers the range instead of sampling one point of it five times.

Everything is seeded from the document key plus the page number, so a rerun
produces the same grain in the same places. A scanned page that changed
between runs would make a regression impossible to see.

    from fideon_synth.scan import scan_pdf, PROFILES, by_key

    stats = scan_pdf("digital.pdf", "scanned.pdf", by_key("fax_bitonal"),
                     seed="df_001")
    stats["words"]      # 0 - there is nothing left to extract

Profiles are ordinary dataclasses. Build your own when a carrier's documents
arrive in a way these do not cover:

    Profile(key="duplex_bleed", label="duplex, show-through",
            dpi=220, jpeg_quality=70, gradient=0.1, noise=(8, 14))
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field

import fitz
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


@dataclass
class Profile:
    key: str
    label: str
    dpi: int = 200
    jpeg_quality: int = 70
    grayscale: bool = True
    bitonal: bool = False
    skew: tuple = (-0.4, 0.4)          # degrees
    blur: tuple = (0.3, 0.6)
    noise: tuple = (3.0, 7.0)          # gaussian sigma
    speckle: float = 0.0               # fraction of pixels flipped
    dust: int = 0                      # number of specks
    streaks: int = 0                   # vertical toner bands
    gradient: float = 0.0              # uneven illumination, 0-1
    vignette: float = 0.0              # corner falloff, 0-1
    shadow: float = 0.0                # one soft edge shadow, 0-1
    tint: tuple = field(default=(1.0, 1.0, 1.0))   # per-channel gain
    contrast: tuple = (0.98, 1.06)
    brightness: tuple = (0.98, 1.04)


PROFILES = [
    Profile(
        key="high_quality",
        label="high-quality scan, 400 dpi",
        dpi=400, jpeg_quality=98,
        skew=(0.0, 0.0), blur=(0.0, 0.0), noise=(0.0, 0.0),
        contrast=(1.0, 1.0), brightness=(1.0, 1.0),
    ),
    Profile(
        key="office_flatbed",
        label="office flatbed, 300 dpi",
        dpi=300, jpeg_quality=86,
        skew=(-0.15, 0.15), blur=(0.25, 0.45), noise=(2.0, 4.5),
        dust=12,
    ),
    Profile(
        key="fax_bitonal",
        label="fax, 200 dpi bitonal",
        dpi=200, jpeg_quality=60,
        bitonal=True,
        skew=(-0.7, 0.7), blur=(0.45, 0.8), noise=(6.0, 11.0),
        speckle=0.0012, dust=40,
        contrast=(1.15, 1.30),
    ),
    Profile(
        key="phone_photo",
        label="phone photo, uneven light",
        dpi=260, jpeg_quality=72,
        grayscale=False,
        skew=(-1.4, 1.4), blur=(0.5, 0.9), noise=(5.0, 9.0),
        gradient=0.30, vignette=0.22, shadow=0.26,
        tint=(1.02, 1.00, 0.94),
        brightness=(0.94, 1.02), contrast=(0.92, 1.02),
    ),
    Profile(
        key="photocopy",
        label="photocopy, blotchy with toner streaks",
        dpi=240, jpeg_quality=66,
        skew=(-0.6, 0.6), blur=(0.5, 0.85), noise=(6.0, 10.0),
        speckle=0.0006, dust=55, streaks=4, gradient=0.16,
        contrast=(1.06, 1.18), brightness=(0.90, 0.98),
    ),
    Profile(
        key="old_flatbed",
        label="older flatbed, skewed and over-compressed",
        dpi=180, jpeg_quality=44,
        grayscale=False,
        skew=(-1.8, -0.9), blur=(0.6, 1.0), noise=(7.0, 12.0),
        dust=28, vignette=0.12,
        tint=(1.04, 1.01, 0.90),
        contrast=(0.94, 1.04), brightness=(0.96, 1.03),
    ),
]


def _rng(*parts):
    """A generator seeded by content, so the same page degrades the same way."""
    digest = hashlib.sha256("::".join(str(p) for p in parts).encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "big"))


def _uniform(rng, span):
    lo, hi = span
    return float(rng.uniform(lo, hi))


# ── the individual artefacts ────────────────────────────────────────────────

def _illumination(arr, rng, strength):
    """A smooth bright-to-dim wash, the way a page lit from one side reads."""
    h, w = arr.shape[:2]
    ax, ay = rng.uniform(-1, 1), rng.uniform(-1, 1)
    gx = np.linspace(-1, 1, w)[None, :]
    gy = np.linspace(-1, 1, h)[:, None]
    field_ = 1.0 - strength * (0.5 + 0.5 * (ax * gx + ay * gy))
    return arr * field_[..., None]


def _vignette(arr, strength):
    h, w = arr.shape[:2]
    gx = np.linspace(-1, 1, w)[None, :]
    gy = np.linspace(-1, 1, h)[:, None]
    r = np.sqrt(gx ** 2 + gy ** 2) / np.sqrt(2.0)
    return arr * (1.0 - strength * r ** 2)[..., None]


def _shadow(arr, rng, strength):
    """One soft band along an edge - a hand, or the phone itself."""
    h, w = arr.shape[:2]
    vertical = bool(rng.integers(0, 2))
    n = w if vertical else h
    width = int(n * rng.uniform(0.12, 0.26))
    ramp = np.linspace(0.0, 1.0, max(width, 2))
    band = np.ones(n)
    if rng.integers(0, 2):
        band[:width] = 1.0 - strength * (1.0 - ramp)
    else:
        band[n - width:] = 1.0 - strength * ramp
    mask = band[None, :] if vertical else band[:, None]
    return arr * mask[..., None]


def _streaks(arr, rng, count):
    """Vertical toner bands, the signature of a tired copier drum."""
    h, w = arr.shape[:2]
    for _ in range(count):
        x = int(rng.integers(0, w))
        width = int(rng.integers(1, 5))
        gain = float(rng.uniform(0.82, 0.96))
        arr[:, x:x + width] *= gain
    return arr


def _dust(arr, rng, count):
    h, w = arr.shape[:2]
    for _ in range(count):
        y, x = int(rng.integers(0, h)), int(rng.integers(0, w))
        r = int(rng.integers(1, 4))
        dark = rng.random() < 0.8
        arr[max(y - r, 0):y + r, max(x - r, 0):x + r] = 30 if dark else 250
    return arr


def _speckle(arr, rng, fraction):
    h, w = arr.shape[:2]
    n = int(h * w * fraction)
    if n <= 0:
        return arr
    ys = rng.integers(0, h, n)
    xs = rng.integers(0, w, n)
    vals = np.where(rng.random(n) < 0.75, 0, 255)
    arr[ys, xs] = vals[:, None]
    return arr


# ── one page ────────────────────────────────────────────────────────────────

def _degrade(img, p, rng):
    if p.grayscale:
        img = img.convert("L").convert("RGB")

    img = ImageEnhance.Brightness(img).enhance(_uniform(rng, p.brightness))
    img = ImageEnhance.Contrast(img).enhance(_uniform(rng, p.contrast))

    # skew before blur: a rotated hard edge should be softened by the optics,
    # not stay crisp while everything around it goes soft
    img = img.rotate(_uniform(rng, p.skew), resample=Image.BICUBIC,
                     expand=False, fillcolor=(255, 255, 255))
    img = img.filter(ImageFilter.GaussianBlur(_uniform(rng, p.blur)))

    arr = np.asarray(img).astype(np.float32)
    if p.gradient:
        arr = _illumination(arr, rng, p.gradient)
    if p.vignette:
        arr = _vignette(arr, p.vignette)
    if p.shadow:
        arr = _shadow(arr, rng, p.shadow)
    if p.streaks:
        arr = _streaks(arr, rng, p.streaks)
    if p.tint != (1.0, 1.0, 1.0):
        arr = arr * np.asarray(p.tint, dtype=np.float32)[None, None, :]

    arr = arr + rng.normal(0.0, _uniform(rng, p.noise), arr.shape)
    arr = np.clip(arr, 0, 255)

    if p.dust:
        arr = _dust(arr, rng, p.dust)
    if p.speckle:
        arr = _speckle(arr, rng, p.speckle)

    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, "RGB")

    if p.bitonal:
        # threshold last, so every artefact above is baked into what survives
        img = img.convert("L").point(lambda v: 255 if v > 176 else 0, mode="1")
        img = img.convert("RGB")
    return img


def scan_pdf(src, dst, profile, seed):
    """Rasterise, degrade, re-embed. The result has no text layer.

    Page geometry is preserved exactly - a scanned page that came back a
    different size would break any coordinate a downstream reader derives.
    """
    fitz.TOOLS.mupdf_display_errors(False)
    src_doc = fitz.open(str(src))
    out = fitz.open()
    for i, page in enumerate(src_doc, 1):
        rng = _rng(seed, profile.key, i)
        pix = page.get_pixmap(dpi=profile.dpi, colorspace=fitz.csRGB)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        img = _degrade(img, profile, rng)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=profile.jpeg_quality,
                 optimize=True)
        new = out.new_page(width=page.rect.width, height=page.rect.height)
        new.insert_image(new.rect, stream=buf.getvalue())

    pages = out.page_count
    out.save(str(dst), deflate=True, garbage=4)
    out.close()
    src_doc.close()

    # the whole point is that there is nothing left to extract
    check = fitz.open(str(dst))
    words = sum(len(pg.get_text("words")) for pg in check)
    size_kb = len(check.tobytes()) / 1024.0
    check.close()
    return {"pages": pages, "words": words, "kb": size_kb,
            "profile": profile.label, "key": profile.key}


def by_key(key):
    """Look a profile up by name, listing the alternatives when it is wrong."""
    for profile in PROFILES:
        if profile.key == key:
            return profile
    raise KeyError("No scanner profile %r. Available: %s"
                   % (key, ", ".join(p.key for p in PROFILES)))
