"""
Video Metadata Parser Module.
Extracts detailed metadata from video files using ffmpeg-python.
"""

import ffmpeg
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional, Any
from datetime import timedelta

@dataclass
class VideoMetadata:
    """Data class to store video-specific metadata"""
    duration: float  # Duration in seconds
    width: int
    height: int
    codec: str
    bitrate: int  # bits per second
    fps: float
    audio_codec: Optional[str] = None
    audio_sample_rate: Optional[int] = None
    file_size: int = 0
    
    @property
    def resolution(self) -> str:
        """Returns the video resolution as a string (e.g., '1920x1080')"""
        return f"{self.width}x{self.height}"
    
    @property
    def duration_formatted(self) -> str:
        """Returns the duration in HH:MM:SS format"""
        td = timedelta(seconds=int(self.duration))
        return str(td)

class VideoMetadataParser:
    """Parser for extracting metadata from video files"""
    
    @staticmethod
    def parse_video(file_path: str | Path) -> Optional[VideoMetadata]:
        """
        Extract metadata from a video file using ffmpeg.
        
        Args:
            file_path: Path to the video file
            
        Returns:
            VideoMetadata object if successful, None if parsing fails
        """
        try:
            probe = ffmpeg.probe(str(file_path))
            video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            
            # Get audio info if available
            audio_info = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
            
            # Extract duration - use format duration if available, otherwise stream duration
            duration = float(probe['format'].get('duration', video_info.get('duration', 0)))
            
            # Calculate bitrate
            size = os.path.getsize(file_path)
            bitrate = int(probe['format'].get('bit_rate', 0))
            
            # Extract FPS
            fps_parts = video_info.get('r_frame_rate', '0/1').split('/')
            fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else 0.0
            
            return VideoMetadata(
                duration=duration,
                width=int(video_info['width']),
                height=int(video_info['height']),
                codec=video_info['codec_name'],
                bitrate=bitrate,
                fps=fps,
                audio_codec=audio_info['codec_name'] if audio_info else None,
                audio_sample_rate=int(audio_info['sample_rate']) if audio_info else None,
                file_size=size
            )
            
        except Exception as e:
            print(f"Error parsing video metadata for {file_path}: {str(e)}")
            return None
    
    @staticmethod
    def validate_metadata(metadata: VideoMetadata) -> Dict[str, bool]:
        """
        Validate video metadata against common requirements.
        
        Args:
            metadata: VideoMetadata object to validate
            
        Returns:
            Dictionary of validation results
        """
        return {
            'has_valid_duration': metadata.duration > 0,
            'has_valid_dimensions': metadata.width > 0 and metadata.height > 0,
            'has_valid_bitrate': metadata.bitrate > 0,
            'has_valid_fps': metadata.fps > 0,
            'has_audio': metadata.audio_codec is not None
        }
