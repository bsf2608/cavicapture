# Cavicapture Usage Guide - Running Experiments

This guide explains how to use Cavicapture for actual image capture and analysis experiments.

## Table of Contents

1. [Understanding Your First Run](#understanding-your-first-run)
2. [Capture Workflows](#capture-workflows)
3. [Processing Workflows](#processing-workflows)
4. [Advanced Configuration](#advanced-configuration)
5. [Data Analysis](#data-analysis)
6. [Common Tasks](#common-tasks)
7. [Performance Tips](#performance-tips)

---

## Understanding Your First Run

### What Happens During Capture

When you run `cavicapture.py`:

```
1. Reads configuration file
2. Sets up camera and GPIO light
3. Creates output folders
4. Creates SQLite database (capture.db)
5. Starts capture loop:
   - Records current timestamp
   - Turns lights ON (waits 3 seconds for stabilization)
   - Captures image as PNG
   - Turns lights OFF
   - Records in database
   - Waits for interval
   - Repeats from start until duration expires
```

### What Happens During Processing

When you run `caviprocess.py`:

```
1. Reads configuration file
2. Opens the SQLite database
3. Scans database for unprocessed images
4. For each image pair:
   - Loads two consecutive images
   - Subtracts pixel values
   - Applies filtering (removes small differences)
   - Removes outlier pixels (noise)
   - Applies threshold (black/white only)
   - Counts white pixels = "area"
   - Updates database with result
5. Waits for new images, repeats
```

---

## Capture Workflows

### Workflow 1: Simple Time-Lapse Capture

**Goal:** Capture images at regular intervals for a specific duration

**Setup:**
1. Copy `example_config.ini` → `timelapse.ini`
2. Edit important settings:
   ```ini
   [capture]
   duration=5                          # 5 hours
   interval=300                        # 1 image every 5 minutes
   output_dir=./captures
   sequence_name=timelapse_20260302    # Meaningful name
   
   [camera]
   ISO=100
   shutter_speed=1500
   
   [pi]
   GPIO_light_channel=4                # Your LED GPIO
   ```

**Run:**
```bash
sudo python3 cavicapture.py --config timelapse.ini
```

**View results:**
```bash
ls -la ./captures/timelapse_20260302/
file ./captures/timelapse_20260302/*.png
```

### Workflow 2: Capture with Cropping

**Goal:** Crop images to specific region-of-interest (ROI)

**Why:** Reduces file size, speeds up processing

**Setup:**
```ini
[capture]
crop_enabled=On
crop=0.17,0.26,0.45,0.49    # x1,y1,x2,y2 as % of image
                              # Example: 17% from left, 26% from top
                              # Captures 45-17=28% width, 49-26=23% height
```

**Find your ROI:**
1. Capture a preview: `python3 cavicapture.py --config test.ini --preview`
2. Open preview.png in image editor
3. Identify region of interest
4. Calculate percentages:
   - Left edge pixels / image width = x1
   - Top edge pixels / image height = y1
   - (Right edge pixels / image width) = x2
   - (Bottom edge pixels / image height) = y2

**Example calculation:**
- Image: 3280 × 2464 pixels
- Your ROI: starts at x=450, y=500, ends at x=1170, y=950
- Percentages: 450/3280=0.14, 500/2464=0.20, 1170/3280=0.36, 950/2464=0.39
- Config: `crop=0.17,0.26,0.45,0.49`

### Workflow 3: Quick Test Capture

**Goal:** Test setup with minimal time/storage

**Setup:**
```ini
[capture]
duration=0.025              # ~1.5 minutes
interval=10                 # 10 seconds between images
resolution=Small            # 640×480 = fast
```

**Run:**
```bash
sudo python3 cavicapture.py --config test.ini
```

### Workflow 4: High-Resolution Continuous Capture

**Goal:** Capture high-quality images continuously

**Setup:**
```ini
[capture]
duration=24                 # 24 hours
interval=5                  # Every 5 seconds
resolution=Max              # 3280×2464 (largest)

[camera]
ISO=100
shutter_speed=auto         # Let camera auto-adjust
```

⚠️ **Storage:** 
- Max resolution Every 5 seconds = ~500 images/hour
- 24 hours = ~12,000 images × ~3MB each = **36GB storage required!**

---

## Processing Workflows

### Workflow 1: Real-time Processing (Capture + Process Simultaneously)

**Best for:** Long experiments, monitor results as they occur

**Terminal 1 - Start Capture:**
```bash
cd .
source cavicapture_env/bin/activate  # If using venv
sudo python3 cavicapture.py --config my_config.ini
```

**Terminal 2 - Start Processing (in parallel):**
```bash
cd .
source cavicapture_env/bin/activate  # If using venv
python3 caviprocess.py --config my_config.ini
```

Both run simultaneously:
- Capture writes images continuously
- Processing analyzes them as they appear
- Results appear in database in real-time

**Check progress:**
```bash
# In Terminal 3:
sqlite3 ./captures/experiment_001/capture.db "SELECT COUNT(*) as captured, SUM(CASE WHEN processed=1 THEN 1 ELSE 0 END) as processed FROM captures;"
```

**Expected output:**
```
captured|processed
50|45
```

### Workflow 2: Capture First, Process Later

**Best for:** When you need to prioritize capture speed

**Step 1: Capture only**
```bash
# Edit config: set any process settings to Off
[process]
difference_enabled=Off

# Run
sudo python3 cavicapture.py --config my_config.ini
```

**Step 2: Process when convenient**
```bash
# Enable processing in config
[process]
difference_enabled=On
filter_threshold=7

# Run processing
python3 caviprocess.py --config my_config.ini
```

### Workflow 3: Reprocess with Different Settings

**Goal:** Change filter settings and reprocess all images

**Scenario:** Original filter_threshold=7 is too strict, want to try 5

**Setup:**
```ini
[process]
filter_threshold=5          # New threshold
```

**Run:**
```bash
python3 caviprocess.py --config my_config.ini --reprocess
```

This re-analyzes **all** images with the new settings.

⚠️ **Warning:** The `--reprocess` flag will:
- Recalculate all image differences
- Update the `area` column in database
- Takes time proportional to number of images

### Workflow 4: Process Only Region-of-Interest

**Goal:** Calculate difference areas only for a specific region

**Setup:**
```ini
[process]
roi_enabled=On
roi=0.17,0.26,0.45,0.49    # Your ROI coordinates
```

**Run:**
```bash
python3 caviprocess.py --config my_config.ini --roiareas
```

This calculates area only within the ROI rectangle.

---

## Advanced Configuration

### Camera Settings for Different Light Conditions

#### Bright Lab Lighting
```ini
[camera]
ISO=100
shutter_speed=500           # Fast shutter (less light exposed)
```

#### Dim Lighting
```ini
[camera]
ISO=400
shutter_speed=6000          # Slow shutter (more light exposed)
```

#### Auto Exposure (Not Recommended for Time-Lapse)
```ini
[camera]
shutter_speed=auto          # Let camera decide
```

### Processing Pipeline Control

#### Aggressive Noise Removal
```ini
[process]
filter_threshold=15         # Remove more noise
outlier_removal_enabled=On
filtering_enabled=On
```

#### Sensitive Detection (Catch Small Changes)
```ini
[process]
filter_threshold=3          # Keep small differences
outlier_removal_enabled=Off
filtering_enabled=On
```

#### Maximum Speed (Skip Processing)
```ini
[process]
difference_enabled=Off      # Don't process
```

### Debug Mode - Save All Processing Stages

Very useful for understanding why results don't match expectations:

```ini
[process]
intermediates_enabled=On    # Save every stage
verbose=On                  # Log everything
```

This creates subfolder with images at each stage:
```
captures/sequence_name/processed/
├── 20260302-120540/
│   ├── 20260302-120540_difference.png       (Step 2)
│   ├── 20260302-120540_pixels_filtered.png  (Step 3)
│   ├── 20260302-120540_outliers_removed.png (Step 4)
│   ├── 20260302-120540_thresholded.png      (Step 5)
│   └── 20260302-120540.png                  (Final result)
├── 20260302-120550/
│   └── ...
```

**Analysis with ImageJ:**
Open any intermediate image in [ImageJ](https://imagej.net/):
- Use **Image → Adjust → Threshold** to see pixel value distributions
- Use **Color → Show LUT** to visualize pixel intensity
- Helps determine optimal `filter_threshold`

---

## Data Analysis

### Quick Database Query

View all results:
```bash
sqlite3 ./captures/experiment_001/capture.db << EOF
.headers on
.mode column
SELECT id, filename, timestamp, area FROM captures LIMIT 20;
EOF
```

Output:
```
id  filename                  timestamp           area
1   20260302-120530.png       20260302-120530     0
2   20260302-120540.png       20260302-120540     15234
3   20260302-120550.png       20260302-120550     14567
```

### Export to CSV

```bash
sqlite3 ./captures/experiment_001/capture.db << EOF
.mode csv
.output results.csv
SELECT timestamp, area FROM captures WHERE area > 0 ORDER BY id;
EOF

cat results.csv
```

### Statistical Analysis

```bash
sqlite3 ./captures/experiment_001/capture.db << EOF
SELECT 
  COUNT(*) as total_images,
  COUNT(CASE WHEN area > 0 THEN 1 END) as with_changes,
  ROUND(AVG(area),2) as avg_area,
  MIN(area) as min_area,
  MAX(area) as max_area
FROM captures 
WHERE processed = 1;
EOF
```

### Export with Python for Analysis

```python
import sqlite3
import pandas as pd

# Load data
conn = sqlite3.connect('./captures/experiment_001/capture.db')
df = pd.read_sql_query(
    "SELECT timestamp, area FROM captures WHERE processed=1", 
    conn
)

# Analysis
print(f"Total images: {len(df)}")
print(f"Mean area: {df['area'].mean():.2f}")
print(f"Std dev: {df['area'].std():.2f}")

# Save to Excel
df.to_excel('experiment_analysis.xlsx', index=False)
```

---

## Common Tasks

### Task 1: Create Multiple Sequences

Create different experiments with different settings:

```bash
# Experiment 1: Normal conditions
cp example_config.ini exp1_normal.ini
nano exp1_normal.ini
# Change: sequence_name=exp1_normal

# Experiment 2: High ISO (dark conditions)
cp example_config.ini exp2_dark.ini
nano exp2_dark.ini
# Change: sequence_name=exp2_dark, ISO=400

# Experiment 3: With cropping
cp example_config.ini exp3_cropped.ini
nano exp3_cropped.ini
# Change: sequence_name=exp3_cropped, crop_enabled=On
```

### Task 2: Schedule Automated Captures (Cron)

Run captures on a schedule:

```bash
# Edit crontab
crontab -e

# Add this line to run capture daily at 8 AM:
0 8 * * * cd . && sudo python3 cavicapture.py --config daily.ini >> /var/log/cavicapture.log 2>&1
```

### Task 3: Monitor Capture Progress

```bash
# Watch in real-time
watch -n 5 'sqlite3 ./captures/*/capture.db "SELECT COUNT(*) as images FROM captures; SELECT COUNT(*) as processed FROM captures WHERE processed=1;"'
```

### Task 4: Convert External Images

If you have images from another source:

```bash
python3 seq_converter.py \
  --config example_config.ini \
  --input_dir /path/to/old/images \
  --output_dir ./captures \
  --sequence_name old_experiment \
  --file_mask "*.jpg"
```

### Task 5: Backup Results

```bash
# Backup database
cp ./captures/experiment_001/capture.db ./captures/experiment_001/capture.db.backup

# Backup all processed images
tar -czf experiment_001_backup.tar.gz ./captures/experiment_001/

# Transfer to external storage
scp -r ./captures/experiment_001 user@external_computer:/backups/
```

---

## Performance Tips

### Speed Up Capture

- Use **Small resolution:** ~640×480 (instead of 3280×2464)
- Disable crop: `crop_enabled=Off`
- Reduce exposure time: `shutter_speed=500`

**Result:** Can capture every 2 seconds (instead of 5+)

### Speed Up Processing

- Enable ROI: `roi_enabled=On` (only count ROI area)
- Increase filter threshold: `filter_threshold=15` (fewer pixels to process)
- Disable intermediates: `intermediates_enabled=Off`
- Reduce image resolution

### Reduce Storage

- Use **Small or Medium resolution**
- Enable **crop** to specific region
- Delete intermediate images after processing
- Use **image compression** (post-processing)

### Monitor System Resources

```bash
# Check disk usage
df -h

# Check RAM usage
free -h

# Check CPU usage
top -b -n 1 | head -15

# Check camera status
vcgencmd get_camera
```

---

## Troubleshooting

### Images Look Too Dark

```ini
[camera]
ISO=100          -> ISO=400         # Increase sensitivity
shutter_speed=1500 -> shutter_speed=6000  # Longer exposure
```

Or check if LED light is working (test GPIO separately).

### Images Look Too Bright

```ini
[camera]
shutter_speed=6000 -> shutter_speed=500   # Shorter exposure
```

### Processing Very Slow

Check which step is slow:
```ini
[process]
verbose=On          # See timing for each step

# If difference calculation is slow: reduce resolution
# If filtering is slow: increase filter_threshold
# If outlier removal is slow: disable it temporarily
```

### Database Getting Too Large

```bash
# Check size
du -h ./captures/experiment_001/capture.db

# Delete only unprocessed images
sqlite3 ./captures/experiment_001/capture.db "DELETE FROM captures WHERE processed=0;"
```

### Cannot Connect to Camera

```bash
# Test camera
python3 << EOF
from picamera2 import Picamera2
try:
    cam = Picamera2()
    print("✓ Camera OK")
except Exception as e:
    print(f"✗ Error: {e}")
EOF

# Or test with libcamera instead (legacy raspistill may not exist)
// Try Bookworm `rpicam` tools first (if present), otherwise use libcamera tools
rpicam-hello || libcamera-hello --width 3280 --height 2464 -t 1000
rpicam-jpeg -o test.jpg || libcamera-still -o test.jpg
```

---

## Next Steps

1. ✅ Run your first capture sequence
2. 📊 Analyze results in the database
3. 🔧 Adjust settings based on results
4. 📈 Repeat experiments with different conditions
5. 📚 Document successful configurations for reproducibility

---

**Happy experimenting!**
