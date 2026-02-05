"""Parser for Ableton .asd clip analysis files.

.asd files contain clip-level metadata including:
- Warp markers and timing information
- Loop points
- Sample rate and bit depth
- Transient analysis data
- BPM detection results

Note: Live 12+ uses a different binary format that may require different parsing.
This parser targets Live 9/10/11 .asd files.
"""

import struct
from dataclasses import dataclass, field
from pathlib import Path

from ..utils.logging import get_logger


@dataclass
class WarpMarker:
    """A warp marker in an audio clip."""

    beat_time: float = 0.0  # Position in beats
    sample_time: float = 0.0  # Position in samples/seconds

    @property
    def stretch_ratio(self) -> float:
        """Calculate the stretch ratio at this marker."""
        if self.sample_time > 0:
            return self.beat_time / self.sample_time
        return 1.0


@dataclass
class LoopInfo:
    """Loop information for a clip."""

    loop_start: float = 0.0
    loop_end: float = 0.0
    loop_on: bool = False

    @property
    def loop_length(self) -> float:
        """Calculate loop length in beats."""
        return self.loop_end - self.loop_start


@dataclass
class ClipAnalysisData:
    """Extracted analysis data from an .asd file."""

    # File info
    file_path: str | None = None
    sample_rate: float = 44100.0

    # Warp information
    warp_markers: list[WarpMarker] = field(default_factory=list)
    warp_mode: str = "beats"  # beats, tones, texture, repitch, complex, complex_pro

    # Loop information
    loop_info: LoopInfo | None = None

    # Timing
    original_bpm: float | None = None
    detected_bpm: float | None = None
    start_marker: float = 0.0
    end_marker: float = 0.0

    # Transient data
    transient_count: int = 0
    transients: list[float] = field(default_factory=list)  # Transient positions

    # Metadata flags
    is_warped: bool = False
    hide_warp_markers: bool = False

    # Quality metrics (for ML features)
    @property
    def warp_marker_count(self) -> int:
        """Number of warp markers."""
        return len(self.warp_markers)

    @property
    def avg_stretch_ratio(self) -> float:
        """Average stretch ratio across all warp markers."""
        if not self.warp_markers:
            return 1.0
        ratios = [m.stretch_ratio for m in self.warp_markers if m.stretch_ratio > 0]
        return sum(ratios) / len(ratios) if ratios else 1.0

    @property
    def clip_duration(self) -> float:
        """Duration of the clip region."""
        return self.end_marker - self.start_marker


