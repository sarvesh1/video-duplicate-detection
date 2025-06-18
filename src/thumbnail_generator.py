"""
Thumbnail Generator Module.
Extracts thumbnail images from video files for HTML interface display.
"""

import cv2
import base64
import os
from pathlib import Path
from typing import Optional, Dict
import hashlib
import json
from datetime import datetime

class ThumbnailGenerator:
    """Generates and caches video thumbnails for HTML interface"""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize thumbnail generator with cache directory.
        
        Args:
            cache_dir: Directory to store thumbnail cache. Defaults to 
                      .video_duplicate_detection/thumbnails in current working directory
        """
        if cache_dir is None:
            cache_dir = Path.cwd() / ".video_duplicate_detection" / "thumbnails"
        
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache metadata file to track thumbnails
        self.cache_metadata_file = self.cache_dir / "thumbnail_cache.json"
        self.cache_metadata = self._load_cache_metadata()
        
        # Thumbnail settings
        self.thumbnail_width = 150
        self.thumbnail_height = 100
        self.frame_position = 0.1  # Extract frame at 10% of video duration
    
    def _load_cache_metadata(self) -> Dict:
        """Load thumbnail cache metadata"""
        if self.cache_metadata_file.exists():
            try:
                with open(self.cache_metadata_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    def _save_cache_metadata(self):
        """Save thumbnail cache metadata"""
        try:
            with open(self.cache_metadata_file, 'w') as f:
                json.dump(self.cache_metadata, f, indent=2)
        except Exception:
            pass
    
    def _get_cache_key(self, video_path: Path) -> str:
        """Generate cache key for video file"""
        # Use file path and modification time for cache key
        try:
            mtime = video_path.stat().st_mtime
            path_str = str(video_path.absolute())
            cache_key = hashlib.md5(f"{path_str}_{mtime}".encode()).hexdigest()
            return cache_key
        except Exception:
            # Fallback to just path hash if stat fails
            return hashlib.md5(str(video_path.absolute()).encode()).hexdigest()
    
    def _get_cached_thumbnail(self, cache_key: str) -> Optional[str]:
        """Get cached thumbnail as base64 string"""
        if cache_key in self.cache_metadata:
            thumbnail_file = self.cache_dir / f"{cache_key}.jpg"
            if thumbnail_file.exists():
                try:
                    with open(thumbnail_file, 'rb') as f:
                        image_data = f.read()
                        return base64.b64encode(image_data).decode('utf-8')
                except Exception:
                    pass
        return None
    
    def _save_thumbnail(self, cache_key: str, image_data: bytes):
        """Save thumbnail to cache"""
        try:
            thumbnail_file = self.cache_dir / f"{cache_key}.jpg"
            with open(thumbnail_file, 'wb') as f:
                f.write(image_data)
            
            # Update cache metadata
            self.cache_metadata[cache_key] = {
                'created_at': datetime.now().isoformat(),
                'filename': f"{cache_key}.jpg"
            }
            self._save_cache_metadata()
        except Exception:
            pass
    
    def generate_thumbnail(self, video_path: Path) -> Optional[str]:
        """Generate thumbnail for video file.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Base64-encoded thumbnail image as data URL, or None if generation fails
        """
        cache_key = self._get_cache_key(video_path)
        
        # Try to get from cache first
        cached_thumbnail = self._get_cached_thumbnail(cache_key)
        if cached_thumbnail:
            return f"data:image/jpeg;base64,{cached_thumbnail}"
        
        # Generate new thumbnail
        try:
            # Open video file
            cap = cv2.VideoCapture(str(video_path))
            
            if not cap.isOpened():
                return None
            
            # Get video properties
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            if total_frames == 0 or fps == 0:
                cap.release()
                return None
            
            # Calculate frame position (10% into video)
            target_frame = int(total_frames * self.frame_position)
            
            # Seek to target frame
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            
            # Read frame
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                return None
            
            # Resize frame to thumbnail size
            thumbnail = cv2.resize(frame, (self.thumbnail_width, self.thumbnail_height))
            
            # Encode as JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
            ret, buffer = cv2.imencode('.jpg', thumbnail, encode_param)
            
            if not ret:
                return None
            
            # Convert to bytes
            image_data = buffer.tobytes()
            
            # Save to cache
            self._save_thumbnail(cache_key, image_data)
            
            # Convert to base64 data URL
            base64_image = base64.b64encode(image_data).decode('utf-8')
            return f"data:image/jpeg;base64,{base64_image}"
            
        except Exception as e:
            print(f"Error generating thumbnail for {video_path}: {str(e)}")
            return None
    
    def generate_placeholder_thumbnail(self) -> str:
        """Generate placeholder thumbnail for videos that can't be processed.
        
        Returns:
            Base64-encoded placeholder image as data URL
        """
        # Create simple placeholder image using OpenCV
        try:
            # Create gray image
            placeholder = cv2.rectangle(
                src=cv2.copyMakeBorder(
                    src=cv2.resize(
                        src=cv2.imread(cv2.samples.findFile("lena.jpg"), cv2.IMREAD_GRAYSCALE) or 
                            (cv2.ones((100, 150), dtype='uint8') * 128),
                        dsize=(self.thumbnail_width, self.thumbnail_height)
                    ),
                    top=0, bottom=0, left=0, right=0,
                    borderType=cv2.BORDER_CONSTANT,
                    value=128
                ),
                pt1=(5, 5), 
                pt2=(self.thumbnail_width-5, self.thumbnail_height-5),
                color=64, 
                thickness=2
            )
            
            # Add text
            cv2.putText(placeholder, "No Preview", (20, 55), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, 255, 1)
            
            # Encode as JPEG
            ret, buffer = cv2.imencode('.jpg', placeholder, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ret:
                base64_image = base64.b64encode(buffer.tobytes()).decode('utf-8')
                return f"data:image/jpeg;base64,{base64_image}"
        except Exception:
            pass
        
        # Fallback: simple SVG placeholder
        svg_placeholder = '''<svg width="150" height="100" xmlns="http://www.w3.org/2000/svg">
            <rect width="150" height="100" fill="#cccccc" stroke="#999999" stroke-width="2"/>
            <text x="75" y="55" text-anchor="middle" font-family="Arial" font-size="12">No Preview</text>
        </svg>'''
        
        base64_svg = base64.b64encode(svg_placeholder.encode()).decode('utf-8')
        return f"data:image/svg+xml;base64,{base64_svg}"
    
    def cleanup_cache(self, max_age_days: int = 30):
        """Clean up old thumbnails from cache.
        
        Args:
            max_age_days: Remove thumbnails older than this many days
        """
        try:
            cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 3600)
            
            for cache_key, metadata in list(self.cache_metadata.items()):
                try:
                    created_at = datetime.fromisoformat(metadata['created_at'])
                    if created_at.timestamp() < cutoff_time:
                        # Remove thumbnail file
                        thumbnail_file = self.cache_dir / metadata['filename']
                        if thumbnail_file.exists():
                            thumbnail_file.unlink()
                        
                        # Remove from metadata
                        del self.cache_metadata[cache_key]
                except Exception:
                    # Remove invalid entries
                    del self.cache_metadata[cache_key]
            
            self._save_cache_metadata()
        except Exception:
            pass