# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

### Running the Application
```bash
python src/main.py test_data/original/
python src/main.py ~/path/to/videos/
```

### Testing Commands
```bash
# Run all tests (may timeout due to performance tests)
python3 -m unittest discover src -v -p "test_*.py"

# Run individual test files (recommended for development)
python3 -m unittest src.test_duplicate_detector -v  # Core logic tests
python3 -m unittest src.test_report -v             # Report generation tests
python3 -m unittest src.test_edge_cases -v         # Edge case tests
python3 -m unittest src.test_video_metadata -v     # Video metadata tests (slow)

# Fast test suite (skip slow performance tests)
python3 -m unittest src.test_duplicate_detector src.test_report src.test_edge_cases -v
```

### Dependencies
```bash
pip install -r requirements.txt
```

## Architecture Overview

### Core Components

**Main Processing Pipeline (`src/main.py`)**
- Entry point that orchestrates the entire duplicate detection process
- Scans directories → extracts metadata → detects duplicates → generates reports
- Handles multiple input directories and error handling

**Directory Scanner (`src/scanner.py`)**
- Recursively scans directories for MP4 files
- Extracts file system metadata (size, timestamps)
- Integrates with VideoMetadataParser for technical metadata

**Duplicate Detection Engine (`src/duplicate_detector.py`)**
- Core logic for identifying duplicate videos based on metadata analysis
- Uses multi-factor scoring: aspect ratio (40%), bitrate (30%), file size (20%), timestamps (10%)
- Handles edge cases like rotation detection and resolution scaling chains
- Confidence scoring ranges: 1.0 (perfect), ≥0.8 (high confidence), 0.5-0.8 (medium), <0.5 (low)

**Data Storage (`src/data_structures.py`)**
- `MetadataStore`: Central storage with multiple indices (filename, directory, size)
- `FileInfo`: Represents individual file metadata
- Efficient lookup structures for duplicate candidate identification

**Video Metadata (`src/video_metadata.py`)**
- Uses ffmpeg-python to extract technical video properties
- Handles duration, resolution, codecs, bitrate, aspect ratio
- Includes caching and error handling for corrupted files

**Report Generation (`src/report.py`)**
- Generates detailed text reports of duplicate relationships
- Tracks confidence scores, validation results, and recommended actions
- Handles resolution variants and rotation detection

### Key Algorithms

**Duplicate Detection Strategy**
1. Duration matching (required within 1 second)
2. Resolution analysis (standard scaling patterns, rotation detection)
3. Technical metadata correlation (codecs, bitrate, file size)
4. Timestamp proximity analysis

**Confidence Scoring**
- Weighted scoring system with rotation bonuses and metadata penalties
- Duration mismatches automatically disqualify candidates
- Handles missing metadata gracefully with reduced confidence

### Test Structure
- Unit tests cover all major components with real video file fixtures
- Performance tests create large temporary files (up to 100MB)
- Edge case testing for corrupted files, missing metadata, and unusual formats
- Memory usage validation with cache behavior testing