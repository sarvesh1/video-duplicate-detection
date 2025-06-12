#!/usr/bin/env python3
"""
Tests for video metadata extraction functionality.
"""

import unittest
import os
from pathlib import Path
import sys
import shutil

# Add the src directory to Python path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from video_metadata import VideoMetadataParser, VideoMetadata

class TestVideoMetadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test data directory and ensure test video exists"""
        cls.base_dir = Path(__file__).parent.parent
        cls.test_data_dir = cls.base_dir / 'test_data'
        cls.test_video_path = cls.test_data_dir / 'original' / 'video1.mp4'
        
        if not cls.test_video_path.exists():
            raise unittest.SkipTest(f"Test video not found at {cls.test_video_path}")
    
    def test_video_metadata_extraction(self):
        """Test basic video metadata extraction"""
        metadata = VideoMetadataParser.parse_video(self.test_video_path)
        
        # Check if metadata was extracted successfully
        self.assertIsNotNone(metadata, "Metadata extraction failed")
        self.assertIsInstance(metadata, VideoMetadata)
        
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
        invalid_path = self.test_data_dir / "nonexistent.mp4"
        metadata = VideoMetadataParser.parse_video(invalid_path)
        self.assertIsNone(metadata)
        
    def test_video_comparison(self):
        """Test comparing metadata of original and backup videos"""
        original_path = self.test_data_dir / 'original' / 'video2.mp4'
        backup_path = self.test_data_dir / 'backup' / 'video2.mp4'
        
        if not (original_path.exists() and backup_path.exists()):
            self.skipTest("Test video files not found")
            
        original_meta = VideoMetadataParser.parse_video(original_path)
        backup_meta = VideoMetadataParser.parse_video(backup_path)
        
        self.assertIsNotNone(original_meta)
        self.assertIsNotNone(backup_meta)
        self.assertEqual(original_meta.resolution, backup_meta.resolution)
        self.assertEqual(original_meta.duration, backup_meta.duration)
        self.assertEqual(original_meta.codec, backup_meta.codec)

if __name__ == '__main__':
    unittest.main(verbosity=2)

if __name__ == '__main__':
    unittest.main()
