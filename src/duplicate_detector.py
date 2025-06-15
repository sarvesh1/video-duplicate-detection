"""
Duplicate Detection Engine Module.

This module provides functionality to identify and validate duplicate video files
based on their metadata and characteristics.
"""

from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, NamedTuple, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from src.video_metadata import VideoMetadata
from src.data_structures import FileInfo

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

class ResolutionVariant(NamedTuple):
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
    confidence: float  # 0-1

class DuplicateDetector:
    """Identifies and validates duplicate video files"""
    
    DURATION_TOLERANCE = 1.0  # Maximum duration difference in seconds
    MIN_CONFIDENCE_SCORE = 0.7  # Minimum confidence score to consider as duplicate
    ASPECT_RATIO_TOLERANCE = 0.01  # 1% tolerance for aspect ratio differences
    MAX_TIMESTAMP_DIFF_DAYS = 30  # Maximum reasonable time between original and duplicate
    EXPECTED_SIZE_RATIO_TOLERANCE = 0.3  # 30% tolerance for size ratio vs resolution ratio
    
    def __init__(self, file_info_map: Dict[Path, FileInfo]):
        """
        Initialize the detector with file information.
        
        Args:
            file_info_map: Dictionary mapping file paths to FileInfo objects
        """
        self.file_info_map = file_info_map
        self._filename_groups: Dict[str, Set[Path]] = {}
        self._build_filename_groups()
    
    def _build_filename_groups(self) -> None:
        """Group files by their base filename for initial candidate identification"""
        for path in self.file_info_map:
            filename = path.name
            if filename not in self._filename_groups:
                self._filename_groups[filename] = set()
            self._filename_groups[filename].add(path)
    
    def find_duplicate_candidates(self) -> List[DuplicateGroup]:
        """
        Identify potential duplicate files based on filename and duration.
        
        Returns:
            List of DuplicateGroup objects for files that might be duplicates
        """
        duplicate_groups: List[DuplicateGroup] = []
        
        # Process each group of files with the same filename
        for filename, paths in self._filename_groups.items():
            if len(paths) < 2:
                continue  # Skip files without duplicates
                
            # Get metadata for all files in the group
            files_metadata: List[Tuple[Path, VideoMetadata]] = []
            for path in paths:
                info = self.file_info_map[path]
                if info.video_metadata:
                    files_metadata.append((path, info.video_metadata))
            
            if len(files_metadata) < 2:
                continue  # Skip if we don't have metadata for at least 2 files
            
            # Compare durations within the group
            duration_matches: List[Tuple[Path, VideoMetadata]] = []
            
            # Try each duration as the base to find the largest matching group
            for _, base_metadata in files_metadata:
                current_matches = []
                for path, metadata in files_metadata:
                    if abs(metadata.duration - base_metadata.duration) <= self.DURATION_TOLERANCE:
                        current_matches.append((path, metadata))
                
                # Keep this group if it's larger than what we've found so far
                if len(current_matches) >= 2 and len(current_matches) > len(duration_matches):
                    duration_matches = current_matches
            
            if duration_matches:
                # Find the likely original (highest resolution, earliest timestamp)
                original_path, score = self._identify_original(duration_matches)
                duplicates = [p for p, _ in duration_matches if p != original_path]
                
                group = DuplicateGroup(
                    filename=filename,
                    original=original_path,
                    duplicates=duplicates,
                    confidence_score=score
                )
                duplicate_groups.append(group)
        
        return duplicate_groups
    
    def _identify_original(
        self, candidates: List[Tuple[Path, VideoMetadata]]
    ) -> Tuple[Optional[Path], float]:
        """
        Identify the likely original file from a group of candidates.
        
        Args:
            candidates: List of (path, metadata) tuples for candidate files
            
        Returns:
            Tuple of (original_path, confidence_score), where original_path
            may be None if no suitable original is found
        """
        max_resolution = 0
        earliest_time = float('inf')
        original_path = None
        total_score = 0.0
        
        # Find highest resolution and earliest video metadata timestamp
        for path, metadata in candidates:
            resolution = metadata.width * metadata.height
            
            if resolution > max_resolution:
                max_resolution = resolution
            
            # Only use video metadata creation time, ignore filesystem dates
            if metadata.creation_time:
                timestamp = metadata.creation_time.timestamp()
                if timestamp < earliest_time:
                    earliest_time = timestamp
        
        # Score each candidate
        for path, metadata in candidates:
            file_info = self.file_info_map[path]
            resolution = metadata.width * metadata.height
            
            # Calculate score components
            resolution_score = resolution / max_resolution  # 0-1 score for resolution
            
            # Only use video metadata creation time for scoring
            time_score = 0.5  # Default neutral score if no video creation time
            if metadata.creation_time and earliest_time != float('inf'):
                timestamp = metadata.creation_time.timestamp()
                time_score = 1 - ((timestamp - earliest_time) / (86400 * 30))  # Time diff in 30 days
                time_score = max(0, min(1, time_score))  # Clamp between 0-1
            
            # Calculate file size score with safe access
            file_size = file_info.file_size if file_info else 0
            max_size = max((self.file_info_map[p].file_size for p, _ in candidates), default=1)
            size_score = file_size / max_size if max_size > 0 else 0
            
            # Weighted score (prioritize file size over resolution, reduce time weight since it's less reliable)
            score = (size_score * 0.6) + (resolution_score * 0.3) + (time_score * 0.1)
            
            if score > total_score:
                total_score = score
                original_path = path
        
        return original_path, total_score

    def validate_duplicates(self, group: DuplicateGroup) -> DuplicateGroup:
        """
        Validate suspected duplicates using multiple criteria.
        
        Args:
            group: DuplicateGroup object containing suspected duplicates
            
        Returns:
            Updated DuplicateGroup with validation results
        """
        if not group.original:
            return group
            
        original_info = self.file_info_map[group.original]
        original_meta = original_info.video_metadata
        
        if not original_meta:
            return group
        
        validation_results = {}
        
        for duplicate_path in group.duplicates:
            duplicate_info = self.file_info_map[duplicate_path]
            duplicate_meta = duplicate_info.video_metadata
            
            if not duplicate_meta:
                continue
                
            # Validate aspect ratio
            original_ratio = original_meta.width / original_meta.height
            duplicate_ratio = duplicate_meta.width / duplicate_meta.height
            ratio_diff = abs(original_ratio - duplicate_ratio) / original_ratio
            aspect_ratio_match = ratio_diff <= self.ASPECT_RATIO_TOLERANCE
            
            # Validate timestamps using only video metadata creation time
            timestamp_valid = True
            time_diff_seconds = 0
            
            # Only use video metadata creation time - no filesystem date fallback
            if (original_meta.creation_time and duplicate_meta.creation_time):
                time_diff_seconds = abs(
                    (duplicate_meta.creation_time - original_meta.creation_time).total_seconds()
                )
                # For files with identical names and durations, use very strict timestamp validation
                # If video creation times differ by more than 60 seconds, they're different recordings
                strict_timestamp_threshold = 60  # seconds
                timestamp_valid = time_diff_seconds <= strict_timestamp_threshold
            else:
                # If no video metadata creation time available, skip timestamp validation
                # This prevents false matches based on filesystem dates
                timestamp_valid = True  # Neutral - don't penalize missing metadata
            
            # Validate file size correlation with resolution
            original_pixels = original_meta.width * original_meta.height
            duplicate_pixels = duplicate_meta.width * duplicate_meta.height
            resolution_ratio = duplicate_pixels / original_pixels
            
            # Check size correlation if both files have size information
            size_correlation_valid = True
            if original_meta.file_size > 0 and duplicate_meta.file_size > 0:
                expected_size = original_meta.file_size * resolution_ratio
                actual_size = duplicate_meta.file_size
                size_diff_ratio = abs(actual_size - expected_size) / expected_size
                size_correlation_valid = size_diff_ratio <= self.EXPECTED_SIZE_RATIO_TOLERANCE
            
            # Check bitrate correlation if both files have bitrate information
            bitrate_valid = True
            if original_meta.bitrate > 0 and duplicate_meta.bitrate > 0:
                expected_bitrate = original_meta.bitrate * resolution_ratio
                actual_bitrate = duplicate_meta.bitrate
                bitrate_diff_ratio = abs(actual_bitrate - expected_bitrate) / expected_bitrate
                bitrate_valid = bitrate_diff_ratio <= self.EXPECTED_SIZE_RATIO_TOLERANCE
            
            # Calculate overall validation score
            # For same-name, same-duration files, timestamp validation is critical
            # If timestamp validation fails due to large time differences, this should be disqualifying
            if not timestamp_valid and time_diff_seconds > 86400:  # More than 1 day difference
                # Large timestamp differences are disqualifying for files with identical names/durations
                score = 0.0
            else:
                weights = {
                    'aspect_ratio': 0.3,
                    'timestamp': 0.4,  # Increased weight for timestamp validation
                    'size': 0.15,
                    'bitrate': 0.15
                }
                
                score = (
                    (aspect_ratio_match * weights['aspect_ratio']) +
                    (timestamp_valid * weights['timestamp']) +
                    (size_correlation_valid * weights['size']) +
                    (bitrate_valid * weights['bitrate'])
                )
            
            # Generate reason string
            reasons = []
            if not aspect_ratio_match:
                reasons.append("aspect ratio mismatch")
            if not timestamp_valid:
                if time_diff_seconds > 86400:  # More than 1 day
                    time_diff_days = time_diff_seconds / 86400
                    reasons.append(f"disqualifying timestamp difference ({time_diff_days:.1f} days apart)")
                else:
                    reasons.append("suspicious timestamp")
            if not size_correlation_valid:
                reasons.append("unexpected file size")
            if not bitrate_valid:
                reasons.append("unexpected bitrate")
                
            reason = "; ".join(reasons) if reasons else "all checks passed"
            
            validation_results[duplicate_path] = ValidationResult(
                aspect_ratio_match=aspect_ratio_match,
                timestamp_valid=timestamp_valid,
                size_correlation_valid=size_correlation_valid,
                bitrate_valid=bitrate_valid,
                overall_score=score,
                reason=reason
            )
        
        group.validation_results = validation_results
        return group

    def build_relationships(self) -> List[VideoRelationship]:
        """
        Build relationships between original videos and their variants.
        
        Returns:
            List of VideoRelationship objects mapping originals to duplicates
        """
        # First, find all duplicate groups
        duplicate_groups = self.find_duplicate_candidates()
        relationships: List[VideoRelationship] = []

        for group in duplicate_groups:
            # Validate the group first
            validated_group = self.validate_duplicates(group)
            
            if not validated_group.original:
                continue

            # Get metadata for the original
            original_info = self.file_info_map[validated_group.original]
            original_meta = original_info.video_metadata
            
            if not original_meta:
                continue

            # Create original variant
            original_variant = ResolutionVariant(
                path=validated_group.original,
                width=original_meta.width,
                height=original_meta.height,
                created_at=original_info.created_at,
                confidence_score=validated_group.confidence_score
            )

            # Process all duplicates and create variants
            variants: List[ResolutionVariant] = []
            total_confidence = validated_group.confidence_score

            for dup_path in validated_group.duplicates:
                dup_info = self.file_info_map[dup_path]
                dup_meta = dup_info.video_metadata
                
                if not dup_meta:
                    continue

                # Get validation results if available
                validation_score = 1.0
                if (validated_group.validation_results and 
                    dup_path in validated_group.validation_results):
                    validation_score = validated_group.validation_results[dup_path].overall_score

                # Only include variants that pass minimum confidence threshold
                # This prevents false matches with disqualifying timestamp differences
                if validation_score >= 0.1:  # Very low threshold to allow some flexibility, but exclude 0.0 scores
                    variant = ResolutionVariant(
                        path=dup_path,
                        width=dup_meta.width,
                        height=dup_meta.height,
                        created_at=dup_info.created_at,
                        confidence_score=validation_score
                    )
                    variants.append(variant)
                    total_confidence *= validation_score

            # Create the relationship if we have variants
            if variants:
                relationship = VideoRelationship(
                    original=original_variant,
                    variants=sorted(
                        variants,
                        key=lambda v: v.width * v.height,
                        reverse=True
                    ),
                    filename=group.filename,
                    total_confidence=total_confidence,
                    validation_results=validated_group.validation_results or {}
                )
                relationships.append(relationship)

        return sorted(relationships, key=lambda r: r.total_confidence, reverse=True)

    def analyze_resolution_chain(self, relationship: VideoRelationship) -> Dict[str, Any]:
        """
        Analyze the resolution chain in a relationship for completeness and consistency.
        
        Args:
            relationship: VideoRelationship object to analyze
            
        Returns:
            Dictionary containing analysis results
        """
        resolutions = relationship.resolution_chain
        
        # Check if resolutions form a logical progression
        is_consistent = True
        expected_ratios = set()
        
        for i in range(len(resolutions) - 1):
            curr_res = resolutions[i]
            next_res = resolutions[i + 1]
            
            # Calculate scale ratio
            width_ratio = next_res[0] / curr_res[0]
            height_ratio = next_res[1] / curr_res[1]
            
            # Ratios should be consistent and make sense (e.g., 0.5, 0.75)
            if not (0.1 <= width_ratio <= 1.0 and abs(width_ratio - height_ratio) < 0.01):
                is_consistent = False
            
            expected_ratios.add(round(width_ratio, 2))
        
        # Common scale ratios we might expect (e.g., 1080p->720p, 1080p->480p)
        common_ratios = {0.5, 0.75, 0.66}  
        missing_common = common_ratios - expected_ratios
        
        return {
            'resolutions': resolutions,
            'is_consistent': is_consistent,
            'scale_ratios': sorted(expected_ratios),
            'missing_common_ratios': sorted(missing_common),
            'resolution_count': len(resolutions)
        }

    def map_relationships_to_groups(self, relationships: List[VideoRelationship]) -> List[DuplicateGroup]:
        """
        Map video relationships to duplicate groups for consolidated reporting.
        
        Args:
            relationships: List of VideoRelationship objects
            
        Returns:
            List of DuplicateGroup objects representing the mapped relationships
        """
        group_map: Dict[Path, DuplicateGroup] = {}
        
        for relationship in relationships:
            # Create or update the group for the original video
            if relationship.original.path not in group_map:
                group_map[relationship.original.path] = DuplicateGroup(
                    filename=relationship.filename,
                    original=relationship.original.path,
                    duplicates=[],
                    confidence_score=relationship.total_confidence
                )
            
            # Add all variant paths to the group's duplicates
            group = group_map[relationship.original.path]
            for variant in relationship.variants:
                if variant.path not in group.duplicates:
                    group.duplicates.append(variant.path)
            
            # Update confidence score if this relationship has higher confidence
            group.confidence_score = max(
                group.confidence_score,
                relationship.total_confidence
            )
            
            # Copy validation results if available
            if relationship.validation_results:
                for path, result in relationship.validation_results.items():
                    group.validation_results[path] = result
        
        return list(group_map.values())

    def detect_and_report_duplicates(self) -> List[DuplicateGroup]:
        """
        Detect duplicates and generate a consolidated report of duplicate groups.
        
        Returns:
            List of DuplicateGroup objects representing detected duplicates
        """
        # Step 1: Find initial duplicate candidates
        self.find_duplicate_candidates()
        
        # Step 2: Validate and build relationships for all candidates
        all_relationships = self.build_relationships()
        
        # Step 3: Map relationships to duplicate groups
        duplicate_groups = self.map_relationships_to_groups(all_relationships)
        
        # Step 4: Validate each duplicate group and refine relationships
        for group in duplicate_groups:
            self.validate_duplicates(group)
        
        return sorted(duplicate_groups, key=lambda g: g.confidence_score, reverse=True)

    def analyze_edge_cases(self, group: DuplicateGroup) -> List[EdgeCaseAnalysis]:
        """
        Analyze a duplicate group for potential edge cases and issues.
        
        Args:
            group: DuplicateGroup to analyze
            
        Returns:
            List of EdgeCaseAnalysis objects for files requiring attention
        """
        edge_cases: List[EdgeCaseAnalysis] = []
        
        if not group.original:
            return edge_cases
            
        original_info = self.file_info_map[group.original]
        original_meta = original_info.video_metadata
        
        if not original_meta:
            return edge_cases
        
        # Check each duplicate for potential issues
        for duplicate_path in group.duplicates:
            duplicate_info = self.file_info_map[duplicate_path]
            
            # First check if metadata exists
            if not duplicate_info.video_metadata:
                edge_cases.append(EdgeCaseAnalysis(
                    file_path=duplicate_path,
                    issue_type=EdgeCaseType.METADATA,
                    severity=Severity.HIGH,
                    details="Missing or invalid video metadata",
                    recommendation="Manual verification required - file may be corrupted"
                ))
                continue
            
            duplicate_meta = duplicate_info.video_metadata
            validation = group.validation_results.get(duplicate_path)
            
            # Skip remaining checks if we don't have validation results
            if not validation:
                continue
            
            # Check for aspect ratio issues
            if not validation.aspect_ratio_match:
                edge_cases.append(EdgeCaseAnalysis(
                    file_path=duplicate_path,
                    issue_type=EdgeCaseType.ASPECT_RATIO,
                    severity=Severity.MEDIUM,
                    details=f"Aspect ratio mismatch: original={original_meta.width/original_meta.height:.2f}, duplicate={duplicate_meta.width/duplicate_meta.height:.2f}",
                    recommendation="Manual review needed - possible crop or different content"
                ))
            
            # Check for suspicious timestamps (only video metadata, no filesystem dates)
            if not validation.timestamp_valid:
                # Only analyze video metadata creation time
                if (original_meta.creation_time and duplicate_meta.creation_time):
                    time_diff_seconds = abs(
                        (duplicate_meta.creation_time - original_meta.creation_time).total_seconds()
                    )
                    time_diff_days = time_diff_seconds / (24 * 3600)
                    edge_cases.append(EdgeCaseAnalysis(
                        file_path=duplicate_path,
                        issue_type=EdgeCaseType.TIMESTAMP,
                        severity=Severity.HIGH,
                        details=f"Video creation times differ by {time_diff_days:.1f} days ({time_diff_seconds:.0f} seconds) - likely different recordings with same name",
                        recommendation="These appear to be different videos despite identical names and durations"
                    ))
            
            # Check for quality issues (bitrate, size)
            if not validation.bitrate_valid or not validation.size_correlation_valid:
                edge_cases.append(EdgeCaseAnalysis(
                    file_path=duplicate_path,
                    issue_type=EdgeCaseType.QUALITY,
                    severity=Severity.MEDIUM,
                    details="File size or bitrate doesn't match expected ratio for resolution",
                    recommendation="Check for quality loss or compression issues"
                ))
            
            # Duration check
            duration_diff = abs(duplicate_meta.duration - original_meta.duration)
            if duration_diff > self.DURATION_TOLERANCE:
                edge_cases.append(EdgeCaseAnalysis(
                    file_path=duplicate_path,
                    issue_type=EdgeCaseType.DURATION_MISMATCH,
                    severity=Severity.HIGH,
                    details=f"Duration difference of {duration_diff:.2f} seconds exceeds tolerance",
                    recommendation="Files may be different content despite same name"
                ))
        
        return edge_cases
    
    def get_action_recommendations(self, group: DuplicateGroup) -> List[ActionRecommendation]:
        """
        Generate action recommendations for each file in a duplicate group.
        
        Args:
            group: DuplicateGroup to analyze
            
        Returns:
            List of ActionRecommendation objects
        """
        recommendations: List[ActionRecommendation] = []
        
        # Analyze edge cases
        edge_cases = self.analyze_edge_cases(group)
        edge_case_paths = {ec.file_path for ec in edge_cases}
        
        # Always preserve the original
        if group.original:
            recommendations.append(ActionRecommendation(
                file_path=group.original,
                action=Action.PRESERVE,
                reason="Original high-resolution file",
                confidence=1.0
            ))
        
        # Process each duplicate
        for duplicate_path in group.duplicates:
            validation = group.validation_results.get(duplicate_path)
            
            # First check for edge cases that require manual review
            if duplicate_path in edge_case_paths:
                # Get all edge cases for this path
                issues = [ec for ec in edge_cases if ec.file_path == duplicate_path]
                
                # Check for severe issues that require manual review
                if any(ec.severity == Severity.HIGH for ec in issues):
                    recommendations.append(ActionRecommendation(
                        file_path=duplicate_path,
                        action=Action.MANUAL_REVIEW,
                        reason="File has critical issues requiring manual review",
                        confidence=0.9
                    ))
                    continue
                
                # Check for aspect ratio mismatches specifically
                if any(ec.issue_type == EdgeCaseType.ASPECT_RATIO for ec in issues):
                    recommendations.append(ActionRecommendation(
                        file_path=duplicate_path,
                        action=Action.MANUAL_REVIEW,
                        reason="Aspect ratio mismatch requires manual review",
                        confidence=0.8
                    ))
                    continue
                
                # For other medium severity issues, recommend verification
                if any(ec.severity == Severity.MEDIUM for ec in issues):
                    recommendations.append(ActionRecommendation(
                        file_path=duplicate_path,
                        action=Action.VERIFY,
                        reason="File has issues requiring verification",
                        confidence=0.7
                    ))
                    continue
            
            # If we have valid metadata and high confidence, recommend deletion
            if validation and validation.overall_score >= self.MIN_CONFIDENCE_SCORE:
                recommendations.append(ActionRecommendation(
                    file_path=duplicate_path,
                    action=Action.SAFE_DELETE,
                    reason=f"Confirmed lower-resolution duplicate (Score: {validation.overall_score:.2f})",
                    confidence=validation.overall_score
                ))
            else:
                # For low confidence matches, recommend verification
                recommendations.append(ActionRecommendation(
                    file_path=duplicate_path,
                    action=Action.VERIFY,
                    reason="Low confidence duplicate match",
                    confidence=validation.overall_score if validation else 0.5
                ))
        
        return recommendations

    def _validate_resolution_chain(self, original_metadata, variants):
        """Validate resolution chain, including rotation cases."""
        issues = []
        for variant in variants:
            aspect_ratio_original = original_metadata.width / original_metadata.height
            aspect_ratio_variant = variant.width / variant.height

            # Check for rotation (aspect ratio swapped)
            if abs(aspect_ratio_original - (1 / aspect_ratio_variant)) < self.ASPECT_RATIO_TOLERANCE:
                issues.append(f"Rotation detected: {variant.path} (rotated resolution)")
                confidence_score += 0.2  # Boost confidence for rotation cases
            elif abs(aspect_ratio_original - aspect_ratio_variant) > self.ASPECT_RATIO_TOLERANCE:
                issues.append(f"Aspect ratio mismatch: {variant.path}")

        return issues
