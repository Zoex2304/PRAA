
from __future__ import annotations

import logging
import math

import numpy as np

from src.domain.config.constants import (
    SPECTRUM_DB_FLOOR,
    SPECTRUM_DB_CEILING,
    SPECTRUM_SMOOTHING_ATTACK,
    SPECTRUM_SMOOTHING_DECAY,
    SPECTRUM_MIN_MAGNITUDE,
)

logger = logging.getLogger(__name__)


class SpectrumAnalyzer:

    DB_FLOOR = SPECTRUM_DB_FLOOR
    DB_CEILING = SPECTRUM_DB_CEILING
    SMOOTHING_ATTACK = SPECTRUM_SMOOTHING_ATTACK
    SMOOTHING_DECAY = SPECTRUM_SMOOTHING_DECAY
    MIN_MAGNITUDE = SPECTRUM_MIN_MAGNITUDE

    def __init__(self, num_bands: int = 16) -> None:
        self._num_bands = num_bands
        self._prev_magnitudes = np.zeros(num_bands)
        self._window_cache: dict[int, np.ndarray] = {}  # block_size -> window
        self._band_edges_cache: dict[tuple[int, int], list[int]] = {}
        self._active = False

    def set_active(self, active: bool) -> None:
        self._active = active
        if not active:
            # Don't reset immediately — let decay animation handle it
            pass

    @property
    def bars(self) -> list[float]:
        return self._prev_magnitudes.tolist()

    def update(self, block: np.ndarray | None = None, samplerate: int = 24000) -> list[float]:
        if block is None or not self._active:
            # Decay to zero
            self._prev_magnitudes *= self.SMOOTHING_DECAY
            # Snap to zero when very small
            self._prev_magnitudes[self._prev_magnitudes < 0.01] = 0.0
            return self._prev_magnitudes.tolist()

        try:
            # Convert to mono if multi-channel
            samples = self._to_mono(block)

            if len(samples) < 4:
                return self._prev_magnitudes.tolist()

            # Apply Hanning window
            window = self._get_window(len(samples))
            windowed = samples * window

            # FFT
            spectrum = np.fft.rfft(windowed)
            magnitudes = np.abs(spectrum)

            # Group into logarithmic frequency bands
            band_magnitudes = self._bin_to_bands(magnitudes, samplerate)

            # Convert to dB scale
            db_values = self._to_db(band_magnitudes)

            # Normalize to 0.0–1.0
            normalized = self._normalize(db_values)

            # Smooth with previous frame
            smoothed = self._smooth(normalized)

            self._prev_magnitudes = smoothed
            return smoothed.tolist()

        except Exception:
            logger.debug("Spectrum analysis error", exc_info=True)
            return self._prev_magnitudes.tolist()



    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_mono(block: np.ndarray) -> np.ndarray:
        if block.ndim == 1:
            return block
        return block.mean(axis=1)

    def _get_window(self, size: int) -> np.ndarray:
        if size not in self._window_cache:
            self._window_cache[size] = np.hanning(size).astype(np.float32)
        return self._window_cache[size]

    def _bin_to_bands(self, magnitudes: np.ndarray, samplerate: int) -> np.ndarray:
        n_fft = len(magnitudes)
        cache_key = (n_fft, samplerate)

        if cache_key not in self._band_edges_cache:
            # Compute logarithmic band edges
            min_freq = 60.0     # Hz — skip sub-bass (inaudible in speech)
            max_freq = min(samplerate / 2, 8000.0)  # Nyquist or 8kHz (speech range)

            # Logarithmic spacing
            log_min = math.log10(max(min_freq, 1.0))
            log_max = math.log10(max(max_freq, min_freq + 1.0))

            edges = []
            for i in range(self._num_bands + 1):
                freq = 10 ** (log_min + (log_max - log_min) * i / self._num_bands)
                bin_idx = int(freq * n_fft * 2 / samplerate)
                bin_idx = min(bin_idx, n_fft - 1)
                edges.append(bin_idx)

            self._band_edges_cache[cache_key] = edges

        edges = self._band_edges_cache[cache_key]
        bands = np.zeros(self._num_bands)

        for i in range(self._num_bands):
            start = edges[i]
            end = max(edges[i + 1], start + 1)  # At least 1 bin per band
            end = min(end, len(magnitudes))

            if start < end:
                # Use RMS of magnitudes in this band for smoother response
                bands[i] = np.sqrt(np.mean(magnitudes[start:end] ** 2))

        return bands

    def _to_db(self, magnitudes: np.ndarray) -> np.ndarray:
        safe = np.maximum(magnitudes, self.MIN_MAGNITUDE)
        return 20.0 * np.log10(safe)

    def _normalize(self, db_values: np.ndarray) -> np.ndarray:
        clamped = np.clip(db_values, self.DB_FLOOR, self.DB_CEILING)
        return (clamped - self.DB_FLOOR) / (self.DB_CEILING - self.DB_FLOOR)

    def _smooth(self, current: np.ndarray) -> np.ndarray:
        result = np.empty_like(current)
        for i in range(len(current)):
            if current[i] > self._prev_magnitudes[i]:
                # Rising — use attack speed
                alpha = 1.0 - self.SMOOTHING_ATTACK
                result[i] = self._prev_magnitudes[i] + alpha * (current[i] - self._prev_magnitudes[i])
            else:
                # Falling — use decay speed
                alpha = self.SMOOTHING_DECAY
                result[i] = self._prev_magnitudes[i] + alpha * (current[i] - self._prev_magnitudes[i])
        return result

    def reset(self) -> None:
        self._prev_magnitudes = np.zeros(self._num_bands)
        self._active = False
