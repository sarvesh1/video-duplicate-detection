#!/usr/bin/env python3
"""Test script to validate HTML file JavaScript"""

import re
import json

# Read the HTML file
import glob
html_files = glob.glob('duplicate_report_*.html')
if not html_files:
    print("No HTML files found")
    exit(1)
    
html_file = html_files[0]
print(f"Testing {html_file}")

with open(html_file, 'r') as f:
    content = f.read()

# Extract the JavaScript data
data_match = re.search(r'const duplicateData = ({.*?});', content, re.DOTALL)
if data_match:
    try:
        # Remove comments and validate JSON structure
        data_str = data_match.group(1)
        data = json.loads(data_str)
        print(f"✓ JavaScript data is valid JSON")
        print(f"✓ Found {len(data['groups'])} groups")
        print(f"✓ Summary: {data['summary']['total_groups']} groups, {data['summary']['total_duplicates']} duplicates")
        
        # Check if groups have required fields
        for i, group in enumerate(data['groups']):
            required_fields = ['id', 'filename', 'original', 'duplicates']
            for field in required_fields:
                if field not in group:
                    print(f"✗ Group {i} missing field: {field}")
                else:
                    print(f"✓ Group {i} has {field}")
                    
    except json.JSONDecodeError as e:
        print(f"✗ JavaScript data is invalid JSON: {e}")
else:
    print("✗ Could not find JavaScript data in HTML file")

# Check for basic JavaScript syntax issues
if 'escapeHtml' in content:
    print("✓ escapeHtml function found")
else:
    print("✗ escapeHtml function not found")

if 'DOMContentLoaded' in content:
    print("✓ DOMContentLoaded event listener found")
else:
    print("✗ DOMContentLoaded event listener not found")

# Check for common template string issues
template_issues = re.findall(r'\$\{[^}]*\$\{[^}]*\}[^}]*\}', content)
if template_issues:
    print(f"⚠ Found {len(template_issues)} potentially nested template strings")
else:
    print("✓ No nested template string issues found")