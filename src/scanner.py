"""
Directory Scanner Module for Video Duplicate Detection.
Recursively scans directories to discover MP4 files and extract basic metadata.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from video_metadata import VideoMetadata, VideoMetadataParser
from tqdm import tqdm

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
        self.stats = {
            'total_dirs': 0,
            'total_files': 0,
            'mp4_files': 0,
            'errors': 0
        }
    
    def _count_items(self, directory: Path) -> Tuple[int, int]:
        """
        Count total number of files and directories to process.
        
        Args:
            directory: Path object for the directory to scan
            
        Returns:
            Tuple of (total_files, total_dirs)
        """
        total_files = 0
        total_dirs = 1
        try:
            for item in directory.iterdir():
                if item.is_file():
                    total_files += 1
                elif item.is_dir():
                    total_dirs += 1
                    sub_files, sub_dirs = self._count_items(item)
                    total_files += sub_files
                    total_dirs += sub_dirs
        except Exception as e:
            print(f"\nError counting items in {directory}: {str(e)}")
            
        return total_files, total_dirs
    
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
            
            print(f"\nAnalyzing directory structure in {directory_path}...")
            total_files, total_dirs = self._count_items(directory)
            self.stats['total_files'] = total_files
            self.stats['total_dirs'] = total_dirs
            
            print(f"\nFound {total_files} files in {total_dirs} directories")
            print("Starting scan...")
            
            self._scan_recursive(directory, tqdm(total=total_files, desc="Scanning files", unit="file"))
            
            print(f"\nScan complete:")
            print(f"- Processed {self.stats['total_files']} files in {self.stats['total_dirs']} directories")
            print(f"- Found {self.stats['mp4_files']} MP4 files")
            if self.stats['errors'] > 0:
                print(f"- Encountered {self.stats['errors']} errors")
            
            return self.found_files
            
        except Exception as e:
            print(f"Error scanning directory {directory_path}: {str(e)}")
            return []
    
    def _scan_recursive(self, directory: Path, progress: tqdm) -> None:
        """
        Recursively scan directory for MP4 files.
        
        Args:
            directory: Path object for the directory to scan
            progress: tqdm progress bar object
        """
        try:
            for item in directory.iterdir():
                if item.is_file():
                    progress.update(1)
                    if item.suffix.lower() == '.mp4':
                        self.stats['mp4_files'] += 1
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
                        progress.set_postfix({'Total MP4s found': self.stats['mp4_files']})
                elif item.is_dir():
                    self._scan_recursive(item, progress)
        
        except Exception as e:
            self.stats['errors'] += 1
            print(f"\nError processing directory {directory}: {str(e)}")
