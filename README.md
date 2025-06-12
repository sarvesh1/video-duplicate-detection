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

## Contributing
We welcome contributions from anyone! Please read the [CONTRIBUTING.md](https://github.com/sarvesh1/video-duplicate-detection/blob/main/CONTRIBUTING.md) for guidelines on how to contribute to this project.

## License
This project is licensed under the MIT License - see the [LICENSE.md](https://github.com/sarvesh1/video-duplicate-detection/blob/main/LICENSE.md) file for details.