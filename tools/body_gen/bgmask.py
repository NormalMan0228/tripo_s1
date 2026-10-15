"""Foreground mask for studio renders on white or light-grey backgrounds.

Image models often paint a faint grey gradient or a contact shadow instead of pure
white. A plain "darker than 235" test then counts that background as body, which
inflates silhouettes and breaks alignment and symmetry numbers. Here, near-neutral
light pixels (low saturation, bright) that connect to the image border are treated
as background; bright pixels inside the creature (teeth, highlights) stay.
"""
import numpy as np
from scipy import ndimage


def fg_mask(rgb, thr=235, sat=22, light=165, bg_tol=14):
    a = np.asarray(rgb).astype(np.int16)
    lo, hi = a.min(axis=2), a.max(axis=2)
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    bg = np.median(border, axis=0)
    if bg.min() < 225 and bg.max() - bg.min() < 20:
        # Flat grey background (used for white or pale monsters): only pixels close to
        # that grey are background, so white fur or ice touching it is kept.
        # The backdrop is flat; fur and ice shading near the same grey has texture, so also
        # require a very low local variation (5x5 standard deviation of brightness).
        lum = a.mean(axis=2).astype(np.float32)
        mean = ndimage.uniform_filter(lum, 5)
        std = np.sqrt(np.maximum(ndimage.uniform_filter(lum * lum, 5) - mean * mean, 0))
        maybe_bg = (np.abs(a - bg).max(axis=2) < 2 * bg_tol) & (hi - lo < sat) & (std < 2.5)
        maybe_bg = ndimage.binary_opening(maybe_bg, iterations=1, border_value=1)
        lab, _ = ndimage.label(maybe_bg)
        edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
        fg = ~np.isin(lab, edge[edge > 0])
        gap = (np.abs(a - bg).max(axis=2) < 6) & (std < 1.0)  # real backdrop seen through a gap
        hl, n = ndimage.label(gap & fg)
        if n:  # enclosed grey gaps (between legs, arm and body)
            sizes = ndimage.sum(np.ones_like(hl), hl, index=np.arange(1, n + 1))
            fg &= ~np.isin(hl, np.arange(1, n + 1)[sizes > 0.0015 * fg.size])
        return fg
    maybe_bg = (lo >= thr) | ((hi - lo < sat) & (lo > light))
    # Off-white backgrounds (warm or cool tints): also accept pixels close to the
    # border's median colour, so a tinted floor band is not taken for the body.
    if bg.min() > 200:
        maybe_bg |= (np.abs(a - bg).max(axis=2) < bg_tol) & (lo > 200)
    lab, _ = ndimage.label(maybe_bg)
    edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    edge = edge[edge > 0]
    fg = ~np.isin(lab, edge)
    if bg.min() > 200:
        # Enclosed gaps (between the legs, arm and body) painted in the background
        # colour are background too; small specks (eye glints) stay.
        close = fg & (np.abs(a - bg).max(axis=2) < bg_tol) & (lo > 200)
        hl, n = ndimage.label(close)
        if n:
            sizes = ndimage.sum(np.ones_like(hl), hl, index=np.arange(1, n + 1))
            big = np.arange(1, n + 1)[sizes > 0.0015 * close.size]
            fg &= ~np.isin(hl, big)
    return fg


def fg_mask_strict(rgb, sat=8, foot_band=0.06, **kw):
    """Like fg_mask, but with a stricter saturation limit (keeps pale stone/skin
    highlights) everywhere except the lowest foot_band of the silhouette, where the
    default limit still removes the grey contact shadow."""
    loose = fg_mask(rgb, **kw)
    strict = fg_mask(rgb, sat=sat, **kw)
    ys = np.where(loose.any(axis=1))[0]
    if len(ys) == 0:
        return strict
    cut = int(ys[-1] - foot_band * (ys[-1] - ys[0]))
    strict[cut:] = loose[cut:]
    return strict
