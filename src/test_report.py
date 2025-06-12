"""
Unit tests for the reporting module.
"""

import unittest
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

from data_structures import MetadataStore, FileInfo
from video_metadata import VideoMetadata
from duplicate_detector import ResolutionVariant, VideoRelationship, ValidationResult
from report import ReportGenerator, DuplicateAnalysis

class TestReport(unittest.TestCase):
    def setUp(self):
        """Set up test data"""
        self.base_path = Path('/test_data')
        self.original_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
        self.resized_time = datetime(2023, 1, 2, tzinfo=timezone.utc)
        
        # Create test metadata
        # Create test metadata
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
        
        self.resized_meta_720p = VideoMetadata(
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
        
        self.resized_meta_480p = VideoMetadata(
            duration=30.5,
            width=854,
            height=480,
            codec="h264",
            bitrate=1000000,
            fps=30.0,
            audio_codec="aac",
            audio_sample_rate=44100,
            file_size=2500000
        )
        
        # Create file paths
        self.original_path = self.base_path / 'original' / 'video.mp4'
        self.resized_720p_path = self.base_path / 'resized' / '720p.mp4'
        self.resized_480p_path = self.base_path / 'resized' / '480p.mp4'
        
        # Create MetadataStore
        self.store = MetadataStore()
        
        # Add original file
        self.store.add_file(FileInfo(
            path=self.original_path,
            file_size=10000000,
            created_at=self.original_time,
            modified_at=self.original_time,
            video_metadata=self.original_meta
        ))
        
        # Add 720p file
        self.store.add_file(FileInfo(
            path=self.resized_720p_path,
            file_size=5000000,
            created_at=self.resized_time,
            modified_at=self.resized_time,
            video_metadata=self.resized_meta_720p
        ))
        
        # Add 480p file
        self.store.add_file(FileInfo(
            path=self.resized_480p_path,
            file_size=2500000,
            created_at=self.resized_time,
            modified_at=self.resized_time,
            video_metadata=self.resized_meta_480p
        ))
        
        # Create resolution variants
        self.original = ResolutionVariant(
            path=self.original_path,
            width=1920,
            height=1080,
            created_at=self.original_time,
            confidence_score=1.0
        )
        
        self.variants = [
            ResolutionVariant(
                path=self.resized_720p_path,
                width=1280,
                height=720,
                created_at=self.resized_time,
                confidence_score=0.9
            ),
            ResolutionVariant(
                path=self.resized_480p_path,
                width=854,
                height=480,
                created_at=self.resized_time,
                confidence_score=0.85
            )
        ]
        
        # Create relationship
        self.relationship = VideoRelationship(
            original=self.original,
            variants=self.variants,
            filename='video.mp4',
            total_confidence=0.9,
            validation_results={}
        )
        
        # Create report generator
        self.generator = ReportGenerator(
            relationships=[self.relationship],
            base_dir=self.base_path,
            metadata_store=self.store
        )

    def test_analyze_relationships(self):
        """Test relationship analysis"""
        analyses = self.generator.analyze_relationships()
        
        self.assertEqual(len(analyses), 1)
        analysis = analyses[0]
        
        # Check original file details
        self.assertEqual(analysis.original_path, self.original_path)
        self.assertEqual(analysis.original_resolution, "1920x1080")
        self.assertEqual(analysis.confidence_score, 0.9)
        
        # Check duplicates
        self.assertEqual(len(analysis.duplicates), 2)
        
        # Check first duplicate (720p)
        dup_720p = next(d for d in analysis.duplicates if d['resolution'] == "1280x720")
        self.assertEqual(dup_720p['path'], self.resized_720p_path)
        self.assertEqual(dup_720p['size'], 5000000)
        self.assertEqual(dup_720p['confidence'], 0.9)
        
        # Check second duplicate (480p)
        dup_480p = next(d for d in analysis.duplicates if d['resolution'] == "854x480")
        self.assertEqual(dup_480p['path'], self.resized_480p_path)
        self.assertEqual(dup_480p['size'], 2500000)
        self.assertEqual(dup_480p['confidence'], 0.85)
        
        # Check size calculations
        self.assertEqual(analysis.total_size, 17500000)  # Original + 720p + 480p
        self.assertEqual(analysis.potential_savings, 7500000)  # 720p + 480p

    def test_validate_resolution_chain(self):
        """Test resolution chain validation"""
        chain_analysis = self.generator._validate_resolution_chain(self.relationship)
        
        self.assertTrue(chain_analysis['is_consistent'])
        self.assertEqual(chain_analysis['resolution_count'], 3)
        
        # Check scale ratios (1080p -> 720p -> 480p)
        scale_ratios = chain_analysis['scale_ratios']
        self.assertIn(0.67, scale_ratios)  # 1080p -> 720p
        self.assertIn(0.44, scale_ratios)  # 720p -> 480p
        
        # Check for missing common ratios
        self.assertEqual(len(chain_analysis['missing_common_ratios']), 0)

    def test_inconsistent_resolution_chain(self):
        """Test handling of inconsistent resolution chains"""
        # Create variant with unusual aspect ratio
        unusual_variant = ResolutionVariant(
            path=self.base_path / 'resized' / 'unusual.mp4',
            width=1280,
            height=960,  # 4:3 instead of 16:9
            created_at=self.resized_time,
            confidence_score=0.7
        )
        
        relationship = VideoRelationship(
            original=self.original,
            variants=[unusual_variant],
            filename='video.mp4',
            total_confidence=0.7,
            validation_results={}
        )
        
        generator = ReportGenerator(
            relationships=[relationship],
            base_dir=self.base_path,
            metadata_store=self.store
        )
        
        analyses = generator.analyze_relationships()
        
        # Check that inconsistency was detected
        self.assertFalse(analyses[0].resolution_chain_valid)
        self.assertIn("Inconsistent resolution scaling", analyses[0].issues)

    def test_relative_path_generation(self):
        """Test relative path generation"""
        # Test path inside base directory
        rel_path = self.generator._get_relative_path(self.original_path)
        self.assertEqual(rel_path, "original/video.mp4")
        
        # Test path outside base directory
        outside_path = Path("/other/path/video.mp4")
        abs_path = self.generator._get_relative_path(outside_path)
        self.assertEqual(abs_path, str(outside_path))

    def test_generate_text_report(self):
        """Test text report generation"""
        report = self.generator.generate_text_report()
        
        # Check report contains key information
        self.assertIn("=== Video Duplicate Analysis Report ===", report)
        self.assertIn("Total duplicate groups: 1", report)
        self.assertIn("Total duplicate files: 2", report)
        self.assertIn("Resolution: 1920x1080", report)
        self.assertIn("Resolution: 1280x720", report)
        self.assertIn("Resolution: 854x480", report)
        self.assertIn("Size:", report)
        self.assertIn("Confidence Score:", report)
        
        # Check formatting
        self.assertIn("Group 1:", report)
        self.assertIn("Original:", report)
        self.assertIn("Duplicates:", report)
        
        # Verify all paths are relative
        self.assertNotIn(str(self.base_path), report)
        self.assertIn("original/video.mp4", report)
        self.assertIn("resized/720p.mp4", report)
        self.assertIn("resized/480p.mp4", report)

if __name__ == '__main__':
    unittest.main()
