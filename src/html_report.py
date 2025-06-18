"""
HTML Report Generator Module.
Generates interactive HTML interface for bulk video duplicate management.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import asdict

from src.thumbnail_generator import ThumbnailGenerator
from src.report import VideoRelationship, ReportGenerator
from src.data_structures import MetadataStore


class HTMLReportGenerator:
    """Generates interactive HTML reports for duplicate video management"""
    
    def __init__(self, relationships: List[VideoRelationship], 
                 base_dir: Path, metadata_store: MetadataStore):
        """Initialize HTML report generator.
        
        Args:
            relationships: List of VideoRelationship objects
            base_dir: Base directory for relative path calculations
            metadata_store: MetadataStore containing file metadata
        """
        self.relationships = relationships
        self.base_dir = base_dir
        self.metadata_store = metadata_store
        self.thumbnail_generator = ThumbnailGenerator()
    
    def _get_relative_path(self, path: Path) -> str:
        """Convert path relative to base directory for cleaner output."""
        try:
            return str(path.relative_to(self.base_dir))
        except ValueError:
            return str(path)
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"
    
    def _prepare_data_for_html(self) -> Dict[str, Any]:
        """Prepare relationship data for HTML/JavaScript consumption."""
        groups = []
        total_size = 0
        total_duplicates = 0
        
        for relationship in self.relationships:
            # Get original file info
            original_info = self.metadata_store.files[str(relationship.original.path)]
            original_thumbnail = self.thumbnail_generator.generate_thumbnail(relationship.original.path)
            if not original_thumbnail:
                original_thumbnail = self.thumbnail_generator.generate_placeholder_thumbnail()
            
            # Prepare duplicates data
            duplicates = []
            group_size = original_info.file_size
            
            for variant in relationship.variants:
                variant_info = self.metadata_store.files[str(variant.path)]
                variant_thumbnail = self.thumbnail_generator.generate_thumbnail(variant.path)
                if not variant_thumbnail:
                    variant_thumbnail = self.thumbnail_generator.generate_placeholder_thumbnail()
                
                # Check validation results
                validation = relationship.validation_results.get(variant.path)
                issues = []
                if validation:
                    if not validation.aspect_ratio_match:
                        issues.append("Aspect ratio mismatch")
                    if not validation.timestamp_valid:
                        issues.append("Timestamp mismatch")
                    if not validation.size_correlation_valid:
                        issues.append("Size correlation invalid")
                    if not validation.bitrate_valid:
                        issues.append("Bitrate invalid")
                    if validation.is_rotated:
                        issues.append("Rotated variant")
                
                # Select all duplicates by default (not just high-confidence ones)
                pre_selected = True
                
                duplicate_data = {
                    'path': str(variant.path),
                    'relative_path': self._get_relative_path(variant.path),
                    'thumbnail': variant_thumbnail,
                    'size': variant_info.file_size,
                    'size_formatted': self._format_file_size(variant_info.file_size),
                    'resolution': f"{variant.width}x{variant.height}",
                    'confidence': variant.confidence_score,
                    'issues': issues,
                    'pre_selected': pre_selected,
                    'created_at': variant_info.created_at.isoformat() if variant_info.created_at else None,
                    'modified_at': variant_info.modified_at.isoformat() if variant_info.modified_at else None
                }
                
                duplicates.append(duplicate_data)
                group_size += variant_info.file_size
                if pre_selected:
                    total_duplicates += 1
            
            # Prepare group data
            group_data = {
                'id': f"group_{len(groups)}",
                'filename': relationship.filename,
                'confidence': relationship.total_confidence,
                'original': {
                    'path': str(relationship.original.path),
                    'relative_path': self._get_relative_path(relationship.original.path),
                    'thumbnail': original_thumbnail,
                    'size': original_info.file_size,
                    'size_formatted': self._format_file_size(original_info.file_size),
                    'resolution': f"{relationship.original.width}x{relationship.original.height}",
                    'created_at': original_info.created_at.isoformat() if original_info.created_at else None,
                    'modified_at': original_info.modified_at.isoformat() if original_info.modified_at else None
                },
                'duplicates': duplicates,
                'total_size': group_size,
                'total_size_formatted': self._format_file_size(group_size),
                'duplicate_count': len(duplicates),
                'pre_selected_count': sum(1 for d in duplicates if d['pre_selected'])
            }
            
            groups.append(group_data)
            total_size += group_size
        
        # Calculate potential savings (size of all pre-selected duplicates)
        potential_savings = sum(
            d['size'] for group in groups 
            for d in group['duplicates'] if d['pre_selected']
        )
        
        # Count total pre-selected duplicates
        total_pre_selected = sum(
            sum(1 for d in group['duplicates'] if d['pre_selected'])
            for group in groups
        )
        
        return {
            'groups': groups,
            'summary': {
                'total_groups': len(groups),
                'total_duplicates': sum(len(g['duplicates']) for g in groups),
                'pre_selected_duplicates': total_pre_selected,
                'total_size': total_size,
                'total_size_formatted': self._format_file_size(total_size),
                'potential_savings': potential_savings,
                'potential_savings_formatted': self._format_file_size(potential_savings),
                'generated_at': datetime.now().isoformat()
            }
        }
    
    def generate_html_report(self, output_dir: Path = None) -> Path:
        """Generate complete HTML report file.
        
        Args:
            output_dir: Directory to save HTML file. Defaults to current working directory.
            
        Returns:
            Path to generated HTML file
        """
        if output_dir is None:
            output_dir = Path.cwd()
        
        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        html_file = output_dir / f"duplicate_report_{timestamp}.html"
        
        # Prepare data
        data = self._prepare_data_for_html()
        
        # Debug output
        print(f"DEBUG: Prepared {len(data['groups'])} groups for HTML")
        print(f"DEBUG: Summary: {data['summary']}")
        if data['groups']:
            print(f"DEBUG: First group: {data['groups'][0]['filename']} with {len(data['groups'][0]['duplicates'])} duplicates")
        
        # Generate HTML content
        html_content = self._generate_html_template(data)
        
        # Write HTML file
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return html_file
    
    def _generate_html_template(self, data: Dict[str, Any]) -> str:
        """Generate complete HTML template with embedded data and JavaScript."""
        
        # Convert data to JSON for embedding
        data_json = json.dumps(data, indent=2)
        
        html_template = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Video Duplicate Manager</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }}
        
        .summary {{
            background: white;
            margin: 2rem auto;
            max-width: 1200px;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        
        .summary-item {{
            text-align: center;
            padding: 1rem;
            background: #f8f9fa;
            border-radius: 4px;
        }}
        
        .summary-item .value {{
            font-size: 2rem;
            font-weight: bold;
            color: #667eea;
            display: block;
        }}
        
        .summary-item .label {{
            color: #666;
            font-size: 0.9rem;
        }}
        
        .controls {{
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
            justify-content: center;
            margin-bottom: 2rem;
        }}
        
        .btn {{
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 1rem;
            transition: all 0.3s ease;
        }}
        
        .btn-primary {{
            background: #667eea;
            color: white;
        }}
        
        .btn-secondary {{
            background: #6c757d;
            color: white;
        }}
        
        .btn-success {{
            background: #28a745;
            color: white;
        }}
        
        .btn-warning {{
            background: #ffc107;
            color: #212529;
        }}
        
        .btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 1rem;
        }}
        
        .group {{
            background: white;
            margin-bottom: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        
        .group-header {{
            background: #f8f9fa;
            padding: 1rem 1.5rem;
            border-bottom: 1px solid #e9ecef;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .group-header:hover {{
            background: #e9ecef;
        }}
        
        .group-title {{
            font-size: 1.2rem;
            font-weight: 600;
        }}
        
        .group-info {{
            display: flex;
            gap: 1rem;
            font-size: 0.9rem;
            color: #666;
            align-items: center;
        }}
        
        .confidence-badge {{
            padding: 0.25rem 0.5rem;
            border-radius: 12px;
            font-size: 0.8rem;
            font-weight: 600;
        }}
        
        .confidence-high {{ background: #d4edda; color: #155724; }}
        .confidence-medium {{ background: #fff3cd; color: #856404; }}
        .confidence-low {{ background: #f8d7da; color: #721c24; }}
        
        .group-content {{
            display: block;
            padding: 1.5rem;
        }}
        
        .group.collapsed .group-content {{
            display: none;
        }}
        
        .original-file {{
            background: #e8f5e8;
            border: 2px solid #28a745;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1.5rem;
        }}
        
        .original-label {{
            color: #28a745;
            font-weight: bold;
            font-size: 0.9rem;
            margin-bottom: 0.5rem;
        }}
        
        .file-item {{
            display: flex;
            align-items: center;
            gap: 1rem;
            padding: 1rem;
            border: 1px solid #e9ecef;
            border-radius: 4px;
            margin-bottom: 0.5rem;
        }}
        
        .file-thumbnail {{
            width: 150px;
            height: 100px;
            object-fit: cover;
            border-radius: 4px;
            flex-shrink: 0;
        }}
        
        .file-info {{
            flex: 1;
        }}
        
        .file-path {{
            font-weight: 600;
            margin-bottom: 0.25rem;
            word-break: break-all;
        }}
        
        .file-metadata {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 0.5rem;
            color: #666;
            font-size: 0.9rem;
        }}
        
        .duplicate-item {{
            background: #fff8f0;
            border-left: 4px solid #ffc107;
        }}
        
        .duplicate-checkbox {{
            margin-right: 1rem;
        }}
        
        .duplicate-checkbox input[type="checkbox"] {{
            width: 18px;
            height: 18px;
        }}
        
        .issues {{
            margin-top: 0.5rem;
        }}
        
        .issue-tag {{
            display: inline-block;
            background: #f8d7da;
            color: #721c24;
            padding: 0.2rem 0.5rem;
            border-radius: 12px;
            font-size: 0.8rem;
            margin-right: 0.5rem;
            margin-bottom: 0.25rem;
        }}
        
        .selection-summary {{
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            background: white;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            border: 1px solid #e9ecef;
            min-width: 250px;
        }}
        
        .selection-summary h4 {{
            margin-bottom: 0.5rem;
            color: #333;
        }}
        
        #confirmDialog {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
        }}
        
        .dialog-content {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 2rem;
            border-radius: 8px;
            max-width: 500px;
            width: 90%;
        }}
        
        .dialog-buttons {{
            display: flex;
            gap: 1rem;
            justify-content: flex-end;
            margin-top: 1.5rem;
        }}
        
        @media (max-width: 768px) {{
            .file-item {{
                flex-direction: column;
                align-items: flex-start;
            }}
            
            .file-thumbnail {{
                width: 100%;
                max-width: 300px;
            }}
            
            .selection-summary {{
                position: static;
                margin: 2rem auto;
                max-width: 1200px;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Video Duplicate Manager</h1>
        <p>Review and manage duplicate video files</p>
    </div>
    
    <div class="summary">
        <div class="summary-grid">
            <div class="summary-item">
                <span class="value" id="totalGroups">0</span>
                <span class="label">Duplicate Groups</span>
            </div>
            <div class="summary-item">
                <span class="value" id="totalDuplicates">0</span>
                <span class="label">Total Duplicates</span>
            </div>
            <div class="summary-item">
                <span class="value" id="selectedCount">0</span>
                <span class="label">Selected for Deletion</span>
            </div>
            <div class="summary-item">
                <span class="value" id="potentialSavings">0 B</span>
                <span class="label">Potential Space Savings</span>
            </div>
        </div>
        
        <div class="controls">
            <button class="btn btn-secondary" onclick="collapseAllGroups()">Collapse All</button>
            <button class="btn btn-primary" onclick="expandAllGroups()">Expand All</button>
            <button class="btn btn-warning" onclick="selectHighConfidence()">Select High Confidence Only</button>
            <button class="btn btn-secondary" onclick="deselectAll()">Deselect All</button>
            <button class="btn btn-secondary" onclick="selectAll()">Select All</button>
            <button class="btn btn-success" onclick="generateScript()">Generate Deletion Script</button>
        </div>
    </div>
    
    <div class="container">
        <div id="groupsContainer">
            <!-- Groups will be populated by JavaScript -->
        </div>
    </div>
    
    <div class="selection-summary">
        <h4>Selection Summary</h4>
        <div>Files selected: <span id="summaryCount">0</span></div>
        <div>Space to free: <span id="summarySavings">0 B</span></div>
    </div>
    
    <div id="confirmDialog">
        <div class="dialog-content">
            <h3>Generate Deletion Script</h3>
            <p>You have selected <span id="confirmCount">0</span> files for deletion.</p>
            <p>This will free approximately <span id="confirmSavings">0 B</span> of disk space.</p>
            <p><strong>The script will be downloaded to your Downloads folder. You must manually execute it to delete the files.</strong></p>
            <div class="dialog-buttons">
                <button class="btn btn-secondary" onclick="closeConfirmDialog()">Cancel</button>
                <button class="btn btn-success" onclick="downloadScript()">Download Script</button>
            </div>
        </div>
    </div>
    
    <script>
        // Embedded data from Python
        const duplicateData = {data_json};
        
        // Global state
        let selectedFiles = new Set();
        
        // Utility functions
        function escapeHtml(text) {{
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}
        
        // Initialize the interface
        document.addEventListener('DOMContentLoaded', function() {{
            console.log('DOM loaded, starting initialization...');
            console.log('Groups found:', duplicateData.groups.length);
            
            try {{
                renderSummary();
                renderGroups();
                updateSelectionSummary();
                console.log('Initialization complete');
            }} catch (error) {{
                console.error('Error during initialization:', error);
                document.getElementById('groupsContainer').innerHTML = '<p style="color: red;">Error: ' + error.message + '</p>';
            }}
        }});
        
        function renderSummary() {{
            console.log('Rendering summary...');
            const summary = duplicateData.summary;
            document.getElementById('totalGroups').textContent = summary.total_groups;
            document.getElementById('totalDuplicates').textContent = summary.total_duplicates;
            document.getElementById('selectedCount').textContent = summary.pre_selected_duplicates;
            document.getElementById('potentialSavings').textContent = summary.potential_savings_formatted;
            
            // Initialize with pre-selected files
            duplicateData.groups.forEach(group => {{
                group.duplicates.forEach(duplicate => {{
                    if (duplicate.pre_selected) {{
                        selectedFiles.add(duplicate.path);
                    }}
                }});
            }});
            console.log('Summary rendered');
        }}
        
        function renderGroups() {{
            console.log('Rendering groups...');
            const container = document.getElementById('groupsContainer');
            if (!container) {{
                console.error('Container not found!');
                return;
            }}
            
            container.innerHTML = '';
            
            duplicateData.groups.forEach((group, index) => {{
                console.log(`Rendering group ${{index}}: ${{group.filename}}`);
                try {{
                    const groupElement = createGroupElement(group);
                    container.appendChild(groupElement);
                }} catch (error) {{
                    console.error(`Error rendering group ${{index}}:`, error);
                    const errorDiv = document.createElement('div');
                    errorDiv.innerHTML = `<p style="color: red;">Error rendering group ${{group.filename}}: ${{error.message}}</p>`;
                    container.appendChild(errorDiv);
                }}
            }});
            console.log('Groups rendered');
        }}
        
        function createGroupElement(group) {{
            console.log('Creating element for group:', group.filename);
            const groupDiv = document.createElement('div');
            groupDiv.className = 'group';
            groupDiv.id = group.id;
            
            const confidenceClass = group.confidence >= 0.8 ? 'confidence-high' : 
                                  group.confidence >= 0.5 ? 'confidence-medium' : 'confidence-low';
            
            // Use simple innerHTML for now to avoid complex DOM issues
            groupDiv.innerHTML = `
                <div class="group-header" onclick="toggleGroup('${{group.id}}')">
                    <div class="group-title">${{escapeHtml(group.filename)}}</div>
                    <div class="group-info">
                        <span class="confidence-badge ${{confidenceClass}}">
                            ${{(group.confidence * 100).toFixed(1)}}% confidence
                        </span>
                        <span>${{group.duplicate_count}} duplicates</span>
                        <span>${{group.total_size_formatted}}</span>
                    </div>
                </div>
                <div class="group-content">
                    <div class="original-file">
                        <div class="original-label">✓ KEEP - Original File</div>
                        <div class="file-item">
                            <img src="${{group.original.thumbnail}}" alt="Thumbnail" class="file-thumbnail" onerror="this.style.display='none'">
                            <div class="file-info">
                                <div class="file-path">${{escapeHtml(group.original.relative_path)}}</div>
                                <div class="file-metadata">
                                    <div>Size: ${{escapeHtml(group.original.size_formatted)}}</div>
                                    <div>Resolution: ${{escapeHtml(group.original.resolution)}}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="duplicates">
                        ${{group.duplicates.map(duplicate => `
                            <div class="file-item duplicate-item">
                                <div class="duplicate-checkbox">
                                    <input type="checkbox" 
                                           id="check_${{duplicate.path.replace(/[^a-zA-Z0-9]/g, '_')}}"
                                           onchange="toggleFileSelection('${{duplicate.path.replace(/'/g, "\\\\'")}}');"
                                           ${{duplicate.pre_selected ? 'checked' : ''}}>
                                </div>
                                <img src="${{duplicate.thumbnail}}" alt="Thumbnail" class="file-thumbnail" onerror="this.style.display='none'">
                                <div class="file-info">
                                    <div class="file-path">${{escapeHtml(duplicate.relative_path)}}</div>
                                    <div class="file-metadata">
                                        <div>Size: ${{escapeHtml(duplicate.size_formatted)}}</div>
                                        <div>Resolution: ${{escapeHtml(duplicate.resolution)}}</div>
                                        <div>Confidence: ${{(duplicate.confidence * 100).toFixed(1)}}%</div>
                                    </div>
                                    ${{duplicate.issues.length > 0 ? '<div class="issues">' + duplicate.issues.map(issue => '<span class="issue-tag">' + escapeHtml(issue) + '</span>').join('') + '</div>' : ''}}
                                </div>
                            </div>
                        `).join('')}}
                    </div>
                </div>
            `;
            
            console.log('Group element created successfully');
            return groupDiv;
        }}
        
        function createFileItemHTML(file, isDuplicate) {{
            const issues = isDuplicate && file.issues.length > 0 ? 
                '<div class="issues">' + file.issues.map(issue => '<span class="issue-tag">' + escapeHtml(issue) + '</span>').join('') + '</div>' : '';
            
            return `
                <img src="${{file.thumbnail}}" alt="Thumbnail" class="file-thumbnail" onerror="this.style.display='none'">
                <div class="file-info">
                    <div class="file-path">${{escapeHtml(file.relative_path)}}</div>
                    <div class="file-metadata">
                        <div>Size: ${{escapeHtml(file.size_formatted)}}</div>
                        <div>Resolution: ${{escapeHtml(file.resolution)}}</div>
                        ${{isDuplicate ? '<div>Confidence: ' + (file.confidence * 100).toFixed(1) + '%</div>' : ''}}
                        <div>Created: ${{file.created_at ? new Date(file.created_at).toLocaleDateString() : 'Unknown'}}</div>
                    </div>
                    ${{issues}}
                </div>
            `;
        }}
        
        function toggleGroup(groupId) {{
            const group = document.getElementById(groupId);
            group.classList.toggle('collapsed');
        }}
        
        function expandAllGroups() {{
            document.querySelectorAll('.group').forEach(group => {{
                group.classList.remove('collapsed');
            }});
        }}
        
        function collapseAllGroups() {{
            document.querySelectorAll('.group').forEach(group => {{
                group.classList.add('collapsed');
            }});
        }}
        
        function toggleFileSelection(filePath) {{
            if (selectedFiles.has(filePath)) {{
                selectedFiles.delete(filePath);
            }} else {{
                selectedFiles.add(filePath);
            }}
            updateSelectionSummary();
        }}
        
        function selectHighConfidence() {{
            selectedFiles.clear();
            duplicateData.groups.forEach(group => {{
                group.duplicates.forEach(duplicate => {{
                    if (duplicate.confidence >= 0.8) {{
                        selectedFiles.add(duplicate.path);
                    }}
                }});
            }});
            updateCheckboxes();
            updateSelectionSummary();
        }}
        
        function selectAll() {{
            selectedFiles.clear();
            duplicateData.groups.forEach(group => {{
                group.duplicates.forEach(duplicate => {{
                    selectedFiles.add(duplicate.path);
                }});
            }});
            updateCheckboxes();
            updateSelectionSummary();
        }}
        
        function deselectAll() {{
            selectedFiles.clear();
            updateCheckboxes();
            updateSelectionSummary();
        }}
        
        function updateCheckboxes() {{
            duplicateData.groups.forEach(group => {{
                group.duplicates.forEach(duplicate => {{
                    const checkbox = document.getElementById(`check_${{duplicate.path.replace(/[^a-zA-Z0-9]/g, '_')}}`);
                    if (checkbox) {{
                        checkbox.checked = selectedFiles.has(duplicate.path);
                    }}
                }});
            }});
        }}
        
        function updateSelectionSummary() {{
            let totalSize = 0;
            let count = 0;
            
            duplicateData.groups.forEach(group => {{
                group.duplicates.forEach(duplicate => {{
                    if (selectedFiles.has(duplicate.path)) {{
                        totalSize += duplicate.size;
                        count++;
                    }}
                }});
            }});
            
            document.getElementById('summaryCount').textContent = count;
            document.getElementById('summarySavings').textContent = formatBytes(totalSize);
        }}
        
        function formatBytes(bytes) {{
            const units = ['B', 'KB', 'MB', 'GB', 'TB'];
            let size = bytes;
            let unitIndex = 0;
            
            while (size >= 1024 && unitIndex < units.length - 1) {{
                size /= 1024;
                unitIndex++;
            }}
            
            return `${{size.toFixed(1)}} ${{units[unitIndex]}}`;
        }}
        
        function generateScript() {{
            if (selectedFiles.size === 0) {{
                alert('No files selected for deletion.');
                return;
            }}
            
            // Update confirmation dialog
            let totalSize = 0;
            duplicateData.groups.forEach(group => {{
                group.duplicates.forEach(duplicate => {{
                    if (selectedFiles.has(duplicate.path)) {{
                        totalSize += duplicate.size;
                    }}
                }});
            }});
            
            document.getElementById('confirmCount').textContent = selectedFiles.size;
            document.getElementById('confirmSavings').textContent = formatBytes(totalSize);
            document.getElementById('confirmDialog').style.display = 'block';
        }}
        
        function closeConfirmDialog() {{
            document.getElementById('confirmDialog').style.display = 'none';
        }}
        
        function downloadScript() {{
            const selectedPaths = Array.from(selectedFiles);
            
            let scriptContent = `#!/bin/bash
# Video Duplicate Deletion Script
# Generated: ${{new Date().toISOString()}}
# Files to delete: ${{selectedPaths.length}}

echo "Video Duplicate Deletion Script"
echo "================================"
echo "Files to delete: ${{selectedPaths.length}}"
echo ""

# Confirmation
read -p "Are you sure you want to delete these files? (y/N): " confirm
if [[ $$confirm != [yY] ]]; then
    echo "Deletion cancelled."
    exit 0
fi

echo ""
echo "Deleting duplicate files..."

`;
            
            selectedPaths.forEach(filePath => {{
                // Escape the file path for bash - replace single quotes with '\''
                const escapedPath = filePath.replace(/'/g, "'\\''");
                scriptContent += `
if [ -f '${{escapedPath}}' ]; then
    echo "Deleting: ${{filePath}}"
    rm '${{escapedPath}}'
    if [ $$? -eq 0 ]; then
        echo "  ✓ Successfully deleted"
    else
        echo "  ✗ Failed to delete"
    fi
else
    echo "  ⚠ File not found: ${{filePath}}"
fi
`;
            }});
            
            scriptContent += `
echo ""
echo "Deletion script completed."
`;
            
            // Create and download the file
            const blob = new Blob([scriptContent], {{ type: 'text/plain' }});
            const url = URL.createObjectURL(blob);
            
            const a = document.createElement('a');
            a.href = url;
            a.download = 'selected_deletions.sh';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            
            URL.revokeObjectURL(url);
            closeConfirmDialog();
            
            alert(`Deletion script downloaded successfully!\\n\\nTo execute:\\n1. Open terminal\\n2. Navigate to your Downloads folder\\n3. Run: chmod +x selected_deletions.sh\\n4. Run: ./selected_deletions.sh`);
        }}
        
        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') {{
                closeConfirmDialog();
            }}
        }});
    </script>
</body>
</html>'''
        
        return html_template