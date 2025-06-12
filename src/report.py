"""
Reporting module for generating file inventory reports.
"""

from typing import Dict, List
from data_structures import MetadataStore
from scanner import FileMetadata
from pathlib import Path
import humanize
from statistics import mean

class InventoryReport:
    """
    Generates reports about the video file inventory
    """
    
    def __init__(self, metadata_store: MetadataStore):
        self.store = metadata_store
    
    def generate_summary(self) -> str:
        """
        Generate a summary report of all files
        
        Returns:
            Formatted string containing the report
        """
        total_files = len(self.store.files)
        total_size = sum(meta.file_size for meta in self.store.files.values())
        
        # Find filename collisions
        collisions = {
            filename: paths 
            for filename, paths in self.store.filename_index.items()
            if len(paths) > 1
        }
        
        # Collect video metadata statistics
        valid_video_count = 0
        total_duration = 0.0
        resolutions = {}
        codecs = {}
        fps_values = []
        
        for meta in self.store.files.values():
            if meta.video_metadata:
                valid_video_count += 1
                total_duration += meta.video_metadata.duration
                resolution = meta.video_metadata.resolution
                resolutions[resolution] = resolutions.get(resolution, 0) + 1
                codecs[meta.video_metadata.codec] = codecs.get(meta.video_metadata.codec, 0) + 1
                fps_values.append(meta.video_metadata.fps)
        
        # Generate report
        report = []
        report.append("=== Video File Inventory Report ===\n")
        
        # Overall statistics
        report.append("Overall Statistics:")
        report.append(f"Total files: {total_files}")
        report.append(f"Total size: {humanize.naturalsize(total_size)}")
        report.append(f"Files with valid video metadata: {valid_video_count}")
        if valid_video_count > 0:
            report.append(f"Total video duration: {int(total_duration/3600)}h {int((total_duration%3600)/60)}m")
            report.append(f"Average FPS: {mean(fps_values):.2f}")
            report.append("\nResolutions found:")
            for res, count in sorted(resolutions.items(), key=lambda x: x[1], reverse=True):
                report.append(f"  {res}: {count} files")
            report.append("\nCodecs used:")
            for codec, count in sorted(codecs.items(), key=lambda x: x[1], reverse=True):
                report.append(f"  {codec}: {count} files")
        report.append("")
        
        # Files by directory
        report.append("Files by Directory:")
        for directory in sorted(self.store.directory_index.keys()):
            files = self.store.get_by_directory(directory)
            dir_size = sum(f.file_size for f in files)
            report.append(f"  {directory}:")
            report.append(f"    Files: {len(files)}")
            report.append(f"    Size: {humanize.naturalsize(dir_size)}\n")
        
        # Filename collisions
        if collisions:
            report.append("\nPotential Duplicates (Same Filename):")
            for filename, paths in collisions.items():
                report.append(f"\n  {filename}:")
                for path in sorted(paths):
                    metadata = self.store.files[path]
                    report.append(f"    - {path}")
                    report.append(f"      Size: {humanize.naturalsize(metadata.file_size)}")
                    report.append(f"      Modified: {metadata.modification_time}")
        
        return "\n".join(report)
