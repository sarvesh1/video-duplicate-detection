"""
Video Metadata Parser Module.
Extracts detailed metadata from video files using ffmpeg-python.
"""

import ffmpeg
import os
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

CACHE_VERSION = "1.0"  # For future cache format changes

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

class MetadataCache:
    """Cache for video metadata to avoid re-reading files"""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / '.video_duplicate_detection' / 'cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "metadata_cache.json"
        self.cache: Dict[str, dict] = self._load_cache()
        self.unsaved_changes = 0
        self.save_threshold = 10  # Save every 10 changes
    
    def _load_cache(self) -> Dict[str, dict]:
        """Load cache from disk"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    if data.get('version') == CACHE_VERSION:
                        return data.get('entries', {})
            except Exception:
                pass
        return {}
    
    def save_cache(self):
        """Save cache to disk"""
        with open(self.cache_file, 'w') as f:
            json.dump({
                'version': CACHE_VERSION,
                'entries': self.cache,
                'last_updated': datetime.now().isoformat()
            }, f)
    
    def get(self, file_path: Path) -> Optional[VideoMetadata]:
        """Get cached metadata if file hasn't changed"""
        key = str(file_path)
        try:
            if key in self.cache:
                cached = self.cache[key]
                current_mtime = file_path.stat().st_mtime
                if current_mtime == cached.get('mtime'):
                    return VideoMetadata(**cached['metadata'])
        except Exception:
            pass
        return None
    
    def set(self, file_path: Path, metadata: VideoMetadata):
        """Cache metadata for a file"""
        try:
            self.cache[str(file_path)] = {
                'mtime': file_path.stat().st_mtime,
                'metadata': asdict(metadata),
                'cached_at': datetime.now().isoformat()
            }
            self.unsaved_changes += 1
            # Auto-save periodically to balance performance and safety
            if self.unsaved_changes >= self.save_threshold:
                self.save_cache()
                self.unsaved_changes = 0
        except Exception:
            pass

class VideoMetadataParser:
    """Parser for extracting metadata from video files"""
    
    _cache = MetadataCache()
    
    @staticmethod
    def parse_video(file_path: str | Path) -> Optional[VideoMetadata]:
        """
        Extract metadata from a video file using ffmpeg.
        Uses caching and optimized probing for better performance.
        
        Args:
            file_path: Path to the video file
            
        Returns:
            VideoMetadata object if successful, None if parsing fails
        """
        file_path = Path(file_path)
        
        # Try to get from cache first
        cached = VideoMetadataParser._cache.get(file_path)
        if cached:
            return cached
            
        try:
            # Use ffprobe with network-optimized settings
            probe = ffmpeg.probe(
                str(file_path),
                cmd='ffprobe',  # Ensure we use ffprobe directly
                v='error',  # Only show errors in ffprobe output
                analyzeduration='1000000',  # Analyze only first 1MB for speed
                probesize='1000000',  # Probe only first 1MB
                select_streams='v:0',  # Only analyze first video stream
            )
            
            video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            audio_info = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
            
            # Extract duration - use format duration if available, otherwise stream duration
            duration = float(probe['format'].get('duration', video_info.get('duration', 0)))
            
            # Calculate bitrate
            size = os.path.getsize(file_path)
            bitrate = int(probe['format'].get('bit_rate', 0))
            
            # Extract FPS
            fps_parts = video_info.get('r_frame_rate', '0/1').split('/')
            fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else 0.0
            
            metadata = VideoMetadata(
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
            
            # Cache the result (auto-saves periodically)
            VideoMetadataParser._cache.set(file_path, metadata)
            
            return metadata
            
        except ffmpeg.Error as e:
            print(f"Error parsing video metadata for {file_path}:")
            print(f"ffprobe stderr output: {e.stderr.decode()}")
            return None
        except Exception as e:
            print(f"Error parsing video metadata for {file_path}: {str(e)}")
            return None
    
    @staticmethod
    def save_cache():
        """Save the metadata cache to disk"""
        VideoMetadataParser._cache.save_cache()
    
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

    def __del__(self):
        """Save cache when parser is destroyed"""
        self._cache.save_cache()
