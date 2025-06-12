"""
Main entry point for the Video Duplicate Detection tool.
"""

import sys
from pathlib import Path

# Add the parent directory of `src` to the Python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from scanner import DirectoryScanner
from data_structures import MetadataStore, FileInfo
from report import ReportGenerator
from duplicate_detector import DuplicateDetector, VideoRelationship, ResolutionVariant

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
                metadata_store.add_file(FileInfo(
                    path=Path(file_metadata.file_path),
                    file_size=file_metadata.file_size,
                    created_at=file_metadata.creation_time,
                    modified_at=file_metadata.modification_time,
                    video_metadata=file_metadata.video_metadata
                ))
        except Exception as e:
            print(f"Error processing directory {directory}: {str(e)}")

    # Convert MetadataStore.files keys to Path
    file_info_map = {Path(k): v for k, v in metadata_store.files.items()}

    # Initialize DuplicateDetector
    duplicate_detector = DuplicateDetector(file_info_map)

    # Detect duplicates and build relationships
    duplicate_groups = duplicate_detector.detect_and_report_duplicates()

    # Map DuplicateGroup objects to VideoRelationship objects
    relationships = []
    for group in duplicate_groups:
        if group.original and file_info_map[group.original].video_metadata:
            original_metadata = file_info_map[group.original].video_metadata
            original_variant = ResolutionVariant(
                path=group.original,
                width=original_metadata.width,
                height=original_metadata.height,
                created_at=file_info_map[group.original].created_at,
                confidence_score=group.confidence_score
            )
        else:
            continue  # Skip group if original metadata is missing

        variants = []
        for variant in group.duplicates:
            variant_metadata = file_info_map[variant].video_metadata
            if variant_metadata:
                validation_result = group.validation_results.get(variant)
                overall_score = validation_result.overall_score if validation_result else 0.0
                variants.append(ResolutionVariant(
                    path=variant,
                    width=variant_metadata.width,
                    height=variant_metadata.height,
                    created_at=file_info_map[variant].created_at,
                    confidence_score=overall_score
                ))

        if variants:  # Only add relationships with valid variants
            relationships.append(VideoRelationship(
                original=original_variant,
                variants=variants,
                filename=group.filename,
                total_confidence=group.confidence_score,
                validation_results=group.validation_results
            ))

    # Generate and print report
    if relationships:
        report_generator = ReportGenerator(
            relationships=relationships,
            base_dir=Path("./test_data"),
            metadata_store=metadata_store
        )
        print("\n" + report_generator.generate_text_report())
    else:
        print("\nNo duplicates found in the specified directories.")

if __name__ == "__main__":
    main()
