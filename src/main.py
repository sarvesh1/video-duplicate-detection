"""
Main entry point for the Video Duplicate Detection tool.
"""

import sys
from pathlib import Path
from scanner import DirectoryScanner
from data_structures import MetadataStore
from report import InventoryReport

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python main.py <directory1> [directory2 ...]")
        sys.exit(1)
    
    # Initialize components
    scanner = DirectoryScanner()
    metadata_store = MetadataStore()
    
    # Process each input directory
    for directory in sys.argv[1:]:
        print(f"\nScanning directory: {directory}")
        try:
            # Scan directory and store metadata
            files = scanner.scan_directory(directory)
            for file_metadata in files:
                metadata_store.add_file(file_metadata)
        except Exception as e:
            print(f"Error processing directory {directory}: {str(e)}")
    
    # Generate and print report
    if metadata_store.files:
        report = InventoryReport(metadata_store)
        print("\n" + report.generate_summary())
    else:
        print("\nNo MP4 files found in the specified directories.")

if __name__ == "__main__":
    main()