class ASDParser:
    """Parser for Ableton .asd clip analysis files.

    The .asd format is a binary format that stores clip analysis data
    including warp markers, transients, and timing information.

    Note: This is a best-effort parser based on reverse engineering.
    Not all fields may be correctly interpreted across all Live versions.
    """

    # Warp mode constants
    WARP_MODES = {
        0: "beats",
        1: "tones",
        2: "texture",
        3: "repitch",
        4: "complex",
        5: "complex_pro",
    }

    def __init__(self):
        """Initialize the parser."""
        self.logger = get_logger(__name__)
        self._cache: dict[str, ClipAnalysisData] = {}

    def parse(self, asd_path: Path) -> ClipAnalysisData | None:
        """Parse an .asd file and extract clip analysis data.

        Args:
            asd_path: Path to the .asd file.

        Returns:
            ClipAnalysisData object with extracted data, or None if parsing fails.
        """
        if not asd_path.exists():
            return None

        # Check cache
        cache_key = f"{asd_path}_{asd_path.stat().st_mtime}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            with open(asd_path, "rb") as f:
                data = f.read()

            result = self._parse_asd_data(data)
            result.file_path = str(asd_path)

            # Cache result
            self._cache[cache_key] = result

            return result

        except Exception as e:
            self.logger.error(f"Error parsing ASD file {asd_path}: {e}", exc_info=True)
            return None

    def _parse_asd_data(self, data: bytes) -> ClipAnalysisData:
        """Parse the binary ASD data.

        The ASD format appears to be:
        - Header with version info
        - Warp marker section
        - Transient section
        - Loop/timing section
        """
        result = ClipAnalysisData()

        if len(data) < 8:
            return result

        try:
            # Try to find and parse warp markers
            warp_markers = self._extract_warp_markers(data)
            result.warp_markers = warp_markers
            result.is_warped = len(warp_markers) > 0

            # Try to extract BPM information
            bpm = self._extract_bpm(data)
            if bpm:
                result.detected_bpm = bpm
                result.original_bpm = bpm

            # Try to extract transients
            transients = self._extract_transients(data)
            result.transients = transients
            result.transient_count = len(transients)

            # Try to extract loop info
            loop_info = self._extract_loop_info(data)
            if loop_info:
                result.loop_info = loop_info

            # Try to extract sample rate
            sample_rate = self._extract_sample_rate(data)
            if sample_rate:
                result.sample_rate = sample_rate

        except Exception as e:
            self.logger.error(f"Error parsing ASD data structure: {e}", exc_info=True)

        return result

    def _extract_warp_markers(self, data: bytes) -> list[WarpMarker]:
        """Extract warp markers from ASD data.

        Warp markers are stored as pairs of double values (beat_time, sample_time).
        We look for patterns that suggest warp marker data.
        """
        markers = []

        # Search for potential warp marker patterns
        # Warp markers typically start after a specific header
        # and consist of pairs of 8-byte doubles

        # Look for common marker pattern locations
        search_offsets = [0x40, 0x50, 0x60, 0x80, 0x100]

        for offset in search_offsets:
            if offset + 16 <= len(data):
                try:
                    # Try to read as two doubles
                    beat_time = struct.unpack_from("<d", data, offset)[0]
                    sample_time = struct.unpack_from("<d", data, offset + 8)[0]

                    # Validate that these look like reasonable marker values
                    if (
                        0 <= beat_time < 100000
                        and 0 <= sample_time < 100000000
                        and beat_time > 0
                        or sample_time > 0
                    ):

                        # Found a potential marker, try to read more
                        pos = offset
                        while pos + 16 <= len(data):
                            try:
                                bt = struct.unpack_from("<d", data, pos)[0]
                                st = struct.unpack_from("<d", data, pos + 8)[0]

                                # Validate values
                                if not (0 <= bt < 100000 and 0 <= st < 100000000):
                                    break

                                if bt > 0 or st > 0:
                                    markers.append(WarpMarker(beat_time=bt, sample_time=st))

                                pos += 16

                                # Stop if we've read too many or values are decreasing
                                if len(markers) > 1000:
                                    break

                            except struct.error:
                                break

                        if markers:
                            break

                except struct.error:
                    continue

        return markers

    def _extract_bpm(self, data: bytes) -> float | None:
        """Extract BPM value from ASD data.

        BPM is typically stored as a double somewhere in the file.
        Common BPM values are 60-200, so we look for doubles in that range.
        """
        # Search through the file for double values that look like BPM
        for i in range(0, min(len(data) - 8, 500), 4):
            try:
                val = struct.unpack_from("<d", data, i)[0]
                # Check if it looks like a reasonable BPM
                if 40.0 <= val <= 300.0:
                    # Additional check: BPM often appears after certain markers
                    # This is a heuristic - may need refinement
                    return float(round(val, 2))
            except struct.error:
                continue

        return None

    def _extract_transients(self, data: bytes) -> list[float]:
        """Extract transient positions from ASD data.

        Transients are detected sample positions stored as an array.
        """
        transients: list[float] = []

        # Transients are harder to locate without more format knowledge
        # This is a placeholder for future implementation

        return transients

    def _extract_loop_info(self, data: bytes) -> LoopInfo | None:
        """Extract loop information from ASD data."""
        # Loop info location varies by version
        # This is a placeholder for future implementation
        return None

    def _extract_sample_rate(self, data: bytes) -> float | None:
        """Extract sample rate from ASD data."""
        # Common sample rates to look for
        common_rates = [44100.0, 48000.0, 88200.0, 96000.0]

        for i in range(0, min(len(data) - 8, 200), 4):
            try:
                val = struct.unpack_from("<d", data, i)[0]
                if val in common_rates:
                    return float(val)
            except struct.error:
                continue

        return None

    def clear_cache(self):
        """Clear the parser cache."""
        self._cache.clear()

    def generate_feature_vector(self, analysis: ClipAnalysisData) -> list[float]:
        """Generate a feature vector from clip analysis data.

        Args:
            analysis: ClipAnalysisData object to vectorize.

        Returns:
            List of float values representing the clip features.
        """
        return [
            float(analysis.sample_rate),
            float(analysis.warp_marker_count),
            float(analysis.avg_stretch_ratio),
            float(analysis.detected_bpm or 0.0),
            float(analysis.transient_count),
            float(analysis.clip_duration),
            1.0 if analysis.is_warped else 0.0,
            1.0 if (analysis.loop_info and analysis.loop_info.loop_on) else 0.0,
            float(analysis.loop_info.loop_length if analysis.loop_info else 0.0),
        ]

    @staticmethod
    def get_feature_names() -> list[str]:
        """Get feature names for the clip analysis feature vector."""
        return [
            "sample_rate",
            "warp_marker_count",
            "avg_stretch_ratio",
            "detected_bpm",
            "transient_count",
            "clip_duration",
            "is_warped",
            "is_looping",
            "loop_length",
        ]


def find_asd_files(project_dir: Path) -> list[Path]:
    """Find all .asd files in a project directory.

    ASD files are typically stored in the project's Ableton Project Info folder
    or alongside audio files.

    Args:
        project_dir: Path to the Ableton project directory.

    Returns:
        List of paths to .asd files.
    """
    asd_files: list[Path] = []

    # Look in common locations
    search_patterns = ["**/*.asd", "Ableton Project Info/*.asd", "Samples/**/*.asd"]

    for pattern in search_patterns:
        asd_files.extend(project_dir.glob(pattern))

    # Remove duplicates
    return list(set(asd_files))
