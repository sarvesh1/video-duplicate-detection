"""
Directory Scanner Module for Video Duplicate Detection.
Recursively scans directories to discover video files and extract basic metadata.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    """Scanner for discovering video files in directories"""
    
    def __init__(self, max_workers: int = 8):
        self.found_files: List[FileMetadata] = []
        self.max_workers = max_workers
        self.stats = {
            'total_dirs': 0,
            'total_files': 0,
            'video_files': 0,
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
        Recursively scan a directory for video files.
        
        Args:
            directory_path: Path to the directory to scan
            
        Returns:
            List of FileMetadata objects for found video files
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
            print("Discovering video files...")
            
            # Phase 1: Discover all video files
            video_paths = []
            self._discover_video_files(directory, video_paths, tqdm(total=total_files, desc="Discovering files", unit="file"))
            
            print(f"Found {len(video_paths)} video files")
            print("Extracting metadata concurrently...")
            
            # Phase 2: Extract metadata concurrently
            self._extract_metadata_concurrent(video_paths)
            
            print(f"\nScan complete:")
            print(f"- Processed {self.stats['total_files']} files in {self.stats['total_dirs']} directories")
            print(f"- Found {self.stats['video_files']} video files")
            if self.stats['errors'] > 0:
                print(f"- Encountered {self.stats['errors']} errors")
            
            return self.found_files
            
        except Exception as e:
            print(f"Error scanning directory {directory_path}: {str(e)}")
            return []
    
    def _discover_video_files(self, directory: Path, video_paths: List[Path], progress: tqdm) -> None:
        """
        Recursively discover video files without extracting metadata.
        
        Args:
            directory: Path object for the directory to scan
            video_paths: List to collect discovered video file paths
            progress: tqdm progress bar object
        """
        try:
            for item in directory.iterdir():
                if item.is_file():
                    progress.update(1)
                    if item.suffix.lower() in ['.mp4', '.mov']:
                        stat = item.stat()
                        
                        # Skip very small files (likely corrupted)
                        if stat.st_size < 1024:  # Less than 1KB
                            continue
                            
                        self.stats['video_files'] += 1
                        video_paths.append(item)
                        progress.set_postfix({'Total videos found': self.stats['video_files']})
                elif item.is_dir():
                    self._discover_video_files(item, video_paths, progress)
        
        except Exception as e:
            self.stats['errors'] += 1
            print(f"\nError processing directory {directory}: {str(e)}")
    
    def _extract_single_metadata(self, file_path: Path) -> Optional[FileMetadata]:
        """
        Extract metadata for a single video file.
        
        Args:
            file_path: Path to the video file
            
        Returns:
            FileMetadata object if successful, None if failed
        """
        try:
            stat = file_path.stat()
            video_metadata = VideoMetadataParser.parse_video(file_path)
            
            return FileMetadata(
                file_path=str(file_path),
                file_size=stat.st_size,
                creation_time=datetime.fromtimestamp(stat.st_ctime),
                modification_time=datetime.fromtimestamp(stat.st_mtime),
                filename=file_path.name,
                directory=str(file_path.parent),
                video_metadata=video_metadata
            )
        except Exception as e:
            self.stats['errors'] += 1
            print(f"\nError extracting metadata for {file_path}: {str(e)}")
            return None
    
    def _extract_metadata_concurrent(self, video_paths: List[Path]) -> None:
        """
        Extract metadata for multiple video files concurrently.
        
        Args:
            video_paths: List of video file paths to process
        """
        if not video_paths:
            return
            
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_path = {
                executor.submit(self._extract_single_metadata, path): path 
                for path in video_paths
            }
            
            # Process completed tasks with progress bar
            with tqdm(total=len(video_paths), desc="Extracting metadata", unit="file") as progress:
                for future in as_completed(future_to_path):
                    result = future.result()
                    if result:
                        self.found_files.append(result)
                    progress.update(1)
                    progress.set_postfix({'Completed': len(self.found_files)})
