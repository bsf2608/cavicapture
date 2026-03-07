# Cavicapture v2 - Complete Guide

**Cavicapture** is an automated image capture and processing system designed to detect embolism events in plant vascular systems. It captures continuous sequences of images and analyzes them using computer vision to identify pixel differences between image pairs.

> **Updated for Python 3** - This version has been modernized from Python 2 to Python 3 with comprehensive documentation for first-time users.

## 📋 Table of Contents

- [What is Cavicapture?](#what-is-cavicapture)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Usage](#usage)
- [Understanding the Processing Pipeline](#understanding-the-processing-pipeline)
- [Troubleshooting](#troubleshooting)

---

## 🎯 What is Cavicapture?

Cavicapture is a scientific instrument control and image analysis system used to study **cavitation/embolism** - the formation of air bubbles in plant xylem vessels under water stress. 

**Key Features:**
- Automated image capture via Raspberry Pi Camera Module
- Real-time image difference detection and analysis
- SQLite database for storing analysis results
- 6-step image processing pipeline with noise removal
- Optional Region-of-Interest (ROI) analysis
- Configurable LED lighting control via GPIO
- Python 3 compatible

---

## 💻 System Requirements

### Hardware
- **Raspberry Pi** (Pi 3 or newer recommended)
- **Raspberry Pi Camera Module** (V2 recommended)
- **GPIO-controlled LED lights** (connected to configured GPIO pin)
- **SD Card** (16GB minimum recommended)

### Software
- **Python 3.7+**
- **OpenCV** (`opencv-python-headless` or `opencv-python`)
- **NumPy**
- **PIL/Pillow**
- **SQLite3** (Usually pre-installed)
- **RPi.GPIO** (For Raspberry Pi GPIO control)
- **picamera2** (Raspberry Pi Camera support via libcamera)

> **Note:** The legacy `picamera` library is no longer used on modern OS releases.  
> Cavicapture now uses `picamera2` and requires the libcamera stack.
- **matplotlib** (For calibration plotting)

---

## 🔧 Installation

### Step 1: Install Python 3

**On Raspberry Pi OS:**
```bash
sudo apt-get update
sudo apt-get install python3 python3-pip python3-venv -y
```

### Step 2: Clone/Download Cavicapture

```bash
cd ~
git clone https://github.com/bsf2608/cavicapture.git
cd cavicapture
git checkout 2.0
```

Or download and extract the ZIP file manually.

### Step 3: Install Required Dependencies

**Using apt-get (System-wide, Recommended)**
```bash
sudo apt-get install python3-opencv python3-numpy python3-pil python3-matplotlib python3-rpi.gpio python3-picamera2 -y
# on 64-bit Pi OS the legacy python3-picamera is not required and may not work
```

**Alternative: Using pip**
```bash
# Note: On newer Raspberry Pi OS versions, you may need to use --break-system-packages or install via apt-get instead
pip3 install --upgrade pip
pip3 install opencv-python-headless numpy pillow matplotlib RPi.GPIO picamera2
```

### Step 4: Verify Installation

Test that all modules are installed correctly:

```bash
python3 << EOF
import cv2
import numpy as np
import RPi.GPIO as GPIO
# test new camera library
from picamera2 import Picamera2
import sqlite3
import matplotlib.pyplot as plt
print("✓ All dependencies installed successfully!") # picamera2 import verified

# optional quick camera test
# python3 test_camera.py    (runs picamera2 capture at full resolution)
EOF
```

---

## ⚡ Quick Start

### 1. Configure the Application

A local `config.ini` has been created for you from the template. You can directly edit it to begin:

```bash
nano config.ini
```

Edit the configuration (see [Configuration](#configuration) section below).

### 2. Generate a Preview

Test your setup with a single test image:

```bash
sudo python3 cavicapture.py --config config.ini --preview
```

This creates a `preview.png` file in your output directory.

### 3. Run Image Capture (5 hours, 5-minute intervals)

```bash
sudo python3 cavicapture.py --config config.ini
```

### 4. Process Images (Run in parallel - in another terminal)

```bash
python3 caviprocess.py --config config.ini
```

### 5. View Results

Results are stored in SQLite database at: `{output_dir}/{sequence_name}/capture.db`

Use a SQLite browser (e.g., [SQLiteBrowser](https://sqlitebrowser.org/)) to view results.

---

## 📁 Project Structure

```
├── cavicapture.py          # Main image capture script
├── caviprocess.py          # Image processing script
├── calibrate.py            # System calibration tool
├── seq_converter.py        # Convert existing image sequences
├── config.ini              # Main active configuration file
├── example_config.ini      # Template configuration file
├── README.md               # User manual (this file)
├── INSTALLATION.md         # Detailed installation guide
├── USAGE.md                # Usage guides and workflows
├── instructions.md         # Original legacy instructions
├── LICENSE                 # License information
├── samples/                # Sample data directory
└── reports/                # Project conversion and audit reports
```

### File Descriptions

| File | Purpose |
|------|---------|
| **cavicapture.py** | Controls the camera, captures images on schedule, stores metadata in SQLite |
| **caviprocess.py** | Analyzes captured image pairs, detects differences, applies filters, saves results |
| **calibrate.py** | Calibration tool to establish noise baselines and test filter settings |
| **seq_converter.py** | Utility to convert external image sequences into Cavicapture format |

---

## ⚙️ Configuration

### Configuration File Format

Create an INI file with the following sections:

```ini
[camera]
ISO=100
shutter_speed=1500

[capture]
duration=5
interval=300
output_dir=./captures
sequence_name=experiment_001
verbose=On
resolution=Max
crop=0.17,0.26,0.45,0.49
crop_enabled=Off
light_source=Above

[process]
processor=./caviprocess.py
intermediates_enabled=Off
outlier_removal_enabled=On
filtering_enabled=On
thresholding_enabled=On
difference_enabled=On
roi_enabled=Off
roi=0.17,0.26,0.45,0.49
verbose=On
filter_threshold=7

[pi]
GPIO_light_channel=7
```

### Configuration Parameters Explained

#### Camera Settings

| Parameter | Description | Example |
|-----------|-------------|---------|
| **ISO** | Camera light sensitivity (1-1600) | `100` = low sensitivity, good for bright light |
| **shutter_speed** | Exposure time in microseconds | `1500` = slow shutter, more light capture |

#### Capture Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| **duration** | Total capture time in hours | `5` = 5 hours |
| **interval** | Seconds between image captures | `300` = 1 image every 5 minutes |
| **output_dir** | Where to save captured images and database | `./captures` |
| **sequence_name** | Folder name for this experiment | `experiment_001` |
| **verbose** | Log all actions (On/Off) | `On` |
| **resolution** | Image size: Max(3280×2464), Large(1920×1080), Medium(1296×972), Small(640×480) | `Max` |
| **crop_enabled** | Crop images to ROI (On/Off) | `Off` |
| **crop** | Region to keep: x1,y1,x2,y2 (% of image) | `0.17,0.26,0.45,0.49` |
| **light_source** | Light position: Above or Below | `Above` |

#### Processing Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| **filter_threshold** | Minimum pixel difference to keep (0-255) | `7` |
| **outlier_removal_enabled** | Remove isolated noise pixels (On/Off) | `On` |
| **filtering_enabled** | Apply threshold filter (On/Off) | `On` |
| **thresholding_enabled** | Set remaining pixels to white (On/Off) | `On` |
| **difference_enabled** | Calculate image differences (On/Off) | `On` |
| **roi_enabled** | Only count differences in ROI (On/Off) | `Off` |
| **roi** | ROI region: x1,y1,x2,y2 (% of image) | Same as crop |
| **intermediates_enabled** | Save processing stages (On/Off) | `Off` |
| **verbose** | Log processing steps (On/Off) | `On` |

#### Raspberry Pi Settings

| Parameter | Description |
|-----------|-------------|
| **GPIO_light_channel** | GPIO pin number for LED control (BCM numbering) |

---

## 🚀 Usage

### Basic Usage

#### 1. Capture Images Only

```bash
sudo python3 cavicapture.py --config config.ini
```

**Output:**
- Sequence of PNG images in `{output_dir}/{sequence_name}/`
- SQLite database: `capture.db` with image metadata

#### 2. Generate Preview Image

```bash
sudo python3 cavicapture.py --config config.ini --preview
```

**Output:**
- Single `preview.png` image for testing focus and lighting

#### 3. Process Captured Images

```bash
python3 caviprocess.py --config config.ini
```

**Output:**
- Processed images in `{output_dir}/{sequence_name}/processed/`
- Database updated with difference calculations
- Log file: `{sequence_name}/processed/log.txt`

#### 4. Reprocess All Images (Recalculate Areas)

```bash
python3 caviprocess.py --config config.ini --reprocess
```

Useful when you change filter settings and want to recalculate.

#### 5. Calculate Only ROI Areas

```bash
python3 caviprocess.py --config config.ini --roiareas
```

Recalculate difference areas for a specific region only.

#### 6. System Calibration

```bash
python3 calibrate.py --config config.ini
```

**Output:**
- Calibration images and noise analysis histograms
- Helps determine optimal `filter_threshold` value
- Creates `./calibration/` folder with results

#### 7. Convert External Image Sequences

```bash
python3 seq_converter.py \
  --config config.ini \
  --input_dir ./existing_images/ \
  --output_dir ./converted_output/ \
  --sequence_name my_sequence \
  --file_mask "*.png"
```

---

## 🔍 Understanding the Processing Pipeline

When `caviprocess.py` runs, it processes images in **sequential pairs** using a 6-step pipeline:

### Step 1: Convert to 8-bit Grayscale
```
Input: Original RGB images
Output: Grayscale values 0 (black) to 255 (white)
```

### Step 2: Calculate Difference
```
For each pixel position (x, y):
  difference = pixel_image2(x,y) - pixel_image1(x,y)
Result: New image showing pixel-level changes
```

### Step 3: Filter Noise
```
Remove small differences below threshold (default: 7)
image[image < 7] = 0
Result: Isolated noise removed
```

### Step 4: Remove Outliers
```
Apply median filter at 3-pixel radius
Removes single-pixel noise artifacts
Result: Cleaner difference map
```

### Step 5: Apply Threshold
```
Set all remaining non-zero pixels to 255 (white)
Result: Binary image (black = no change, white = change)
```

### Step 6: Count Differences
```
Total Area = number of white pixels
Result: Quantitative measure of change between image pair
```

---

## 📊 Data Analysis

### SQLite Database Structure

The `capture.db` file contains a `captures` table:

```sql
CREATE TABLE captures (
  id INTEGER PRIMARY KEY,
  filename CHAR(50),
  timestamp CHAR(50),
  skip INT,
  processed INT,
  processing INT,
  area REAL
)
```

**Columns:**
- `id`: Unique image identifier
- `filename`: PNG filename
- `timestamp`: Capture time (YYYYMMDD-HHMMSS)
- `skip`: Whether to skip this image (0=no, 1=yes)
- `processed`: Processing complete (0=no, 1=yes)
- `processing`: Currently being processed (0=no, 1=yes)
- `area`: Difference pixel count from previous image

### Querying Results

```bash
sqlite3 /path/to/capture.db "SELECT * FROM captures LIMIT 10;"
```

Or use [SQLiteBrowser](https://sqlitebrowser.org/) for GUI analysis.

---

## 🐛 Troubleshooting

### Camera Not Found

**Error:** library import or hardware initialisation failure (e.g. `ModuleNotFoundError: picamera` or libcamera errors)

**Solution:**
1. Make sure the camera ribbon is seated properly and the cable is placed in the correct orientation.
2. On recent Raspberry Pi OS releases the legacy camera stack is disabled; you must use the libcamera drivers.
   ```bash
   sudo raspi-config
   # Navigate to: Interface Options > Legacy Camera  > Disable (if enabled)
   # Then enable "Camera" under Interface Options (uses libcamera)
   ```
3. Reboot: `sudo reboot`
4. Verify the camera with libcamera:
   ```bash
  # On Bookworm the tools may be named `rpicam-hello` / `rpicam-jpeg`.
  # Try rpicam first, otherwise fall back to libcamera commands:
  rpicam-hello || libcamera-hello --width 3280 --height 2464
  rpicam-jpeg -o test.jpg || libcamera-still -o test.jpg
   ```
5. If you see preview/ capture works, then picamera2 should be able to access the device.
6. If problems persist, install `python3-picamera2` and retry the import:
   ```bash
   python3 -c "from picamera2 import Picamera2; Picamera2()"
   ```

> The old `raspistill` tool is part of the legacy stack and may not work on 64‑bit OS.

### GPIO Permission Denied

**Error:** `RuntimeError: No access to /dev/mem`

**Solution:** Run script with `sudo`:
```bash
sudo python3 cavicapture.py --config my_config.ini
```

### "Config file not found"

**Error:** `FileNotFoundError: [Errno 2] No such file or directory`

**Solution:** Ensure the `config.ini` exists in your active directory and is spelled correctly in `--config`. Or explicitly refer to a local path:
```bash
sudo python3 cavicapture.py --config ./config.ini
```

### Low Quality/Dark Images

**Solution:** Adjust camera settings in config:
- Increase `ISO` (e.g., 100 → 400)
- Increase `shutter_speed` (e.g., 1500 → 6000)
- Check physical LED light is on and functional
- Clean camera lens

### OpenCV Import Error

**Error:** `ModuleNotFoundError: No module named 'cv2'`

**Solution:** Install OpenCV:
```bash
pip install opencv-python-headless
# OR
sudo apt-get install python3-opencv
```

### Database Locked

**Error:** `sqlite3.OperationalError: database is locked`

**Solution:** This is normal when capture and processing run simultaneously. The script will retry automatically.

### Slow Image Processing

**Solution:**
- Reduce image resolution in config (`resolution=Small`)
- Disable intermediates (`intermediates_enabled=Off`)
- Increase filter threshold to process fewer pixels
- Run processing on separate Raspberry Pi

---

## 📚 Additional Resources

- **Original Repository:** [bsf2608/cavicapture](https://github.com/bsf2608/cavicapture)
- **Raspberry Pi Setup:** [OpenSourceOV/raspberry-pi-setup](https://github.com/OpenSourceOV/raspberry-pi-setup)
- **GUI Interface:** [OpenSourceOV/caviconsole](https://github.com/OpenSourceOV/caviconsole)
- **SQLite Browser:** [sqlitebrowser.org](https://sqlitebrowser.org/)

---

## 💡 Tips & Best Practices

1. **Always test with preview first:** Run `--preview` before starting long captures
2. **System packages:** It is recommended to use `apt-get` for dependencies on modern Raspberry Pi OS to avoid issues
3. **Monitor disk space:** Large image sequences consume significant storage
4. **Keep verbose logging on:** Helps troubleshoot issues later
5. **Save calibration results:** Document your filter_threshold findings
6. **Run processing in parallel:** While capturing, process in another terminal
7. **Back up your database:** SQLite files are critical - keep backups
8. **Document your settings:** Save successful config files for reproducibility

---

## 📄 License

See [LICENSE](LICENSE) file for license information.

---

## ✨ Updates in This Version

- **Python 3 Compatibility:** Converted from Python 2 to Python 3
- **Enhanced Documentation:** Comprehensive guides for first-time users
- **Fixed Imports:** Updated `ConfigParser` to `configparser`
- **Modern Code:** Print statements use proper Python 3 syntax
- **Better Error Messages:** More descriptive logging and error handling

---

**Last Updated:** March 7, 2026
**Version:** 2.0 (Python 3)
