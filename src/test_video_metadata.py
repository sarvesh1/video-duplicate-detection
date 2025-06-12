#!/usr/bin/env python3
"""
Tests for video metadata extraction functionality.
"""

import unittest
import os
from pathlib import Path
import sys
import shutil
import tempfile

# Add the src directory to Python path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from video_metadata import VideoMetadataParser, VideoMetadata

class TestVideoMetadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test data directory and ensure test video exists"""
        cls.base_dir = Path(__file__).parent.parent
        cls.test_data_dir = cls.base_dir / 'test_data'
        cls.original_dir = cls.test_data_dir / 'original'
        cls.backup_dir = cls.test_data_dir / 'backup'
        
        # Create test directories if they don't exist
        cls.original_dir.mkdir(parents=True, exist_ok=True)
        cls.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Test video paths - using  PXL_20230724_104955429_2.mp4 which exists in both original and backup
        cls.test_video_path = cls.original_dir / 'PXL_20230724_104955429_2.mp4'
        cls.nonexistent_video = cls.test_data_dir / 'nonexistent.mp4'
        
        # Create a corrupted video file for testing
        cls.corrupted_video = cls.test_data_dir / 'corrupted.mp4'
        with open(cls.corrupted_video, 'wb') as f:
            f.write(b'This is not a valid video file')
    
    @classmethod
    def tearDownClass(cls):
        """Clean up temporary test files"""
        if cls.corrupted_video.exists():
            cls.corrupted_video.unlink()
    
    def setUp(self):
        """Verify test environment before each test"""
        if not self.test_video_path.exists():
            self.skipTest(f"Test video not found at {self.test_video_path}. Please ensure test data is available.")
    
    def test_video_metadata_extraction(self):
        """Test basic video metadata extraction"""
        metadata = VideoMetadataParser.parse_video(self.test_video_path)
        
        # First verify that we got metadata back
        self.assertIsNotNone(metadata, "Metadata extraction failed")
        self.assertIsInstance(metadata, VideoMetadata)
        
        # Only proceed with other checks if we have metadata
        if metadata:
            # Basic validation
            self.assertGreater(metadata.duration, 0, "Duration should be greater than 0")
            self.assertGreater(metadata.width, 0, "Width should be greater than 0")
            self.assertGreater(metadata.height, 0, "Height should be greater than 0")
            self.assertGreater(metadata.bitrate, 0, "Bitrate should be greater than 0")
            self.assertGreater(metadata.fps, 0, "FPS should be greater than 0")
            
            # Resolution string format
            self.assertRegex(
                metadata.resolution,
                r'^\d+x\d+$',
                f"Resolution {metadata.resolution} should be in format WIDTHxHEIGHT"
            )
            
            # Duration formatting
            self.assertRegex(
                metadata.duration_formatted,
                r'^\d+:\d{2}:\d{2}$',
                f"Duration {metadata.duration_formatted} should be in format HH:MM:SS"
            )
    
    def test_metadata_properties(self):
        """Test the property methods of VideoMetadata"""
        # Create a sample metadata object
        metadata = VideoMetadata(
            duration=3723.5,  # 1h 2m 3.5s
            width=1920,
            height=1080,
            codec="h264",
            bitrate=5000000,
            fps=29.97,
            audio_codec="aac",
            audio_sample_rate=44100
        )
        
        self.assertEqual(metadata.resolution, "1920x1080")
        self.assertEqual(metadata.duration_formatted, "1:02:03")
    
    def test_metadata_validation(self):
        """Test metadata validation function"""
        # Create a valid metadata object
        valid_metadata = VideoMetadata(
            duration=60.0,
            width=1280,
            height=720,
            codec="h264",
            bitrate=2000000,
            fps=30.0,
            audio_codec="aac",
            audio_sample_rate=44100
        )
        
        validation = VideoMetadataParser.validate_metadata(valid_metadata)
        
        self.assertIsInstance(validation, dict)
        self.assertTrue(validation['has_valid_duration'])
        self.assertTrue(validation['has_valid_dimensions'])
        self.assertTrue(validation['has_valid_bitrate'])
        self.assertTrue(validation['has_valid_fps'])
        self.assertTrue(validation['has_audio'])
    
    def test_invalid_file(self):
        """Test handling of invalid video files"""
        metadata = VideoMetadataParser.parse_video(self.nonexistent_video)
        self.assertIsNone(metadata, "Metadata should be None for nonexistent file")
        
        # Test with corrupted video file
        metadata = VideoMetadataParser.parse_video(self.corrupted_video)
        self.assertIsNone(metadata, "Metadata should be None for corrupted file")
        
        # Test with directory path
        metadata = VideoMetadataParser.parse_video(self.test_data_dir)
        self.assertIsNone(metadata, "Metadata should be None when path is a directory")
    
    def test_empty_video(self):
        """Test handling of empty video files"""
        # Create a temporary empty file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            metadata = VideoMetadataParser.parse_video(tmp_path)
            self.assertIsNone(metadata, "Metadata should be None for empty file")
        finally:
            # Clean up
            tmp_path.unlink()
    
    def test_video_comparison(self):
        """Test comparison of metadata between original and backup videos"""
        # Skip if PXL_20230724_104955429_2.mp4 doesn't exist in both directories
        original_path = self.original_dir / 'PXL_20230724_104955429_2.mp4'
        backup_path = self.backup_dir / 'PXL_20230724_104955429_2.mp4'
        
        if not (original_path.exists() and backup_path.exists()):
            self.skipTest("Test files PXL_20230724_104955429_2.mp4 not found in both original and backup directories")
        
        # Extract metadata from both files
        original_meta = VideoMetadataParser.parse_video(original_path)
        backup_meta = VideoMetadataParser.parse_video(backup_path)
        
        # Check that metadata was extracted successfully
        self.assertIsNotNone(original_meta, "Failed to extract metadata from original video")
        self.assertIsNotNone(backup_meta, "Failed to extract metadata from backup video")
        
        if original_meta and backup_meta:
            # Compare key attributes
            self.assertEqual(original_meta.resolution, backup_meta.resolution, 
                           "Resolution should match between original and backup")
            self.assertEqual(original_meta.duration, backup_meta.duration,
                           "Duration should match between original and backup")
            self.assertEqual(original_meta.codec, backup_meta.codec,
                           "Codec should match between original and backup")

if __name__ == '__main__':
    unittest.main(verbosity=2)

if __name__ == '__main__':
    unittest.main()
