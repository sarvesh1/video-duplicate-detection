#!/usr/bin/env python3
"""
Tests for the duplicate detection engine functionality.
"""

import unittest
from pathlib import Path
from datetime import datetime, timezone
from src.duplicate_detector import (
    DuplicateDetector, DuplicateGroup, VideoRelationship,
    ResolutionVariant, ValidationResult
)
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

    def test_validate_duplicates(self):
        """Test validation of suspected duplicates"""
        # Create a duplicate group with original and resized copy
        group = DuplicateGroup(
            filename='video1.mp4',
            original=self.original_path,
            duplicates=[self.resized_path],
            confidence_score=0.8
        )
        
        # Validate the group
        validated_group = self.detector.validate_duplicates(group)
        
        # Check that we have validation results
        self.assertIn(self.resized_path, validated_group.validation_results)
        result = validated_group.validation_results[self.resized_path]
        
        # Aspect ratio should match (1920/1080 ≈ 1280/720)
        self.assertTrue(result.aspect_ratio_match)
        
        # Timestamps are within allowed range
        self.assertTrue(result.timestamp_valid)
        
        # Size and bitrate correlate with resolution change
        self.assertTrue(result.size_correlation_valid)
        self.assertTrue(result.bitrate_valid)
        
        # Overall score should be high
        self.assertGreaterEqual(result.overall_score, DuplicateDetector.MIN_CONFIDENCE_SCORE)
    
    def test_validate_aspect_ratio_mismatch(self):
        """Test validation with mismatched aspect ratios"""
        # Create a video with different aspect ratio
        different_aspect_path = self.base_path / 'weird' / 'video1.mp4'
        self.file_info_map[different_aspect_path] = FileInfo(
            different_aspect_path,
            created_at=self.resized_time,
            modified_at=self.resized_time,
            file_size=6000000,
            video_metadata=VideoMetadata(
                duration=30.5,
                width=1280,    # 16:10 instead of 16:9
                height=800,
                codec="h264",
                bitrate=2000000,
                fps=30.0,
                audio_codec="aac",
                audio_sample_rate=44100,
                file_size=6000000
            )
        )
        
        group = DuplicateGroup(
            filename='video1.mp4',
            original=self.original_path,
            duplicates=[different_aspect_path],
            confidence_score=0.8
        )
        
        validated_group = self.detector.validate_duplicates(group)
        result = validated_group.validation_results[different_aspect_path]
        
        # Aspect ratio should not match
        self.assertFalse(result.aspect_ratio_match)
        self.assertIn("aspect ratio mismatch", result.reason)
        
        # Overall score should be lower
        self.assertLess(result.overall_score, 0.8)
    
    def test_validate_suspicious_timestamp(self):
        """Test validation with suspicious timestamps"""
        # Create a video with timestamp far in the future
        future_path = self.base_path / 'future' / 'video1.mp4'
        future_time = datetime(2024, 1, 1, tzinfo=timezone.utc)  # 1 year later
        
        self.file_info_map[future_path] = FileInfo(
            future_path,
            created_at=future_time,
            modified_at=future_time,
            file_size=5000000,
            video_metadata=self.resized_meta
        )
        
        group = DuplicateGroup(
            filename='video1.mp4',
            original=self.original_path,
            duplicates=[future_path],
            confidence_score=0.8
        )
        
        validated_group = self.detector.validate_duplicates(group)
        result = validated_group.validation_results[future_path]
        
        # Timestamp should be invalid (too far apart)
        self.assertFalse(result.timestamp_valid)
        self.assertIn("suspicious timestamp", result.reason)
    
    def test_validate_size_mismatch(self):
        """Test validation with unexpected file sizes"""
        # Create a video with unexpected file size for its resolution
        wrong_size_path = self.base_path / 'wrong_size' / 'video1.mp4'
        self.file_info_map[wrong_size_path] = FileInfo(
            wrong_size_path,
            created_at=self.resized_time,
            modified_at=self.resized_time,
            file_size=9000000,  # Too large for the lower resolution
            video_metadata=VideoMetadata(
                duration=30.5,
                width=1280,
                height=720,
                codec="h264",
                bitrate=4500000,  # Bitrate too high for resolution
                fps=30.0,
                audio_codec="aac",
                audio_sample_rate=44100,
                file_size=9000000
            )
        )
        
        group = DuplicateGroup(
            filename='video1.mp4',
            original=self.original_path,
            duplicates=[wrong_size_path],
            confidence_score=0.8
        )
        
        validated_group = self.detector.validate_duplicates(group)
        result = validated_group.validation_results[wrong_size_path]
        
        # Size and bitrate should be invalid (too large for resolution)
        self.assertFalse(result.size_correlation_valid)
        self.assertFalse(result.bitrate_valid)
        self.assertIn("unexpected file size", result.reason)
        self.assertIn("unexpected bitrate", result.reason)

    def test_build_relationships(self):
        """Test building relationships between originals and variants"""
        relationships = self.detector.build_relationships()
        
        # Should find one relationship
        self.assertEqual(len(relationships), 1)
        
        rel = relationships[0]
        self.assertEqual(rel.filename, 'video1.mp4')
        self.assertEqual(rel.original.path, self.original_path)
        self.assertEqual(len(rel.variants), 1)
        
        # Check resolution chain is in descending order
        chain = rel.resolution_chain
        self.assertEqual(len(chain), 2)
        self.assertEqual(chain[0], (1920, 1080))  # Original
        self.assertEqual(chain[1], (1280, 720))   # Variant
    
    def test_analyze_resolution_chain(self):
        """Test analyzing resolution chain for consistency"""
        # Create a relationship with common resolution variants
        original = ResolutionVariant(
            path=self.base_path / 'original' / 'video.mp4',
            width=1920,
            height=1080,
            created_at=self.original_time,
            confidence_score=1.0
        )
        
        variants = [
            # 720p (0.666 scale)
            ResolutionVariant(
                path=self.base_path / 'variants' / '720p.mp4',
                width=1280,
                height=720,
                created_at=self.resized_time,
                confidence_score=0.9
            ),
            # 480p (0.444 scale)
            ResolutionVariant(
                path=self.base_path / 'variants' / '480p.mp4',
                width=854,
                height=480,
                created_at=self.resized_time,
                confidence_score=0.85
            )
        ]
        
        relationship = VideoRelationship(
            original=original,
            variants=variants,
            filename='video.mp4',
            total_confidence=0.9,
            validation_results={}
        )
        
        analysis = self.detector.analyze_resolution_chain(relationship)
        
        # Check resolution chain analysis
        self.assertTrue(analysis['is_consistent'])
        self.assertEqual(len(analysis['resolutions']), 3)
        self.assertEqual(analysis['resolution_count'], 3)
        
        # Check scale ratios (1080p -> 720p -> 480p)
        scale_ratios = analysis['scale_ratios']
        self.assertIn(0.67, scale_ratios)  # 1080p -> 720p (approximately)
        
    def test_complex_resolution_chain(self):
        """Test handling of complex resolution chain scenarios"""
        # Create a relationship with unusual resolution variants
        original = ResolutionVariant(
            path=self.base_path / 'original' / 'video.mp4',
            width=1920,
            height=1080,
            created_at=self.original_time,
            confidence_score=1.0
        )
        
        variants = [
            # Normal 720p variant
            ResolutionVariant(
                path=self.base_path / 'variants' / '720p.mp4',
                width=1280,
                height=720,
                created_at=self.resized_time,
                confidence_score=0.9
            ),
            # Unusual aspect ratio variant
            ResolutionVariant(
                path=self.base_path / 'variants' / 'unusual.mp4',
                width=1280,
                height=960,  # 4:3 instead of 16:9
                created_at=self.resized_time,
                confidence_score=0.7
            )
        ]
        
        relationship = VideoRelationship(
            original=original,
            variants=variants,
            filename='video.mp4',
            total_confidence=0.8,
            validation_results={}
        )
        
        analysis = self.detector.analyze_resolution_chain(relationship)
        
        # Chain should be marked as inconsistent due to aspect ratio mismatch
        self.assertFalse(analysis['is_consistent'])
        self.assertEqual(analysis['resolution_count'], 3)

if __name__ == '__main__':
    unittest.main(verbosity=2)
