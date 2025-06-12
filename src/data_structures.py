"""
Core data structures for storing and indexing video file metadata.
"""

from collections import defaultdict
from typing import Dict, List, Set
from scanner import FileMetadata

class MetadataStore:
    """
    Central data store for file metadata with multiple indices for efficient lookup.
    """
    
    def __init__(self):
        # Primary storage: path -> metadata
        self.files: Dict[str, FileMetadata] = {}
        
        # Filename index: filename -> set of paths
        self.filename_index: Dict[str, Set[str]] = defaultdict(set)
        
        # Directory index: directory -> set of paths
        self.directory_index: Dict[str, Set[str]] = defaultdict(set)
        
        # Size-based index: size -> set of paths (for potential duplicates)
        self.size_index: Dict[int, Set[str]] = defaultdict(set)
    
    def add_file(self, metadata: FileMetadata) -> None:
        """
        Add a file's metadata to the store and update all indices
        
        Args:
            metadata: FileMetadata object containing file information
        """
        self.files[metadata.file_path] = metadata
        self.filename_index[metadata.filename].add(metadata.file_path)
        self.directory_index[metadata.directory].add(metadata.file_path)
        self.size_index[metadata.file_size].add(metadata.file_path)
    
    def get_by_filename(self, filename: str) -> List[FileMetadata]:
        """
        Get all files with a given filename
        
        Args:
            filename: Name of the file to search for
            
        Returns:
            List of FileMetadata objects for matching files
        """
        paths = self.filename_index.get(filename, set())
        return [self.files[path] for path in paths]
    
    def get_by_directory(self, directory: str) -> List[FileMetadata]:
        """
        Get all files in a specific directory
        
        Args:
            directory: Directory path to search in
            
        Returns:
            List of FileMetadata objects for files in the directory
        """
        paths = self.directory_index.get(directory, set())
        return [self.files[path] for path in paths]
    
    def get_similar_sizes(self, size: int, tolerance_bytes: int = 1024) -> List[FileMetadata]:
        """
        Get files with similar sizes (within tolerance)
        
        Args:
            size: Target file size in bytes
            tolerance_bytes: Size difference tolerance in bytes
            
        Returns:
            List of FileMetadata objects for files with similar sizes
        """
        similar_files = []
        for s in range(size - tolerance_bytes, size + tolerance_bytes + 1):
            if s in self.size_index:
                similar_files.extend(self.files[path] for path in self.size_index[s])
        return similar_files
