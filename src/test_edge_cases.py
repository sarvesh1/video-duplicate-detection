#!/usr/bin/env python3
"""
Tests for edge case handling and action recommendations.
"""

import unittest
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

from src.duplicate_detector import (
    DuplicateDetector, DuplicateGroup, VideoRelationship,
    EdgeCaseAnalysis, ActionRecommendation, EdgeCaseType,
    Severity, Action
)
from src.video_metadata import VideoMetadata
from src.data_structures import FileInfo

class TestEdgeCases(unittest.TestCase):
    """Test edge case detection and action recommendations"""
    
    def setUp(self):
        """Set up test data"""
        self.base_path = Path('/test_data')
        self.original_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
        self.modified_time = datetime(2023, 1, 2, tzinfo=timezone.utc)
        
        # Create original file metadata
        self.original_meta = VideoMetadata(
            duration=30.5,
            width=1920,
            height=1080,
            codec="h264",
            bitrate=5000000,
            fps=30.0,
            audio_codec="aac",
            audio_sample_rate=44100,
            file_size=10000000
        )
        
        # Create paths
        self.original_path = self.base_path / 'original' / 'video.mp4'
        self.duplicate_path = self.base_path / 'duplicates' / 'video.mp4'
        
        # Create file info map
        self.file_info_map = {
            self.original_path: FileInfo(
                path=self.original_path,
                created_at=self.original_time,
                modified_at=self.original_time,
                file_size=10000000,
                video_metadata=self.original_meta
            )
        }
        
        # Create detector instance
        self.detector = DuplicateDetector(self.file_info_map)
    
    def test_aspect_ratio_mismatch(self):
        """Test detection of aspect ratio mismatches"""
        # Create a video with different aspect ratio
        different_meta = VideoMetadata(
            duration=30.5,
            width=1280,
            height=960,  # 4:3 instead of 16:9
            codec="h264",
            bitrate=3000000,
            fps=30.0,
            audio_codec="aac",
            audio_sample_rate=44100,
            file_size=6000000
        )
        
        different_path = self.base_path / 'duplicates' / 'different_ratio.mp4'
        self.file_info_map[different_path] = FileInfo(
            path=different_path,
            created_at=self.modified_time,
            modified_at=self.modified_time,
            file_size=6000000,
            video_metadata=different_meta
        )
        
        group = DuplicateGroup(
            filename='video.mp4',
            original=self.original_path,
            duplicates=[different_path],
            confidence_score=0.8
        )
        
        # First validate the duplicate
        validated_group = self.detector.validate_duplicates(group)
        
        # Then analyze edge cases
        edge_cases = self.detector.analyze_edge_cases(validated_group)
        
        self.assertEqual(len(edge_cases), 1)
        case = edge_cases[0]
        
        self.assertEqual(case.issue_type, EdgeCaseType.ASPECT_RATIO)
        self.assertEqual(case.severity, Severity.MEDIUM)
        self.assertIn("aspect ratio mismatch", case.details.lower())
    
    def test_missing_metadata(self):
        """Test handling of files with missing metadata"""
        missing_meta_path = self.base_path / 'corrupt' / 'video.mp4'
        self.file_info_map[missing_meta_path] = FileInfo(
            path=missing_meta_path,
            created_at=self.modified_time,
            modified_at=self.modified_time,
            file_size=5000000,
            video_metadata=None  # Missing metadata
        )
        
        group = DuplicateGroup(
            filename='video.mp4',
            original=self.original_path,
            duplicates=[missing_meta_path],
            confidence_score=0.5
        )
        
        edge_cases = self.detector.analyze_edge_cases(group)
        
        self.assertEqual(len(edge_cases), 1)
        case = edge_cases[0]
        
        self.assertEqual(case.issue_type, EdgeCaseType.METADATA)
        self.assertEqual(case.severity, Severity.HIGH)
        self.assertIn("missing", case.details.lower())
    
    def test_action_recommendations(self):
        """Test action recommendation generation"""
        # Create three duplicates with different characteristics
        
        # 1. Good duplicate (safe to delete)
        good_meta = VideoMetadata(
            duration=30.5,
            width=1280,
            height=720,
            codec="h264",
            bitrate=2000000,
            fps=30.0,
            audio_codec="aac",
            audio_sample_rate=44100,
            file_size=5000000
        )
        
        good_path = self.base_path / 'duplicates' / 'good.mp4'
        self.file_info_map[good_path] = FileInfo(
            path=good_path,
            created_at=self.modified_time,
            modified_at=self.modified_time,
            file_size=5000000,
            video_metadata=good_meta
        )
        
        # 2. Suspicious duplicate (needs verification)
        suspicious_meta = VideoMetadata(
            duration=30.5,
            width=1280,
            height=720,
            codec="h264",
            bitrate=4000000,  # Unexpectedly high bitrate
            fps=30.0,
            audio_codec="aac",
            audio_sample_rate=44100,
            file_size=8000000  # Unexpectedly large
        )
        
        suspicious_path = self.base_path / 'duplicates' / 'suspicious.mp4'
        self.file_info_map[suspicious_path] = FileInfo(
            path=suspicious_path,
            created_at=self.modified_time,
            modified_at=self.modified_time,
            file_size=8000000,
            video_metadata=suspicious_meta
        )
        
        # 3. Different aspect ratio (needs manual review)
        different_meta = VideoMetadata(
            duration=30.5,
            width=1280,
            height=960,
            codec="h264",
            bitrate=3000000,
            fps=30.0,
            audio_codec="aac",
            audio_sample_rate=44100,
            file_size=6000000
        )
        
        different_path = self.base_path / 'duplicates' / 'different.mp4'
        self.file_info_map[different_path] = FileInfo(
            path=different_path,
            created_at=self.modified_time,
            modified_at=self.modified_time,
            file_size=6000000,
            video_metadata=different_meta
        )
        
        # Create and validate the group
        group = DuplicateGroup(
            filename='video.mp4',
            original=self.original_path,
            duplicates=[good_path, suspicious_path, different_path],
            confidence_score=0.8
        )
        
        validated_group = self.detector.validate_duplicates(group)
        recommendations = self.detector.get_action_recommendations(validated_group)
        
        # Check recommendations
        self.assertEqual(len(recommendations), 4)  # Original + 3 duplicates
        
        by_path = {r.file_path: r for r in recommendations}
        
        # Original should be preserved
        self.assertEqual(by_path[self.original_path].action, Action.PRESERVE)
        
        # Good duplicate should be safe to delete
        self.assertEqual(by_path[good_path].action, Action.SAFE_DELETE)
        
        # Suspicious duplicate should need verification
        self.assertEqual(by_path[suspicious_path].action, Action.VERIFY)
        
        # Different aspect ratio should need manual review
        self.assertEqual(by_path[different_path].action, Action.MANUAL_REVIEW)

if __name__ == '__main__':
    unittest.main()
