"""
Main entry point for the Video Duplicate Detection tool.
"""

import sys
from pathlib import Path

# Add the parent directory of `src` to the Python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from scanner import DirectoryScanner
from data_structures import MetadataStore, FileInfo
from report import (
    ReportGenerator, VideoRelationship, ResolutionVariant,
    ASPECT_RATIO_TOLERANCE
)
from duplicate_detector import DuplicateDetector

def process_duplicate_groups(duplicate_groups, file_info_map):
    """Process duplicate groups into video relationships with rotation detection.

    Args:
        duplicate_groups: List of DuplicateGroup objects to process
        file_info_map: Dictionary mapping file paths to FileInfo objects

    Returns:
        List of VideoRelationship objects with rotation information
    """
    relationships = []
    for group in duplicate_groups:
        # Skip if original is missing or has no metadata
        if not group.original:
            continue
            
        original_info = file_info_map.get(group.original)
        if not original_info or not original_info.video_metadata:
            continue

        original_metadata = original_info.video_metadata
        # Create original variant (never rotated)
        original_variant = ResolutionVariant(
            path=group.original,
            width=original_metadata.width,
            height=original_metadata.height,
            created_at=original_info.created_at,
            confidence_score=group.confidence_score
        )

        variants = []
        for variant_path in group.duplicates:
            variant_info = file_info_map.get(variant_path)
            if not variant_info or not variant_info.video_metadata:
                continue

            variant_metadata = variant_info.video_metadata
            aspect_ratio_original = original_metadata.width / original_metadata.height
            aspect_ratio_variant = variant_metadata.width / variant_metadata.height

            # Detect rotation
            rotation_flag = abs(aspect_ratio_original - (1 / aspect_ratio_variant)) < DuplicateDetector.ASPECT_RATIO_TOLERANCE

            validation_result = group.validation_results.get(variant_path)
            overall_score = validation_result.overall_score if validation_result else 0.0
            
            # Add variant
            variants.append(ResolutionVariant(
                path=variant_path,
                width=variant_metadata.width,
                height=variant_metadata.height,
                created_at=variant_info.created_at,
                confidence_score=overall_score
            ))

        if variants:  # Only add relationships with valid variants
            # Track rotated variants
            rotated = {v.path for v in variants if abs(
                original_metadata.width / original_metadata.height - 
                file_info_map[v.path].video_metadata.height / file_info_map[v.path].video_metadata.width
            ) < ASPECT_RATIO_TOLERANCE}

            relationships.append(VideoRelationship(
                original=original_variant,
                variants=variants,
                filename=group.filename,
                total_confidence=group.confidence_score,
                validation_results=group.validation_results,
                rotated_variants=rotated
            ))

    return relationships

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

    # Process and validate duplicates
    relationships = process_duplicate_groups(duplicate_groups, file_info_map)

    # Generate and print report
    if relationships:
        # Use the absolute path to the workspace root
        workspace_root = Path(__file__).resolve().parent.parent
        report_generator = ReportGenerator(
            relationships=relationships,
            base_dir=workspace_root,
            metadata_store=metadata_store
        )
        print("\n" + report_generator.generate_text_report())
    else:
        print("\nNo duplicates found in the specified directories.")

if __name__ == "__main__":
    main()
