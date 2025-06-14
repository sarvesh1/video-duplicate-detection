"""
Duplicate Detection Engine Module.

This module provides functionality to identify and validate duplicate video files
based on their metadata and characteristics.
"""
from typing import Dict, List, Set, Tuple, Optional, NamedTuple, Any
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import defaultdict
import math

from src.video_metadata import VideoMetadata
from src.data_structures import FileInfo, MetadataStore

# Constants
ASPECT_RATIO_TOLERANCE = 0.01  # 1% tolerance for aspect ratio differences

class EdgeCaseType(Enum):
    """Types of edge cases that can be detected"""
    DURATION_MISMATCH = "duration_mismatch"
    ASPECT_RATIO = "aspect_ratio"
    RESOLUTION = "resolution"
    QUALITY = "quality"
    TIMESTAMP = "timestamp"
    METADATA = "metadata"

class Severity(Enum):
    """Severity levels for issues"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class Action(Enum):
    """Possible actions for duplicate files"""
    SAFE_DELETE = "safe_delete"
    MANUAL_REVIEW = "manual_review"
    PRESERVE = "preserve"
    VERIFY = "verify"

@dataclass(frozen=True)
class ResolutionVariant:
    """Represents a video file at a specific resolution"""
    path: Path
    width: int
    height: int
    created_at: datetime
    confidence_score: float

@dataclass
class VideoRelationship:
    """Represents relationships between original and resized video variants"""
    original: ResolutionVariant
    variants: List[ResolutionVariant]
    filename: str
    total_confidence: float
    validation_results: Dict[Path, 'ValidationResult']
    rotated_variants: Set[Path] = field(default_factory=set)  # Set of paths to rotated variants

    @property
    def all_paths(self) -> List[Path]:
        """Returns all paths in the relationship"""
        return [self.original.path] + [v.path for v in self.variants]

    @property
    def resolution_chain(self) -> List[Tuple[int, int]]:
        """Returns all resolutions in descending order"""
        all_variants = [self.original] + self.variants
        return sorted(
            [(v.width, v.height) for v in all_variants],
            key=lambda x: x[0] * x[1],
            reverse=True
        )

@dataclass
class ValidationResult:
    """Results of duplicate validation checks"""
    aspect_ratio_match: bool
    timestamp_valid: bool
    size_correlation_valid: bool
    bitrate_valid: bool
    overall_score: float
    reason: str
    is_rotated: bool = False  # Add rotation flag

@dataclass
class DuplicateGroup:
    """Represents a group of potentially duplicate video files"""
    filename: str  # Base filename without directory
    original: Optional[Path]  # Path to the suspected original file
    duplicates: List[Path]  # Paths to suspected duplicates
    confidence_score: float  # 0-1 score indicating confidence in duplicate relationship
    validation_results: Dict[Path, ValidationResult] = field(default_factory=dict)

    @property
    def all_files(self) -> List[Path]:
        """Returns all files in the group including the original"""
        return [self.original] + self.duplicates if self.original else self.duplicates

@dataclass
class EdgeCaseAnalysis:
    """Analysis of potential edge cases and problematic files"""
    file_path: Path
    issue_type: EdgeCaseType
    severity: Severity
    details: str
    recommendation: str

@dataclass
class ActionRecommendation:
    """Recommended action for a duplicate file"""
    file_path: Path
    action: Action
    reason: str
    confidence: float  # 0-1 score

@dataclass
class DuplicateAnalysis:
    """Analysis report for duplicate video files"""
    original_path: Path
    original_resolution: str
    duplicates: List[Dict[str, Any]]  # List of {path, resolution, size, confidence, issues}
    total_size: int
    potential_savings: int
    confidence_score: float
    resolution_chain_valid: bool
    issues: List[str]

class ReportGenerator:
    """Generates detailed analysis reports for duplicate video files"""

    def __init__(self, relationships: List[VideoRelationship], base_dir: Path, metadata_store: MetadataStore):
        """Initialize the report generator.

        Args:
            relationships: List of VideoRelationship objects to analyze
            base_dir: Base directory for relative path calculations
            metadata_store: MetadataStore containing file metadata
        """
        self.relationships = relationships
        self.base_dir = base_dir
        self.metadata_store = metadata_store

    def _get_relative_path(self, path: Path) -> str:
        """Convert path relative to base directory for cleaner output.
        
        If the path is not under the base directory, returns the absolute path.
        """
        try:
            return str(path.relative_to(self.base_dir))
        except ValueError:
            # If path is not under base_dir, return the absolute path
            return str(path)

    def analyze_relationships(self) -> List[DuplicateAnalysis]:
        """Analyze relationships and generate detailed reports."""
        analyses = []

        for rel in self.relationships:
            # Get original file info
            original = rel.original
            orig_info = self.metadata_store.files[str(original.path)]
            original_resolution = f"{original.width}x{original.height}"

            # Analyze variants
            duplicates = []
            total_size = 0
            issues = []

            # Add original file size to total if available
            total_size += orig_info.file_size if orig_info else 0

            # Validate resolution chain
            chain_analysis = self._validate_resolution_chain(rel)
            resolution_chain_valid = chain_analysis['is_consistent']

            # Add chain validation issues
            if not chain_analysis['is_consistent']:
                issues.append("Inconsistent resolution scaling")
            if chain_analysis['missing_common_ratios']:
                issues.append(
                    f"Missing common resolutions: {', '.join(str(r) for r in chain_analysis['missing_common_ratios'])}"
                )

            # Process each variant
            for variant in rel.variants:
                variant_issues = []
                meta_info = self.metadata_store.files[str(variant.path)]
                resolution = f"{variant.width}x{variant.height}"
                variant_size = meta_info.file_size if meta_info else 0

                # Check for rotation
                if variant.path in rel.rotated_variants:
                    variant_issues.append("Rotated variant")

                duplicates.append({
                    'path': variant.path,
                    'resolution': resolution,
                    'size': variant_size,
                    'confidence': variant.confidence_score,
                    'issues': variant_issues
                })

                total_size += variant_size

            # Calculate potential space savings (size of all duplicates)
            potential_savings = total_size - (orig_info.file_size if orig_info else 0)

            analyses.append(DuplicateAnalysis(
                original_path=original.path,
                original_resolution=original_resolution,
                duplicates=duplicates,
                total_size=total_size,
                potential_savings=potential_savings,
                confidence_score=rel.total_confidence,
                resolution_chain_valid=resolution_chain_valid,
                issues=issues
            ))

        return sorted(analyses, key=lambda x: x.confidence_score, reverse=True)

    def generate_text_report(self) -> str:
        """Generate a human-readable text report of the analysis.

        Returns:
            Formatted text string containing the analysis report
        """
        analyses = self.analyze_relationships()

        # Calculate overall statistics
        total_groups = len(analyses)
        total_duplicates = sum(len(a.duplicates) for a in analyses)
        total_size = sum(a.total_size for a in analyses)
        total_savings = sum(a.potential_savings for a in analyses)

        # Build report
        lines = []

        # Overall summary
        lines.extend([
            "=== Video Duplicate Analysis Report ===\n",
            "Overall Statistics:",
            f"- Total duplicate groups: {total_groups}",
            f"- Total duplicate files: {total_duplicates}",
            f"- Total size: {self._humanize_size(total_size)}",
            f"- Potential space savings: {self._humanize_size(total_savings)}",
            "",
            "Duplicate Groups (sorted by confidence):",
            ""
        ])

        # Details for each duplicate group
        if analyses:
            lines.extend([
                "Format: Group # | Original | Original Resolution | Duplicates | Duplicate Resolution | Duplicate Size | Issues",
                "-" * 120
            ])
            
            for i, analysis in enumerate(analyses, 1):
                # Format original file info
                orig_path = self._get_relative_path(analysis.original_path)
                
                # Format duplicate entries
                dup_entries = []
                for dup in analysis.duplicates:
                    dup_path = self._get_relative_path(dup['path'])
                    dup_info = f"{dup_path} | {dup['resolution']} | {self._humanize_size(dup['size'])}"
                    if dup['issues']:
                        dup_info += f" ({', '.join(dup['issues'])})"
                    dup_entries.append(dup_info)
                
                # Build the single-line entry
                line = f"{i} | {orig_path} | {analysis.original_resolution} | {self._humanize_size(self.metadata_store.files[str(analysis.original_path)].file_size)} | {' | '.join(dup_entries)}"
                
                # Add group issues if any
                if analysis.issues:
                    line += f" | Issues: {', '.join(analysis.issues)}"
                
                lines.extend([
                    line,
                    "-" * 120
                ])
        else:
            lines.append("No duplicates found.")

        return "\n".join(lines)

    def _validate_resolution_chain(self, relationship: VideoRelationship) -> Dict[str, Any]:
        """Analyze resolution chain for consistency and missing common ratios.

        Args:
            relationship: The VideoRelationship to analyze

        Returns:
            Dictionary containing analysis results
        """
        resolutions = []
        resolutions.append((relationship.original.width, relationship.original.height))

        for variant in relationship.variants:
            resolutions.append((variant.width, variant.height))

        # Sort resolutions by total pixels (descending)
        resolutions.sort(key=lambda x: x[0] * x[1], reverse=True)

        # Calculate scale ratios between all resolution pairs
        scale_ratios = set()
        is_consistent = True

        # Check all possible resolution pairs
        for i in range(len(resolutions)):
            for j in range(i + 1, len(resolutions)):
                curr_res = resolutions[i]
                next_res = resolutions[j]

                # Calculate width and height ratios
                width_ratio = next_res[0] / curr_res[0]
                height_ratio = next_res[1] / curr_res[1]

                print(f"Raw ratios - width: {width_ratio:.4f}, height: {height_ratio:.4f}")

                # Check for consistent scaling and reasonable ratios
                if not (0.1 <= width_ratio <= 1.0 and abs(width_ratio - height_ratio) < 0.01):
                    is_consistent = False
                else:
                    # Use width ratio since common video resolutions are based on width
                    ratio = round(width_ratio, 2)
                    scale_ratios.add(ratio)
                    print(f"Added scale ratio {ratio} for {curr_res} -> {next_res}")

        # Common scale ratios (e.g., 1080p->720p->480p)
        common_ratios = {0.67, 0.44}  # Approximations of standard scaling
        missing_ratios = common_ratios - scale_ratios

        return {
            'is_consistent': is_consistent,
            'scale_ratios': sorted(scale_ratios),
            'missing_common_ratios': sorted(missing_ratios),
            'resolution_count': len(resolutions)
        }

    @staticmethod
    def _humanize_size(size_in_bytes: float) -> str:
        """Convert bytes to human readable string."""
        size = float(size_in_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
