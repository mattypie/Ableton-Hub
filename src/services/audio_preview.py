"""Audio preview and thumbnail generation service."""

from typing import Optional, Literal, List
from pathlib import Path
import subprocess
import sys
import random

from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QLinearGradient
from PyQt6.QtCore import Qt

from ..database import get_session, Project, Export
from ..utils.paths import get_thumbnail_cache_dir
from ..utils.logging import get_logger
from ..config import get_config

# Color mode type definition
COLOR_MODES = Literal[
    "rainbow",
    "dark_blue_cyan",
    "orange_red",
    "purple_cyan",
    "green_red",
    "pink_orange",
    "teal_blue",
    "yellow_green",
    "magenta_pink",
    "cyan_green",
    "random",
    "green",
    "blue",
    "purple"
]

# Gradient-only modes (for random selection - excludes solid colors)
GRADIENT_MODES: List[str] = [
    "rainbow",
    "dark_blue_cyan",
    "orange_red",
    "purple_cyan",
    "green_red",
    "pink_orange",
    "teal_blue",
    "yellow_green",
    "magenta_pink",
    "cyan_green"
]


class AudioPreviewGenerator:
    """Service for generating audio preview thumbnails."""
    
    @staticmethod
    def _get_project_color(project_id: int, color_mode: COLOR_MODES = "rainbow") -> Optional[QColor]:
        """Get a color for a project based on color mode.
        
        Args:
            project_id: Project ID for consistent random color generation.
            color_mode: Color mode (all modes use gradients now).
            
        Returns:
            None - all modes use gradients via QLinearGradient.
        """
        # All modes use gradients now (solid colors disabled)
        return None
    
    @staticmethod
    def _get_ffmpeg_colors(color_mode: COLOR_MODES = "rainbow") -> str:
        """Get ffmpeg color string based on color mode.
        
        Note: FFmpeg's showwavespic doesn't support gradient colors directly.
        For gradient modes, we use a representative color from the gradient.
        The simple waveform fallback uses full gradients.
        
        Args:
            color_mode: Color mode.
            
        Returns:
            FFmpeg color string for showwavespic filter.
        """
        color_map = {
            "rainbow": "0x00ffff",        # Cyan (representative of rainbow)
            "dark_blue_cyan": "0x0080ff",  # Blue-cyan
            "orange_red": "0xff6600",      # Orange-red
            "purple_cyan": "0xff00ff",     # Purple-cyan
            "green_red": "0x00ff00",       # Green (representative)
            "pink_orange": "0xff80c0",     # Pink-orange
            "teal_blue": "0x0080ff",       # Teal-blue
            "yellow_green": "0x80ff00",    # Yellow-green
            "magenta_pink": "0xff00ff",    # Magenta-pink
            "cyan_green": "0x00ff80",      # Cyan-green
            "random": "0x00ffff"           # Default to cyan (shouldn't be used - random is resolved earlier)
        }
        return color_map.get(color_mode, "0x00ffff")
    
    @staticmethod
    def has_ffmpeg() -> bool:
        """Check if ffmpeg is available."""
        try:
            subprocess.run(
                ['ffmpeg', '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=2
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    @staticmethod
    def generate_waveform_image(
        audio_path: str,
        output_path: str,
        width: int = 200,
        height: int = 60,
        color_mode: COLOR_MODES = "rainbow",
        project_id: Optional[int] = None
    ) -> bool:
        """Generate a waveform image from an audio file.
        
        Args:
            audio_path: Path to audio file.
            output_path: Path to save the waveform image.
            width: Image width in pixels.
            height: Image height in pixels.
            color_mode: Color mode ("rainbow", "random", or "accent").
            project_id: Project ID for consistent random color (required if color_mode="random").
            
        Returns:
            True if successful, False otherwise.
        """
        if not AudioPreviewGenerator.has_ffmpeg():
            return False
        
        try:
            audio_file = Path(audio_path)
            if not audio_file.exists():
                return False
            
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Get color string for ffmpeg
            # Note: random mode is handled before this function is called (in get_or_generate_preview)
            color_hex = AudioPreviewGenerator._get_ffmpeg_colors(color_mode)
            
            # Use ffmpeg to extract waveform data
            # FFmpeg doesn't support gradients directly, so we use a representative color
            # The simple waveform fallback will use the full gradients
            cmd = [
                'ffmpeg',
                '-i', str(audio_file),
                '-filter_complex', f'[0:a]aformat=channel_layouts=mono,showwavespic=s={width}x{height}:colors={color_hex}',
                '-frames:v', '1',
                '-y',  # Overwrite output
                str(output_file)
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30
            )
            
            return result.returncode == 0
            
        except Exception as e:
            logger = get_logger(__name__)
            logger.error(f"Error generating waveform: {e}", exc_info=True)
            return False
    
    @staticmethod
    def generate_simple_waveform(
        audio_path: str,
        width: int = 200,
        height: int = 60,
        color_mode: COLOR_MODES = "rainbow",
        project_id: Optional[int] = None
    ) -> Optional[QPixmap]:
        """Generate a simple waveform pixmap (fallback if ffmpeg not available).
        
        Args:
            audio_path: Path to audio file.
            width: Image width.
            height: Image height.
            color_mode: Color mode ("rainbow", "random", or "accent").
            project_id: Project ID for consistent random color (required if color_mode="random").
            
        Returns:
            QPixmap with waveform or None if failed.
        """
        # This is a placeholder - would need audio library like librosa
        # For now, return a simple placeholder
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor(30, 30, 30))  # Dark background
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        center_y = height // 2
        
        # Create gradient based on color mode - use GRADIENT_MODES list
        if color_mode in GRADIENT_MODES:
            gradient = QLinearGradient(0, 0, width, 0)
            
            if color_mode == "rainbow":
                # Rainbow gradient
                gradient.setColorAt(0.0, QColor(255, 0, 0))      # Red
                gradient.setColorAt(0.2, QColor(255, 136, 0))    # Orange
                gradient.setColorAt(0.4, QColor(255, 255, 0))    # Yellow
                gradient.setColorAt(0.6, QColor(0, 255, 0))      # Green
                gradient.setColorAt(0.8, QColor(0, 136, 255))   # Blue
                gradient.setColorAt(1.0, QColor(255, 0, 255))   # Purple
            elif color_mode == "dark_blue_cyan":
                # Bright blue to cyan gradient (brightened for readability)
                gradient.setColorAt(0.0, QColor(0, 102, 255))   # Bright blue
                gradient.setColorAt(0.5, QColor(0, 150, 255))  # Medium blue-cyan
                gradient.setColorAt(1.0, QColor(0, 255, 255))  # Cyan
            elif color_mode == "orange_red":
                # Orange to red gradient
                gradient.setColorAt(0.0, QColor(255, 136, 0))   # Orange
                gradient.setColorAt(0.5, QColor(255, 80, 0))    # Orange-red
                gradient.setColorAt(1.0, QColor(255, 0, 0))     # Red
            elif color_mode == "purple_cyan":
                # Purple to cyan gradient (brightened for readability)
                gradient.setColorAt(0.0, QColor(204, 0, 255))   # Bright purple
                gradient.setColorAt(0.5, QColor(150, 100, 255)) # Medium purple-blue
                gradient.setColorAt(1.0, QColor(0, 255, 255))  # Cyan
            elif color_mode == "green_red":
                # Green to red gradient
                gradient.setColorAt(0.0, QColor(0, 255, 0))     # Green
                gradient.setColorAt(0.5, QColor(255, 255, 0))   # Yellow
                gradient.setColorAt(1.0, QColor(255, 0, 0))     # Red
            elif color_mode == "pink_orange":
                # Pink to orange gradient (warm sunset)
                gradient.setColorAt(0.0, QColor(255, 100, 200)) # Pink
                gradient.setColorAt(0.5, QColor(255, 150, 100)) # Peach
                gradient.setColorAt(1.0, QColor(255, 136, 0))   # Orange
            elif color_mode == "teal_blue":
                # Teal to blue gradient (cool ocean)
                gradient.setColorAt(0.0, QColor(0, 200, 200))   # Teal
                gradient.setColorAt(0.5, QColor(0, 150, 255))  # Light blue
                gradient.setColorAt(1.0, QColor(0, 100, 255))  # Blue
            elif color_mode == "yellow_green":
                # Yellow to green gradient (fresh spring)
                gradient.setColorAt(0.0, QColor(255, 255, 0))   # Yellow
                gradient.setColorAt(0.5, QColor(150, 255, 100)) # Light green
                gradient.setColorAt(1.0, QColor(0, 255, 100))   # Green
            elif color_mode == "magenta_pink":
                # Magenta to pink gradient (vibrant)
                gradient.setColorAt(0.0, QColor(255, 0, 200))   # Magenta
                gradient.setColorAt(0.5, QColor(255, 80, 180)) # Hot pink
                gradient.setColorAt(1.0, QColor(255, 150, 200)) # Pink
            elif color_mode == "cyan_green":
                # Cyan to green gradient (cool fresh)
                gradient.setColorAt(0.0, QColor(0, 255, 255))   # Cyan
                gradient.setColorAt(0.5, QColor(0, 255, 180))  # Aqua
                gradient.setColorAt(1.0, QColor(0, 255, 100))  # Green
            
            painter.setPen(QPen(gradient, 2))
        elif color_mode == "random" and project_id is not None:
            # For random mode, randomly select a gradient color mode each time
            # Use project_id as seed for consistency
            random.seed(project_id)
            # ONLY select from gradient modes, never solid colors
            selected_mode = random.choice(GRADIENT_MODES)
            random.seed()  # Reset seed
            
            # All selected modes are gradients, so create gradient
            gradient = QLinearGradient(0, 0, width, 0)
            if selected_mode == "rainbow":
                gradient.setColorAt(0.0, QColor(255, 0, 0))
                gradient.setColorAt(0.2, QColor(255, 136, 0))
                gradient.setColorAt(0.4, QColor(255, 255, 0))
                gradient.setColorAt(0.6, QColor(0, 255, 0))
                gradient.setColorAt(0.8, QColor(0, 136, 255))
                gradient.setColorAt(1.0, QColor(255, 0, 255))
            elif selected_mode == "dark_blue_cyan":
                gradient.setColorAt(0.0, QColor(0, 102, 255))
                gradient.setColorAt(0.5, QColor(0, 150, 255))
                gradient.setColorAt(1.0, QColor(0, 255, 255))
            elif selected_mode == "orange_red":
                gradient.setColorAt(0.0, QColor(255, 136, 0))
                gradient.setColorAt(0.5, QColor(255, 80, 0))
                gradient.setColorAt(1.0, QColor(255, 0, 0))
            elif selected_mode == "purple_cyan":
                gradient.setColorAt(0.0, QColor(204, 0, 255))
                gradient.setColorAt(0.5, QColor(150, 100, 255))
                gradient.setColorAt(1.0, QColor(0, 255, 255))
            elif selected_mode == "green_red":
                gradient.setColorAt(0.0, QColor(0, 255, 0))
                gradient.setColorAt(0.5, QColor(255, 255, 0))
                gradient.setColorAt(1.0, QColor(255, 0, 0))
            elif selected_mode == "pink_orange":
                gradient.setColorAt(0.0, QColor(255, 100, 200))
                gradient.setColorAt(0.5, QColor(255, 150, 100))
                gradient.setColorAt(1.0, QColor(255, 136, 0))
            elif selected_mode == "teal_blue":
                gradient.setColorAt(0.0, QColor(0, 200, 200))
                gradient.setColorAt(0.5, QColor(0, 150, 255))
                gradient.setColorAt(1.0, QColor(0, 100, 255))
            elif selected_mode == "yellow_green":
                gradient.setColorAt(0.0, QColor(255, 255, 0))
                gradient.setColorAt(0.5, QColor(150, 255, 100))
                gradient.setColorAt(1.0, QColor(0, 255, 100))
            elif selected_mode == "magenta_pink":
                gradient.setColorAt(0.0, QColor(255, 0, 200))
                gradient.setColorAt(0.5, QColor(255, 80, 180))
                gradient.setColorAt(1.0, QColor(255, 150, 200))
            elif selected_mode == "cyan_green":
                gradient.setColorAt(0.0, QColor(0, 255, 255))
                gradient.setColorAt(0.5, QColor(0, 255, 180))
                gradient.setColorAt(1.0, QColor(0, 255, 100))
            painter.setPen(QPen(gradient, 2))
        else:
            # Default to rainbow gradient for unknown modes (should not happen)
            gradient = QLinearGradient(0, 0, width, 0)
            gradient.setColorAt(0.0, QColor(255, 0, 0))
            gradient.setColorAt(0.2, QColor(255, 136, 0))
            gradient.setColorAt(0.4, QColor(255, 255, 0))
            gradient.setColorAt(0.6, QColor(0, 255, 0))
            gradient.setColorAt(0.8, QColor(0, 136, 255))
            gradient.setColorAt(1.0, QColor(255, 0, 255))
            painter.setPen(QPen(gradient, 2))
        
        # Draw simple placeholder waveform
        for x in range(0, width, 4):
            # Random height for demo (would use actual audio data)
            wave_height = random.randint(5, height // 2)
            painter.drawLine(x, center_y - wave_height, x, center_y + wave_height)
        
        painter.end()
        return pixmap
    
    @staticmethod
    def get_or_generate_preview(
        project_id: int,
        color_mode: Optional[COLOR_MODES] = None,
        force_regenerate: bool = False
    ) -> Optional[str]:
        """Get or generate preview thumbnail for a project.
        
        Args:
            project_id: ID of the project.
            color_mode: Color mode for waveform. If None, uses config setting.
            force_regenerate: If True, regenerate even if thumbnail exists (useful for random mode).
            
        Returns:
            Path to preview thumbnail, or None if unavailable.
        """
        # Get color mode from config if not specified
        if color_mode is None:
            config = get_config()
            color_mode = config.ui.waveform_color_mode  # type: ignore
        
        # Handle random mode - randomly select a gradient color mode
        # Use project_id as seed for consistent color per project (won't change on resize/refresh)
        if color_mode == "random":
            # Use only project_id as seed for consistent color per project
            # This ensures the same project always gets the same random color
            # until the thumbnail cache is cleared
            random.seed(project_id)
            # ONLY select from gradient modes, never solid colors
            color_mode = random.choice(GRADIENT_MODES)  # type: ignore
            random.seed()  # Reset seed
            # Don't force regenerate - use cached thumbnail if available
        session = get_session()
        try:
            project = session.query(Project).get(project_id)
            if not project:
                return None
            
            # Check if preview already exists (skip if force_regenerate is True)
            if not force_regenerate and project.thumbnail_path and Path(project.thumbnail_path).exists():
                return project.thumbnail_path
            
            # Try to find an export to generate preview from
            exports = session.query(Export).filter(
                Export.project_id == project_id
            ).order_by(Export.created_date.desc()).all()
            
            if not exports:
                return None
            
            # Use the most recent export
            export = exports[0]
            export_path = Path(export.export_path)
            
            if not export_path.exists():
                return None
            
            # Generate preview path using proper cache directory
            preview_dir = get_thumbnail_cache_dir()
            preview_path = preview_dir / f"project_{project_id}.png"
            
            # Generate waveform with color mode
            if AudioPreviewGenerator.generate_waveform_image(
                str(export_path),
                str(preview_path),
                color_mode=color_mode,
                project_id=project_id
            ):
                # Update project with preview path
                project.thumbnail_path = str(preview_path)
                session.commit()
                return str(preview_path)
            else:
                # Fallback to simple waveform
                pixmap = AudioPreviewGenerator.generate_simple_waveform(
                    str(export_path),
                    color_mode=color_mode,
                    project_id=project_id
                )
                if pixmap:
                    pixmap.save(str(preview_path))
                    project.thumbnail_path = str(preview_path)
                    session.commit()
                    return str(preview_path)
            
            return None
            
        finally:
            session.close()
