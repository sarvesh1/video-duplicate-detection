#!/usr/bin/env python3

import sys
from pathlib import Path
sys.path.append('src')
from video_metadata import VideoMetadataParser

def main():
    parser = VideoMetadataParser()
    
    # Check both files
    files = ['test_data/original/IMG_1122.MP4', 'test_data/resized/IMG_1122.MP4']
    for file_path in files:
        if Path(file_path).exists():
            print(f'\n=== {file_path} ===')
            metadata = parser.parse_video(Path(file_path))
            if metadata:
                print(f'Duration: {metadata.duration}s')
                print(f'Resolution: {metadata.width}x{metadata.height}')
                print(f'File size: {metadata.file_size} bytes')
                print(f'Creation time: {metadata.creation_time}')
                print(f'Bitrate: {metadata.bitrate}')
            else:
                print('Failed to extract metadata')
        else:
            print(f'File not found: {file_path}')

if __name__ == '__main__':
    main()