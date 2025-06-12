"""
Core data structures for storing and indexing video file metadata.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Optional
from collections import defaultdict
from src.video_metadata import VideoMetadata
import sys

# Adjust the path for module imports
sys.path.append(str(Path(__file__).resolve().parent))

@dataclass
class FileInfo:
    """Represents metadata for a single file"""
    path: Path
    created_at: datetime
    modified_at: datetime
    file_size: int
    video_metadata: Optional[VideoMetadata] = None

class MetadataStore:
    """
    Central data store for file metadata with multiple indices for efficient lookup.
    """
    
    def __init__(self):
        # Primary storage: path -> metadata
        self.files: Dict[str, FileInfo] = {}
        
        # Filename index: filename -> set of paths
        self.filename_index: Dict[str, Set[str]] = defaultdict(set)
        
        # Directory index: directory -> set of paths
        self.directory_index: Dict[str, Set[str]] = defaultdict(set)
        
        # Size-based index: size -> set of paths (for potential duplicates)
        self.size_index: Dict[int, Set[str]] = defaultdict(set)
    
    def add_file(self, file_info: FileInfo) -> None:
        """
        Add a file's metadata to the store and update all indices
        
        Args:
            file_info: FileInfo object containing file information
        """
        path_str = str(file_info.path)
        self.files[path_str] = file_info
        self.filename_index[file_info.path.name].add(path_str)
        self.directory_index[str(file_info.path.parent)].add(path_str)
        self.size_index[file_info.file_size].add(path_str)
    
    def get_by_filename(self, filename: str) -> List[FileInfo]:
        """
        Get all files with a given filename
        
        Args:
            filename: Name of the file to search for
            
        Returns:
            List of FileInfo objects for matching files
        """
        paths = self.filename_index.get(filename, set())
        return [self.files[path] for path in paths]
    
    def get_by_directory(self, directory: str) -> List[FileInfo]:
        """
        Get all files in a given directory
        
        Args:
            directory: Directory path to search in
            
        Returns:
            List of FileInfo objects for files in the directory
        """
        paths = self.directory_index.get(directory, set())
        return [self.files[path] for path in paths]
    
    def get_similar_sizes(self, size: int, tolerance_bytes: int = 1024) -> List[FileInfo]:
        """
        Find files with sizes similar to the given size
        
        Args:
            size: Target file size in bytes
            tolerance_bytes: Maximum difference in bytes to consider similar
            
        Returns:
            List of FileInfo objects for files with similar sizes
        """
        similar_files = []
        min_size = size - tolerance_bytes
        max_size = size + tolerance_bytes
        
        for file_size in self.size_index:
            if min_size <= file_size <= max_size:
                similar_files.extend(self.files[path] for path in self.size_index[file_size])
        
        return similar_files
