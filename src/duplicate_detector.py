"""
Duplicate Detection Engine Module.

This module provides functionality to identify and validate duplicate video files
based on their metadata and characteristics.
"""

from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
import logging
from src.video_metadata import VideoMetadata
from src.data_structures import FileInfo

@dataclass
class DuplicateGroup:
    """Represents a group of potentially duplicate video files"""
    filename: str  # Base filename without directory
    original: Optional[Path]  # Path to the suspected original file
    duplicates: List[Path]  # Paths to suspected duplicates
    confidence_score: float  # 0-1 score indicating confidence in duplicate relationship
    
    @property
    def all_files(self) -> List[Path]:
        """Returns all files in the group including the original"""
        return [self.original] + self.duplicates if self.original else self.duplicates

class DuplicateDetector:
    """Identifies and validates duplicate video files"""
    
    DURATION_TOLERANCE = 1.0  # Maximum duration difference in seconds
    MIN_CONFIDENCE_SCORE = 0.7  # Minimum confidence score to consider as duplicate
    
    def __init__(self, file_info_map: Dict[Path, FileInfo]):
        """
        Initialize the detector with file information.
        
        Args:
            file_info_map: Dictionary mapping file paths to FileInfo objects
        """
        self.file_info_map = file_info_map
        self._filename_groups: Dict[str, Set[Path]] = {}
        self._build_filename_groups()
    
    def _build_filename_groups(self) -> None:
        """Group files by their base filename for initial candidate identification"""
        for path in self.file_info_map:
            filename = path.name
            if filename not in self._filename_groups:
                self._filename_groups[filename] = set()
            self._filename_groups[filename].add(path)
    
    def find_duplicate_candidates(self) -> List[DuplicateGroup]:
        """
        Identify potential duplicate files based on filename and duration.
        
        Returns:
            List of DuplicateGroup objects for files that might be duplicates
        """
        duplicate_groups: List[DuplicateGroup] = []
        
        # Process each group of files with the same filename
        for filename, paths in self._filename_groups.items():
            if len(paths) < 2:
                continue  # Skip files without duplicates
                
            # Get metadata for all files in the group
            files_metadata: List[Tuple[Path, VideoMetadata]] = []
            for path in paths:
                info = self.file_info_map[path]
                if info.video_metadata:
                    files_metadata.append((path, info.video_metadata))
            
            if len(files_metadata) < 2:
                continue  # Skip if we don't have metadata for at least 2 files
            
            # Compare durations within the group
            duration_matches: List[Tuple[Path, VideoMetadata]] = []
            base_duration = files_metadata[0][1].duration
            
            for path, metadata in files_metadata:
                if abs(metadata.duration - base_duration) <= self.DURATION_TOLERANCE:
                    duration_matches.append((path, metadata))
            
            if len(duration_matches) >= 2:
                # Find the likely original (highest resolution, earliest timestamp)
                original_path, score = self._identify_original(duration_matches)
                duplicates = [p for p, _ in duration_matches if p != original_path]
                
                group = DuplicateGroup(
                    filename=filename,
                    original=original_path,
                    duplicates=duplicates,
                    confidence_score=score
                )
                duplicate_groups.append(group)
        
        return duplicate_groups
    
    def _identify_original(
        self, candidates: List[Tuple[Path, VideoMetadata]]
    ) -> Tuple[Path, float]:
        """
        Identify the likely original file from a group of candidates.
        
        Args:
            candidates: List of (path, metadata) tuples for candidate files
            
        Returns:
            Tuple of (original_path, confidence_score)
        """
        max_resolution = 0
        earliest_time = float('inf')
        original_path = None
        total_score = 0.0
        
        # Find highest resolution and earliest timestamp
        for path, metadata in candidates:
            resolution = metadata.width * metadata.height
            timestamp = self.file_info_map[path].created_at.timestamp()
            
            if resolution > max_resolution:
                max_resolution = resolution
            if timestamp < earliest_time:
                earliest_time = timestamp
        
        # Score each candidate
        for path, metadata in candidates:
            resolution = metadata.width * metadata.height
            timestamp = self.file_info_map[path].created_at.timestamp()
            
            # Calculate score components
            resolution_score = resolution / max_resolution  # 0-1 score for resolution
            time_score = 1 - ((timestamp - earliest_time) / (86400 * 30))  # Time diff in 30 days
            time_score = max(0, min(1, time_score))  # Clamp between 0-1
            
            # Weighted score (resolution more important than timestamp)
            score = (resolution_score * 0.7) + (time_score * 0.3)
            
            if score > total_score:
                total_score = score
                original_path = path
        
        return original_path, total_score
