"""Service for exporting timeline markers to text and CSV formats."""

from pathlib import Path
from typing import List, Dict, Any


def format_time(seconds: float, include_hours: bool = False) -> str:
    """Format time in seconds to MM:SS.mmm or HH:MM:SS.mmm format.
    
    Args:
        seconds: Time in seconds.
        include_hours: If True, format as HH:MM:SS.mmm, else MM:SS.mmm.
        
    Returns:
        Formatted time string.
    """
    total_seconds = int(seconds)
    milliseconds = int((seconds % 1) * 1000)
    
    if include_hours:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"
    else:
        minutes = total_seconds // 60
        secs = total_seconds % 60
        return f"{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def export_markers_to_text(markers: List[Dict[str, Any]], output_path: Path) -> None:
    """Export timeline markers to a plain text file.
    
    Format:
        00:00.000  Marker text
        02:15.115  Another marker
    
    Args:
        markers: List of marker dicts with 'time' and 'text' keys.
        output_path: Path to output file.
        
    Raises:
        IOError: If file cannot be written.
    """
    if not markers:
        raise ValueError("No markers to export")
    
    # Determine if we need hours format (if any marker > 1 hour)
    max_time = max(m.get('time', 0.0) for m in markers)
    include_hours = max_time >= 3600
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for marker in markers:
            time_sec = marker.get('time', 0.0)
            text = marker.get('text', '')
            time_str = format_time(time_sec, include_hours)
            f.write(f"{time_str}  {text}\n")


def export_markers_to_csv(markers: List[Dict[str, Any]], output_path: Path) -> None:
    """Export timeline markers to a CSV file.
    
    Format:
        Time,Text
        0.0,"Marker text"
        135.115,"Another marker"
    
    Args:
        markers: List of marker dicts with 'time' and 'text' keys.
        output_path: Path to output file.
        
    Raises:
        IOError: If file cannot be written.
    """
    import csv
    
    if not markers:
        raise ValueError("No markers to export")
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Time', 'Text'])  # Header
        
        for marker in markers:
            time_sec = marker.get('time', 0.0)
            text = marker.get('text', '')
            writer.writerow([time_sec, text])
