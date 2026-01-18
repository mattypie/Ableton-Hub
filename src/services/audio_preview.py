"""Audio preview and thumbnail generation service."""

from typing import Optional
from pathlib import Path
import subprocess
import sys

from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen
from PyQt6.QtCore import Qt

from ..database import get_session, Project, Export


class AudioPreviewGenerator:
    """Service for generating audio preview thumbnails."""
    
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
        color: QColor = None
    ) -> bool:
        """Generate a waveform image from an audio file.
        
        Args:
            audio_path: Path to audio file.
            output_path: Path to save the waveform image.
            width: Image width in pixels.
            height: Image height in pixels.
            color: Waveform color (default: theme accent).
            
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
            
            # Use ffmpeg to extract waveform data
            # This is a simplified approach - for better results, use librosa or similar
            cmd = [
                'ffmpeg',
                '-i', str(audio_file),
                '-filter_complex', f'[0:a]aformat=channel_layouts=mono,showwavespic=s={width}x{height}:colors=0x00ff00',
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
            print(f"Error generating waveform: {e}")
            return False
    
    @staticmethod
    def generate_simple_waveform(
        audio_path: str,
        width: int = 200,
        height: int = 60,
        color: QColor = None
    ) -> Optional[QPixmap]:
        """Generate a simple waveform pixmap (fallback if ffmpeg not available).
        
        Args:
            audio_path: Path to audio file.
            width: Image width.
            height: Image height.
            color: Waveform color.
            
        Returns:
            QPixmap with waveform or None if failed.
        """
        # This is a placeholder - would need audio library like librosa
        # For now, return a simple placeholder
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor(30, 30, 30))  # Dark background
        
        painter = QPainter(pixmap)
        if color:
            painter.setPen(QPen(color, 2))
        else:
            painter.setPen(QPen(QColor(0, 200, 100), 2))  # Green accent
        
        # Draw simple placeholder waveform
        center_y = height // 2
        for x in range(0, width, 4):
            # Random height for demo (would use actual audio data)
            import random
            wave_height = random.randint(5, height // 2)
            painter.drawLine(x, center_y - wave_height, x, center_y + wave_height)
        
        painter.end()
        return pixmap
    
    @staticmethod
    def get_or_generate_preview(project_id: int) -> Optional[str]:
        """Get or generate preview thumbnail for a project.
        
        Args:
            project_id: ID of the project.
            
        Returns:
            Path to preview thumbnail, or None if unavailable.
        """
        session = get_session()
        try:
            project = session.query(Project).get(project_id)
            if not project:
                return None
            
            # Check if preview already exists
            if project.thumbnail_path and Path(project.thumbnail_path).exists():
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
            
            # Generate preview path
            preview_dir = Path.home() / ".ableton_hub" / "previews"
            preview_dir.mkdir(parents=True, exist_ok=True)
            preview_path = preview_dir / f"project_{project_id}.png"
            
            # Generate waveform
            if AudioPreviewGenerator.generate_waveform_image(
                str(export_path),
                str(preview_path)
            ):
                # Update project with preview path
                project.thumbnail_path = str(preview_path)
                session.commit()
                return str(preview_path)
            else:
                # Fallback to simple waveform
                pixmap = AudioPreviewGenerator.generate_simple_waveform(
                    str(export_path)
                )
                if pixmap:
                    pixmap.save(str(preview_path))
                    project.thumbnail_path = str(preview_path)
                    session.commit()
                    return str(preview_path)
            
            return None
            
        finally:
            session.close()
