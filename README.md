# Video Duplicate Detection App

## Summary
This application detects duplicate video files by analyzing their metadata, such as resolution, codec, bitrate, and aspect ratio. It generates a detailed report highlighting duplicate relationships and provides recommendations for actions like manual review or deletion.

## Installation
1. **Clone the repository:**
   ```bash
   git clone https://github.com/sarvesh1/video-duplicate-detection.git
   cd video-duplicate-detection
   ```
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage
To use the application:
1. Place your video files in a directory, for example `test_data/original/`.
2. Run the script using Python:
   ```bash
   python src/main.py test_data/original/
   ```
3. The script will analyze the video files and generate a report in the terminal or as a text file.

### Example Command
```bash
python src/main.py ~/myvideos/
```
This command assumes you have placed your video files in `~/myvideos/`. Adjust the path as necessary.

## Report Generation
The application generates a text report summarizing duplicate relationships and metadata details. The report includes:
- File paths of duplicate videos.
- Metadata comparison (e.g., resolution, codec).
- Recommended actions (e.g., manual review).

## Duplicate Detection Criteria

### Core Validation Attributes
The application analyzes multiple attributes to determine if videos are duplicates:

1. **Duration Match (Required)**
   - Videos must match within 1 second
   - Duration mismatches automatically disqualify duplicates
   - No tolerance for different lengths

2. **Resolution Analysis**
   - Checks for standard scaling patterns (e.g., 1080p → 720p → 480p)
   - Detects rotated variants (e.g., portrait vs. landscape)
   - Validates aspect ratio consistency

3. **Technical Metadata**
   - Video codec compatibility
   - Audio codec and sample rate
   - Bitrate correlation
   - File size relationships

4. **File Information**
   - Creation timestamps
   - Modification dates
   - File naming patterns

### Confidence Score Calculation
The confidence score (0-1) is calculated using weighted attributes:

#### Primary Weights
- Aspect Ratio Match: 40%
- Bitrate Correlation: 30%
- File Size Correlation: 20%
- Timestamp Proximity: 10%

#### Additional Factors
- Rotation Detection: +20% bonus
- Missing Metadata: Significant penalty
- Resolution Chain Inconsistency: Reduces confidence

#### Confidence Levels
- 1.0: Perfect match
- ≥0.8: High confidence (safe to consider duplicate)
- 0.5-0.8: Medium confidence (needs verification)
- <0.5: Low confidence (requires manual review)

## Contributing
We welcome contributions from anyone! Please read the [CONTRIBUTING.md](https://github.com/sarvesh1/video-duplicate-detection/blob/main/CONTRIBUTING.md) for guidelines on how to contribute to this project.

## License
This project is licensed under the MIT License - see the [LICENSE.md](https://github.com/sarvesh1/video-duplicate-detection/blob/main/LICENSE.md) file for details.