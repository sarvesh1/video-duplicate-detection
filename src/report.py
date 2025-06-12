"""
Reporting module for generating file inventory and duplicate analysis reports.
"""

from dataclasses import dataclass
from typing import Dict, List, Any
from data_structures import MetadataStore, FileInfo
from duplicate_detector import DuplicateGroup, VideoRelationship, ResolutionVariant
from pathlib import Path
import humanize
from statistics import mean

@dataclass
class DuplicateAnalysis:
    """Detailed analysis of a duplicate group"""
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
        """
        Initialize the report generator.
        
        Args:
            relationships: List of VideoRelationship objects to analyze
            base_dir: Base directory for relative path calculations
            metadata_store: MetadataStore containing file metadata
        """
        self.relationships = relationships
        self.base_dir = base_dir
        self.metadata_store = metadata_store
        
    def _get_relative_path(self, path: Path) -> str:
        """Get path relative to base directory for cleaner output"""
        try:
            return str(path.relative_to(self.base_dir))
        except ValueError:
            return str(path)

    def analyze_relationships(self) -> List[DuplicateAnalysis]:
        """
        Analyze each relationship group and generate detailed statistics.
        
        Returns:
            List of DuplicateAnalysis objects
        """
        analyses = []
        for rel in self.relationships:
            # Get original file info
            original = rel.original
            original_resolution = f"{original.width}x{original.height}"
            
            # Analyze variants
            duplicates = []
            total_size = 0
            issues = []
            
            # Add original file size to total if available
            orig_info = self.metadata_store.files.get(str(original.path))
            if orig_info:
                total_size += orig_info.file_size
            
            # Validate resolution chain
            chain_analysis = self._validate_resolution_chain(rel)
            resolution_chain_valid = chain_analysis['is_consistent']
            
            # Check for common resolution chain issues
            if not chain_analysis['is_consistent']:
                issues.append("Inconsistent resolution scaling")
            elif chain_analysis['missing_common_ratios']:
                issues.append(
                    f"Missing common resolutions: {', '.join(str(r) for r in chain_analysis['missing_common_ratios'])}"
                )
            
            # Process each variant
            for variant in rel.variants:
                variant_issues = self._collect_group_issues(chain_analysis, rel)
                resolution = f"{variant.width}x{variant.height}"
                
                # Get file size from metadata store
                file_info = self.metadata_store.files.get(str(variant.path))
                variant_size = file_info.file_size if file_info else 0
                
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

    def _validate_resolution_chain(self, rel: VideoRelationship) -> Dict[str, Any]:
        """Validate the resolution chain in a relationship"""
        resolutions = [(rel.original.width, rel.original.height)]
        for v in rel.variants:
            resolutions.append((v.width, v.height))
        resolutions.sort(key=lambda x: x[0] * x[1], reverse=True)
        
        is_consistent = True
        scale_ratios = set()
        
        # Check all resolution pairs for ratios
        for i in range(len(resolutions)):
            for j in range(i + 1, len(resolutions)):
                curr_res = resolutions[i]
                next_res = resolutions[j]
                
                width_ratio = next_res[0] / curr_res[0]
                height_ratio = next_res[1] / curr_res[1]
                
                # Check for consistent scaling and reasonable ratios
                if not (0.1 <= width_ratio <= 1.0 and abs(width_ratio - height_ratio) < 0.01):
                    is_consistent = False
                
                scale_ratios.add(round(width_ratio, 2))
        
        # Common scale ratios (e.g., 1080p->720p->480p)
        common_ratios = {0.67, 0.44}  # 1080p->720p (0.67), 720p->480p (0.44)
        missing_ratios = common_ratios - scale_ratios
        
        return {
            'is_consistent': is_consistent,
            'scale_ratios': sorted(scale_ratios),
            'missing_common_ratios': sorted(missing_ratios),
            'resolution_count': len(resolutions)
        }

    def _collect_group_issues(self, chain_analysis: Dict[str, Any], rel: VideoRelationship) -> List[str]:
        """Collect any issues with a duplicate group"""
        issues = []
        
        # Resolution chain issues
        if not chain_analysis['is_consistent']:
            issues.append("Inconsistent resolution scaling")
        
        # Low confidence score
        if rel.total_confidence < 0.7:
            issues.append("Low confidence match")
        
        return issues

    def generate_text_report(self) -> str:
        """
        Generate a detailed text report of duplicate analysis.
        
        Returns:
            Formatted string containing the analysis report
        """
        analyses = self.analyze_relationships()
        
        if not analyses:
            return "No duplicates found."
        
        # Calculate overall statistics
        total_groups = len(analyses)
        total_duplicates = sum(len(a.duplicates) for a in analyses)
        total_size = sum(a.total_size for a in analyses)
        total_savings = sum(a.potential_savings for a in analyses)
        
        # Build report
        lines = ["=== Video Duplicate Analysis Report ===\n"]
        
        # Overall summary
        lines.extend([
            "Overall Statistics:",
            f"- Total duplicate groups: {total_groups}",
            f"- Total duplicate files: {total_duplicates}",
            f"- Total size of duplicates: {humanize.naturalsize(total_size)}",
            f"- Potential space savings: {humanize.naturalsize(total_savings)}",
            ""
        ])
        
        # Detailed group analysis
        lines.append("Duplicate Groups (sorted by confidence):\n")
        
        for i, analysis in enumerate(analyses, 1):
            lines.extend([
                f"Group {i}:",
                f"Original: {self._get_relative_path(analysis.original_path)}",
                f"Resolution: {analysis.original_resolution}",
                f"Confidence Score: {analysis.confidence_score:.2f}",
                "Duplicates:"
            ])
            
            for dup in analysis.duplicates:
                dup_lines = [
                    f"- {self._get_relative_path(dup['path'])}",
                    f"  Resolution: {dup['resolution']}",
                    f"  Size: {humanize.naturalsize(dup['size'])}",
                    f"  Confidence: {dup['confidence']:.2f}"
                ]
                
                if dup['issues']:
                    dup_lines.append(f"  Issues: {', '.join(dup['issues'])}")
                
                lines.extend(dup_lines)
            
            if analysis.issues:
                lines.extend([
                    "Group Issues:",
                    *[f"- {issue}" for issue in analysis.issues]
                ])
            
            lines.append("")  # Empty line between groups
        
        return "\n".join(lines)
