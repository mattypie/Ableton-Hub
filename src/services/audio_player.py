"""Audio playback service for previewing exports."""

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer


class AudioPlayer(QObject):
    """Audio player service for previewing audio files.

    Uses Qt's QMediaPlayer for cross-platform audio playback.
    Supports WAV, AIFF, MP3, FLAC, and OGG formats.
    """

    # Signals
    playback_started = pyqtSignal(str)  # File path
    playback_stopped = pyqtSignal()
    playback_paused = pyqtSignal()
    playback_finished = pyqtSignal()
    position_changed = pyqtSignal(int)  # Position in milliseconds
    duration_changed = pyqtSignal(int)  # Duration in milliseconds
    error_occurred = pyqtSignal(str)  # Error message

    # Singleton instance
    _instance: Optional["AudioPlayer"] = None

    @classmethod
    def instance(cls) -> "AudioPlayer":
        """Get the singleton instance of AudioPlayer."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

        self._current_file: str | None = None
        self._is_playing = False

        # Create media player and audio output
        self._player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._player.setAudioOutput(self._audio_output)

        # Set default volume (0.0 to 1.0)
        self._audio_output.setVolume(0.7)

        # Connect signals
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.errorOccurred.connect(self._on_error)

    @property
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        return self._is_playing

    @property
    def current_file(self) -> str | None:
        """Get the currently loaded file path."""
        return self._current_file

    @property
    def volume(self) -> float:
        """Get the current volume (0.0 to 1.0)."""
        return self._audio_output.volume()

    @volume.setter
    def volume(self, value: float) -> None:
        """Set the volume (0.0 to 1.0)."""
        self._audio_output.setVolume(max(0.0, min(1.0, value)))

    @property
    def position(self) -> int:
        """Get the current playback position in milliseconds."""
        return self._player.position()

    @property
    def duration(self) -> int:
        """Get the total duration in milliseconds."""
        return self._player.duration()

    def load(self, file_path: str) -> bool:
        """Load an audio file for playback.

        Args:
            file_path: Path to the audio file.

        Returns:
            True if the file was loaded successfully.
        """
        path = Path(file_path)

        if not path.exists():
            self.error_occurred.emit(f"File not found: {file_path}")
            return False

        # Check supported formats
        supported_extensions = {".wav", ".aiff", ".aif", ".mp3", ".flac", ".ogg", ".m4a"}
        if path.suffix.lower() not in supported_extensions:
            self.error_occurred.emit(f"Unsupported format: {path.suffix}")
            return False

        # Stop current playback
        self.stop()

        # Load new file
        self._current_file = str(path)
        self._player.setSource(QUrl.fromLocalFile(str(path)))

        return True

    def play(self, file_path: str | None = None) -> bool:
        """Start or resume playback.

        Args:
            file_path: Optional path to load and play. If None, resumes current file.

        Returns:
            True if playback started successfully.
        """
        if file_path:
            if not self.load(file_path):
                return False

        if not self._current_file:
            self.error_occurred.emit("No file loaded")
            return False

        self._player.play()
        return True

    def pause(self) -> None:
        """Pause playback."""
        if self._is_playing:
            self._player.pause()

    def stop(self) -> None:
        """Stop playback and reset position."""
        self._player.stop()
        self._is_playing = False

    def toggle_play_pause(self, file_path: str | None = None) -> bool:
        """Toggle between play and pause.

        Args:
            file_path: If provided and different from current file, load and play it.

        Returns:
            True if now playing, False if paused/stopped.
        """
        # If a new file is provided, load and play it
        if file_path and file_path != self._current_file:
            self.play(file_path)
            return True

        # Toggle current playback
        if self._is_playing:
            self.pause()
            return False
        else:
            self.play()
            return True

    def seek(self, position_ms: int) -> None:
        """Seek to a position in the audio.

        Args:
            position_ms: Position in milliseconds.
        """
        self._player.setPosition(position_ms)

    def seek_relative(self, delta_ms: int) -> None:
        """Seek relative to current position.

        Args:
            delta_ms: Milliseconds to seek (positive = forward, negative = backward).
        """
        new_pos = max(0, min(self.duration, self.position + delta_ms))
        self.seek(new_pos)

    def _on_position_changed(self, position: int) -> None:
        """Handle position change."""
        self.position_changed.emit(position)

    def _on_duration_changed(self, duration: int) -> None:
        """Handle duration change."""
        self.duration_changed.emit(duration)

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        """Handle playback state change."""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._is_playing = True
            self.playback_started.emit(self._current_file or "")
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self._is_playing = False
            self.playback_paused.emit()
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            was_playing = self._is_playing
            self._is_playing = False
            if was_playing:
                # Check if playback finished naturally
                if self.position >= self.duration - 100:  # Within 100ms of end
                    self.playback_finished.emit()
                else:
                    self.playback_stopped.emit()

    def _on_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        """Handle playback error."""
        if error != QMediaPlayer.Error.NoError:
            self.error_occurred.emit(error_string)

    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop()
        self._player.setSource(QUrl())


def format_duration(ms: int) -> str:
    """Format milliseconds as MM:SS or HH:MM:SS.

    Args:
        ms: Duration in milliseconds.

    Returns:
        Formatted duration string.
    """
    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"
