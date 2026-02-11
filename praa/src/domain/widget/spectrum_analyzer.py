"""
Widget Domain — Real-Time Audio Spectrum Analyzer

Computes frequency band magnitudes from raw audio samples using FFT.
Replaces the fake random spectrum with actual audio-reactive visualization.

SINGLE RESPONSIBILITY: Convert raw PCM audio blocks into normalized
frequency band magnitudes suitable for bar chart visualization.

ALGORITHM:
1. Apply Hanning window to avoid spectral leakage
2. Compute FFT via numpy.fft.rfft
3. Convert to magnitude (absolute value)
4. Group into logarithmically-spaced frequency bands
5. Convert to decibel scale with floor
6. Normalize to 0.0–1.0 range
7. Apply exponential smoothing with previous frame
"""

from __future__ import annotations

import logging
import math

import numpy as np

logger = logging.getLogger(__name__)


class SpectrumAnalyzer:
    """
    Real-time audio spectrum analyzer using FFT.

    Accepts raw PCM audio blocks and produces smoothed frequency band
    magnitudes for visualization. Uses logarithmic frequency binning
    to match human perception (low frequencies get fewer bars,
    high frequencies get more detail where speech formants live).
    """

    # Tuning parameters
    DB_FLOOR = -60.0           # Minimum dB level (silence threshold)
    DB_CEILING = 0.0           # Maximum dB level
    SMOOTHING_ATTACK = 0.4     # How fast bars rise (0=instant, 1=no change)
    SMOOTHING_DECAY = 0.15     # How fast bars fall (slower for smooth decay)
    MIN_MAGNITUDE = 1e-10      # Avoid log(0)

    def __init__(self, num_bands: int = 16) -> None:
        """
        Args:
            num_bands: Number of frequency bands (bars) to produce.
        """
        self._num_bands = num_bands
        self._prev_magnitudes = np.zeros(num_bands)
        self._window_cache: dict[int, np.ndarray] = {}  # block_size -> window
        self._band_edges_cache: dict[tuple[int, int], list[int]] = {}
        self._active = False

    def set_active(self, active: bool) -> None:
        """Enable/disable spectrum analysis."""
        self._active = active
        if not active:
            # Don't reset immediately — let decay animation handle it
            pass

    @property
    def bars(self) -> list[float]:
        """Current bar heights (0.0 to 1.0)."""
        return self._prev_magnitudes.tolist()

    def update(self, block: np.ndarray | None = None, samplerate: int = 24000) -> list[float]:
        """
        Compute frequency band magnitudes from an audio block.

        Args:
            block: Raw PCM samples as numpy array (float32, mono or multi-channel).
                   None if no audio is playing.
            samplerate: Audio sample rate in Hz.

        Returns:
            List of normalized bar heights (0.0 to 1.0), one per band.
        """
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

    def draw(self, canvas, width: int, height: int, colors: list[str]) -> None:
        """
        Draw spectrum bars on a canvas.

        Args:
            canvas: tkinter Canvas widget.
            width: Canvas width in pixels.
            height: Canvas height in pixels.
            colors: List of color strings for bars.
        """
        canvas.delete("all")
        bars = self._prev_magnitudes
        num_bars = len(bars)

        bar_width = max(2, (width - num_bars * 2) // num_bars)
        gap = 2

        for i in range(num_bars):
            bar_h = max(2, bars[i] * (height - 4))
            x = i * (bar_width + gap) + gap
            y = height - 2
            color = colors[i % len(colors)]

            canvas.create_rectangle(
                x, y - bar_h, x + bar_width, y,
                fill=color, outline="", width=0,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_mono(block: np.ndarray) -> np.ndarray:
        """Convert multi-channel audio to mono by averaging channels."""
        if block.ndim == 1:
            return block
        return block.mean(axis=1)

    def _get_window(self, size: int) -> np.ndarray:
        """Get cached Hanning window of given size."""
        if size not in self._window_cache:
            self._window_cache[size] = np.hanning(size).astype(np.float32)
        return self._window_cache[size]

    def _bin_to_bands(self, magnitudes: np.ndarray, samplerate: int) -> np.ndarray:
        """
        Group FFT bins into logarithmically-spaced frequency bands.

        Logarithmic spacing matches human frequency perception:
        - Band 0: ~20-60 Hz (bass)
        - Band N: ~4000-8000 Hz (sibilants, high detail)
        """
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
        """Convert linear magnitudes to decibel scale."""
        safe = np.maximum(magnitudes, self.MIN_MAGNITUDE)
        return 20.0 * np.log10(safe)

    def _normalize(self, db_values: np.ndarray) -> np.ndarray:
        """Normalize dB values to 0.0–1.0 range."""
        clamped = np.clip(db_values, self.DB_FLOOR, self.DB_CEILING)
        return (clamped - self.DB_FLOOR) / (self.DB_CEILING - self.DB_FLOOR)

    def _smooth(self, current: np.ndarray) -> np.ndarray:
        """Apply asymmetric exponential smoothing (fast attack, slow decay)."""
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
        """Reset all state."""
        self._prev_magnitudes = np.zeros(self._num_bands)
        self._active = False
