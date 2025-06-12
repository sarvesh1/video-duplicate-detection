"""
Directory Scanner Module for Video Duplicate Detection.
Recursively scans directories to discover MP4 files and extract basic metadata.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from .video_metadata import VideoMetadata, VideoMetadataParser

@dataclass
class FileMetadata:
    """Data class to store file metadata"""
    file_path: str
    file_size: int
    creation_time: datetime
    modification_time: datetime
    filename: str
    directory: str
    video_metadata: Optional[VideoMetadata] = None

class DirectoryScanner:
    """Scanner for discovering MP4 files in directories"""
    
    def __init__(self):
        self.found_files: List[FileMetadata] = []
    
    def scan_directory(self, directory_path: str) -> List[FileMetadata]:
        """
        Recursively scan a directory for MP4 files.
        
        Args:
            directory_path: Path to the directory to scan
            
        Returns:
            List of FileMetadata objects for found MP4 files
        """
        try:
            directory = Path(directory_path).resolve()
            if not directory.exists():
                raise FileNotFoundError(f"Directory {directory_path} does not exist")
            
            self._scan_recursive(directory)
            return self.found_files
            
        except Exception as e:
            print(f"Error scanning directory {directory_path}: {str(e)}")
            return []
    
    def _scan_recursive(self, directory: Path) -> None:
        """
        Recursively scan directory for MP4 files.
        
        Args:
            directory: Path object for the directory to scan
        """
        try:
            for item in directory.iterdir():
                if item.is_file() and item.suffix.lower() == '.mp4':
                    stat = item.stat()
                    metadata = FileMetadata(
                        file_path=str(item),
                        file_size=stat.st_size,
                        creation_time=datetime.fromtimestamp(stat.st_ctime),
                        modification_time=datetime.fromtimestamp(stat.st_mtime),
                        filename=item.name,
                        directory=str(item.parent),
                        video_metadata=VideoMetadataParser.parse_video(item)
                    )
                    self.found_files.append(metadata)
                elif item.is_dir():
                    self._scan_recursive(item)
        
        except Exception as e:
            print(f"Error processing directory {directory}: {str(e)}")
