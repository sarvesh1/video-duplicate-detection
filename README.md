## Video Duplicate Detection App

## Summary
This application is designed to detect and validate duplicate video files based on their resolution, codec, bitrate, and other metadata characteristics. It helps users identify similar or identical videos within their file system, which can be useful for cleaning up unnecessary storage or maintaining a library of unique videos.

## Installation
1. **Clone the repository:**
   ```bash
   git clone https://github.com/sarvesh1/videoduplicationdetectionapp.git
   cd videoduplicationdetectionapp
   ```
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage
To run the application on your local machine with example video files:
1. Place your video files in a directory, for example `videos/`.
2. Run the script using Python:
   ```bash
   python src/main.py --video_dir videos/
   ```
3. The script will analyze the video files and output any duplicates found based on their metadata.

### Example Command
```bash
python src/main.py --video_dir ~/myvideos/
```
This command assumes you have placed your video files in `~/myvideos/`. Adjust the path as necessary.

## Contributing
We welcome contributions from anyone! Please read the [CONTRIBUTING.md](https://github.com/sarvesh2/videoduplicationdetectionapp/blob/main/CONTRIBUTING.md) for guidelines on how to contribute to this project.

## License
This project is licensed under the MIT License - see the [LICENSE.md](https://github.com/sarvesh1/videoduplicationdetectionapp/blob/main/LICENSE.md) file for details.