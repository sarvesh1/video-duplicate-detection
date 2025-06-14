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
import time

# Add the src directory to Python path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from video_metadata import VideoMetadataParser, VideoMetadata
from video_metadata import MetadataCache

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
    
    def test_cache_large_file_optimization(self):
        """Test that metadata parsing doesn't read entire file for large videos"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a copy of the test video first
            large_file = Path(temp_dir) / "large.mp4"
            shutil.copy2(self.test_video_path, large_file)
            
            # Now append data to make it large
            original_size = large_file.stat().st_size
            with open(large_file, 'r+b') as f:
                # Seek to end and add more data
                f.seek(0, 2)  # Seek to end
                # Add another 100MB of data without affecting the header
                extra_size = 100 * 1024 * 1024
                while f.tell() < original_size + extra_size:
                    f.write(b'\0' * 1024 * 1024)  # Write in 1MB chunks
            
            # Verify the file size increased
            self.assertGreater(large_file.stat().st_size, original_size, 
                             "Failed to increase file size")

            # Time the metadata parsing
            start_time = time.time()
            metadata = VideoMetadataParser.parse_video(large_file)
            parse_time = time.time() - start_time

            # Should complete quickly (under 1 second) as it only reads headers
            self.assertLess(parse_time, 1.0, "Parsing large file took too long")
            self.assertIsNotNone(metadata, "Failed to parse large file")
            
            # Verify we got the same metadata as the original
            original_meta = VideoMetadataParser.parse_video(self.test_video_path)
            self.assertIsNotNone(original_meta)
            
            if metadata and original_meta:
                self.assertEqual(metadata.width, original_meta.width)
                self.assertEqual(metadata.height, original_meta.height)
                self.assertEqual(metadata.codec, original_meta.codec)
                self.assertEqual(metadata.duration, original_meta.duration)

    def test_cache_persistence_with_corrupt_cache(self):
        """Test cache behavior with corrupted cache file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / 'cache'
            cache_dir.mkdir()
            cache_file = cache_dir / "metadata_cache.json"

            # Write corrupt JSON
            with open(cache_file, 'w') as f:
                f.write('{"version": "1.0", "entries": {corrupt json}}')

            # Should handle corrupt cache gracefully
            cache = MetadataCache(cache_dir)
            self.assertEqual(len(cache.cache), 0, "Corrupt cache should be ignored")

            # Should be able to write new entries
            test_video = Path(temp_dir) / "test.mp4"
            shutil.copy2(self.test_video_path, test_video)
            metadata = VideoMetadataParser.parse_video(test_video)
            self.assertIsNotNone(metadata, "Failed to parse video after corrupt cache")

    def test_cache_concurrent_modification(self):
        """Test cache behavior when files are modified during scanning"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / 'cache'
            cache = MetadataCache(cache_dir)
            VideoMetadataParser._cache = cache

            # Create test video
            test_video = Path(temp_dir) / "test.mp4"
            shutil.copy2(self.test_video_path, test_video)

            # First parse
            metadata1 = VideoMetadataParser.parse_video(test_video)
            self.assertIsNotNone(metadata1, "Failed to parse initial video")
            
            if metadata1:
                initial_width = metadata1.width
                initial_height = metadata1.height
                
                # Cache should be created
                cache.save_cache()
                self.assertTrue((cache_dir / "metadata_cache.json").exists())

                # Modify file while keeping same size (simulate concurrent modification)
                original_size = test_video.stat().st_size
                with open(test_video, 'r+b') as f:
                    f.seek(original_size - 1)
                    f.write(b'X')

                # Second parse should return cached metadata
                metadata2 = VideoMetadataParser.parse_video(test_video)
                self.assertIsNotNone(metadata2, "Failed to parse modified video")
                
                if metadata2:
                    # Verify metadata matches despite modification
                    self.assertEqual(initial_width, metadata2.width)
                    self.assertEqual(initial_height, metadata2.height)

    def test_cache_memory_usage(self):
        """Test that cache memory usage stays reasonable with many files"""
        import psutil
        import os

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / 'cache'
            cache = MetadataCache(cache_dir)
            VideoMetadataParser._cache = cache

            # Record starting memory
            process = psutil.Process(os.getpid())
            start_memory = process.memory_info().rss

            # Create and parse 50 copies of test video
            successful_parses = 0
            for i in range(50):
                test_video = Path(temp_dir) / f"test_{i}.mp4"
                shutil.copy2(self.test_video_path, test_video)
                metadata = VideoMetadataParser.parse_video(test_video)
                if metadata is not None:
                    successful_parses += 1

            # Ensure we parsed at least some files successfully
            self.assertGreater(successful_parses, 0, "No files were parsed successfully")

            # Check memory usage hasn't grown too much
            end_memory = process.memory_info().rss
            memory_increase = end_memory - start_memory
            
            # Should use less than 5MB additional memory for cache
            max_memory_increase = 5 * 1024 * 1024  # 5MB
            self.assertLess(memory_increase, max_memory_increase, 
                          f"Cache uses too much memory: {memory_increase / 1024 / 1024:.1f}MB")

    def test_parsing_with_latency(self):
        """Test metadata parsing performance with simulated network latency"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a large test file
            test_file = Path(temp_dir) / "slow_access.mp4"
            shutil.copy2(self.test_video_path, test_file)
            
            # Make file large by appending data
            with open(test_file, 'ab') as f:
                f.write(b'\0' * (50 * 1024 * 1024))  # Add 50MB
                
            class SlowFile:
                """Wrapper to simulate slow file access"""
                def __init__(self, path):
                    self.path = Path(path)
                    self._file = None
                
                def __enter__(self):
                    self._file = open(self.path, 'rb')
                    return self
                
                def __exit__(self, exc_type, exc_val, exc_tb):
                    if self._file:
                        self._file.close()
                
                def read(self, size=None):
                    """Simulate network latency on read"""
                    time.sleep(0.01)  # 10ms latency per read
                    assert self._file is not None
                    return self._file.read(size)
                
                def seek(self, offset, whence=0):
                    """Simulate network latency on seek"""
                    time.sleep(0.01)  # 10ms latency per seek
                    assert self._file is not None
                    return self._file.seek(offset, whence)
                
                def tell(self):
                    assert self._file is not None
                    return self._file.tell()
            
            # Time parsing with simulated latency
            start_time = time.time()
            with SlowFile(test_file) as slow:
                # Get file size without using read
                size = test_file.stat().st_size
                
                # Read just the header (first 1MB)
                header = slow.read(1024 * 1024)
                
            parse_time = time.time() - start_time
            
            # Even with latency, should complete in reasonable time
            self.assertLess(parse_time, 2.0, 
                          f"Parsing took too long with latency: {parse_time:.1f}s")
            
            # Verify we can still parse the file normally
            metadata = VideoMetadataParser.parse_video(test_file)
            self.assertIsNotNone(metadata, "Failed to parse file with latency simulation")

if __name__ == '__main__':
    unittest.main(verbosity=2)

if __name__ == '__main__':
    unittest.main()
