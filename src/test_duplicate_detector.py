#!/usr/bin/env python3
"""
Tests for the duplicate detection engine functionality.
"""

import unittest
from pathlib import Path
from datetime import datetime, timezone
from src.duplicate_detector import DuplicateDetector, DuplicateGroup
from src.video_metadata import VideoMetadata
from src.data_structures import FileInfo

class TestDuplicateDetector(unittest.TestCase):
    def setUp(self):
        """Set up test data"""
        # Create some test video metadata
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
        
        self.resized_meta = VideoMetadata(
            duration=30.5,  # Same duration
            width=1280,     # Lower resolution
            height=720,
            codec="h264",
            bitrate=2000000,
            fps=30.0,
            audio_codec="aac",
            audio_sample_rate=44100,
            file_size=5000000
        )
        
        # Create test file info objects
        self.base_path = Path('/test_data')
        self.original_path = self.base_path / 'original' / 'video1.mp4'
        self.resized_path = self.base_path / 'resized' / 'video1.mp4'
        self.unrelated_path = self.base_path / 'original' / 'video2.mp4'
        
        # Earlier timestamp for original
        self.original_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
        # Later timestamp for resized copy
        self.resized_time = datetime(2023, 1, 2, tzinfo=timezone.utc)
        
        self.file_info_map = {
            self.original_path: FileInfo(
                self.original_path,
                created_at=self.original_time,
                modified_at=self.original_time,
                file_size=10000000,
                video_metadata=self.original_meta
            ),
            self.resized_path: FileInfo(
                self.resized_path,
                created_at=self.resized_time,
                modified_at=self.resized_time,
                file_size=5000000,
                video_metadata=self.resized_meta
            ),
            self.unrelated_path: FileInfo(
                self.unrelated_path,
                created_at=self.original_time,
                modified_at=self.original_time,
                file_size=8000000,
                video_metadata=VideoMetadata(
                    duration=45.0,  # Different duration
                    width=1920,
                    height=1080,
                    codec="h264",
                    bitrate=5000000,
                    fps=30.0,
                    audio_codec="aac",
                    audio_sample_rate=44100,
                    file_size=8000000
                )
            )
        }
        
        # Initialize detector with test data
        self.detector = DuplicateDetector(self.file_info_map)
    
    def test_find_duplicate_candidates(self):
        """Test identifying duplicate candidates"""
        duplicates = self.detector.find_duplicate_candidates()
        
        # Should find one group of duplicates
        self.assertEqual(len(duplicates), 1)
        
        # Check the duplicate group
        group = duplicates[0]
        self.assertEqual(group.filename, 'video1.mp4')
        self.assertEqual(group.original, self.original_path)
        self.assertEqual(len(group.duplicates), 1)
        self.assertEqual(group.duplicates[0], self.resized_path)
        self.assertGreater(group.confidence_score, DuplicateDetector.MIN_CONFIDENCE_SCORE)
    
    def test_different_duration_videos(self):
        """Test that videos with different durations aren't considered duplicates"""
        # Add another video with same name but different duration
        different_duration_path = self.base_path / 'backup' / 'video1.mp4'
        self.file_info_map[different_duration_path] = FileInfo(
            different_duration_path,
            created_at=self.original_time,
            modified_at=self.original_time,
            file_size=10000000,
            video_metadata=VideoMetadata(
                duration=35.5,  # Different duration
                width=1920,
                height=1080,
                codec="h264",
                bitrate=5000000,
                fps=30.0,
                audio_codec="aac",
                audio_sample_rate=44100,
                file_size=10000000
            )
        )
        
        detector = DuplicateDetector(self.file_info_map)
        duplicates = detector.find_duplicate_candidates()
        
        # Should still only find one group (original and resized)
        self.assertEqual(len(duplicates), 1)
        group = duplicates[0]
        self.assertEqual(len(group.duplicates), 1)
        self.assertNotIn(different_duration_path, group.all_files)
    
    def test_duration_tolerance(self):
        """Test that duration tolerance is respected"""
        # Add a video with slightly different duration (within tolerance)
        similar_duration_path = self.base_path / 'backup' / 'video1.mp4'
        self.file_info_map[similar_duration_path] = FileInfo(
            similar_duration_path,
            created_at=self.original_time,
            modified_at=self.original_time,
            file_size=10000000,
            video_metadata=VideoMetadata(
                duration=31.2,  # Within tolerance of 1 second
                width=1920,
                height=1080,
                codec="h264",
                bitrate=5000000,
                fps=30.0,
                audio_codec="aac",
                audio_sample_rate=44100,
                file_size=10000000
            )
        )
        
        detector = DuplicateDetector(self.file_info_map)
        duplicates = detector.find_duplicate_candidates()
        
        # Should find the group with all three files
        self.assertEqual(len(duplicates), 1)
        group = duplicates[0]
        self.assertEqual(len(group.duplicates), 2)
        self.assertIn(similar_duration_path, group.all_files)
    
    def test_identify_original(self):
        """Test that original identification considers resolution and timestamp"""
        # Create two candidates with different resolutions and timestamps
        low_res_old = (
            self.base_path / 'old_low.mp4',
            VideoMetadata(
                duration=30.0,
                width=1280,
                height=720,
                codec="h264",
                bitrate=2000000,
                fps=30.0,
                audio_codec="aac",
                audio_sample_rate=44100,
                file_size=5000000
            )
        )
        
        high_res_new = (
            self.base_path / 'new_high.mp4',
            VideoMetadata(
                duration=30.0,
                width=1920,
                height=1080,
                codec="h264",
                bitrate=5000000,
                fps=30.0,
                audio_codec="aac",
                audio_sample_rate=44100,
                file_size=10000000
            )
        )
        
        # Add FileInfo objects for the test
        self.file_info_map[low_res_old[0]] = FileInfo(
            low_res_old[0],
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            modified_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
            file_size=5000000,
            video_metadata=low_res_old[1]
        )
        
        self.file_info_map[high_res_new[0]] = FileInfo(
            high_res_new[0],
            created_at=datetime(2023, 2, 1, tzinfo=timezone.utc),
            modified_at=datetime(2023, 2, 1, tzinfo=timezone.utc),
            file_size=10000000,
            video_metadata=high_res_new[1]
        )
        
        detector = DuplicateDetector(self.file_info_map)
        original_path, score = detector._identify_original([
            (low_res_old[0], low_res_old[1]),
            (high_res_new[0], high_res_new[1])
        ])
        
        # Higher resolution should be chosen as original despite later timestamp
        self.assertEqual(original_path, high_res_new[0])
        self.assertGreaterEqual(score, detector.MIN_CONFIDENCE_SCORE)

if __name__ == '__main__':
    unittest.main(verbosity=2)
