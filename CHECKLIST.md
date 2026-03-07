# Setup Verification Checklist

Use this checklist to verify your Cavicapture installation is complete and working.

## System Setup

- [ ] Raspberry Pi OS installed and updated
- [ ] Python 3.7 or newer installed (`python3 --version`)
- [ ] Git installed (`git --version`)
- [ ] Camera module enabled in raspi-config
- [ ] Camera working (`rpicam-hello` or `libcamera-hello` preview, or run `python3 test_camera.py`)


## Cavicapture Installation

- [ ] Cavicapture cloned or downloaded
- [ ] Virtual environment created (optional but recommended)
- [ ] All dependencies installed
- [ ] Dependencies verified:
  ```bash
  python3 << EOF
  import cv2, numpy, RPi.GPIO, picamera2, sqlite3, matplotlib.pyplot
  print("✓ All OK")
  EOF
  ```

## Hardware Setup

- [ ] LED light connected to Raspberry Pi GPIO
- [ ] GPIO pin number noted (default: GPIO 4)
- [ ] GPIO test successful:
  ```bash
  sudo python3 -c "
  import RPi.GPIO as GPIO
  GPIO.setmode(GPIO.BCM)
  GPIO.setup(4, GPIO.OUT)
  GPIO.output(4, True)  # Light on?
  import time; time.sleep(1)
  GPIO.output(4, False)
  GPIO.cleanup()
  print('✓ GPIO 4 works')
  "
  ```

## Configuration

- [ ] `example_config.ini` copied to `my_config.ini`
- [ ] `output_dir` points to valid directory (created if needed)
- [ ] `sequence_name` is set
- [ ] `GPIO_light_channel` matches your GPIO pin
- [ ] `camera ISO` and `shutter_speed` set appropriately
- [ ] `capture duration` and `interval` are reasonable

## Testing

- [ ] Preview image generated successfully
  ```bash
  sudo python3 cavicapture.py --config my_config.ini --preview
  ls -l ./captures/*/preview.png
  ```

- [ ] Short capture sequence (5 images, 10 sec interval) works:
  ```bash
  sudo python3 cavicapture.py --config my_config.ini
  # Wait a minute
  ls ./captures/*/*.png | wc -l  # Should be ~5
  ```

- [ ] Image processing works:
  ```bash
  python3 caviprocess.py --config my_config.ini
  # Wait 10 seconds
  sqlite3 ./captures/*/capture.db "SELECT COUNT(*) FROM captures WHERE processed=1;"
  ```

- [ ] Database contains data:
  ```bash
  sqlite3 ./captures/*/capture.db "SELECT * FROM captures LIMIT 1;"
  # Should show image data
  ```

## File Structure

Verify these files exist:

```
cavicapture/
├── cavicapture.py          ✓
├── caviprocess.py          ✓
├── calibrate.py            ✓
├── seq_converter.py        ✓
├── example_config.ini      ✓
├── README_NEW.md           ✓
├── INSTALLATION.md         ✓
├── USAGE.md                ✓
├── QUICK_START.md          ✓
└── CHECKLIST.md (this file) ✓
```

## Documentation

- [ ] Read [QUICK_START.md](QUICK_START.md) - 5-minute overview
- [ ] Read [README_NEW.md](README_NEW.md) - Complete project documentation
- [ ] Read [INSTALLATION.md](INSTALLATION.md) - Detailed setup guide
- [ ] Read [USAGE.md](USAGE.md) - Usage workflows and examples

## Advanced Features (Optional)

- [ ] Tested with image cropping enabled
- [ ] Tested with ROI processing enabled
- [ ] Tested image reprocessing with different filter settings
- [ ] Calibration tool run successfully
- [ ] Results successfully exported to CSV

## Performance Baseline

Record your system's performance:

```bash
# Number of images captured after 10 minutes
# Expected: depends on interval, but should be consistent

# Time to process 10 images
time python3 caviprocess.py --config test.ini

# Database file size
du -h ./captures/*/capture.db

# Typical values:
# - Capture rate: 1 image per 5-10 seconds
# - Processing: ~1 second per image pair
# - Storage: ~3MB per Max resolution image
```

My values:
- Capture rate: ____________ images per minute
- Process rate: ____________ images per minute
- Disk usage: ____________ GB for X images

## Troubleshooting

If anything is not working, check:

1. **Camera issues?**
   - [ ] Camera enabled: `raspi-config` → Interface → Camera
   - [ ] Camera working: `libcamera-hello` or `python3 test_camera.py`
   - [ ] Reboot: `sudo reboot`

2. **Import errors?**
   - [ ] Virtual env activated: `source cavicapture_env/bin/activate`
   - [ ] Dependencies installed: `pip list | grep opencv`
   - [ ] Reinstall: `pip install --upgrade opencv-python-headless`

3. **GPIO errors?**
   - [ ] Running with sudo: `sudo python3 cavicapture.py ...`
   - [ ] Correct GPIO pin: Check config `GPIO_light_channel`
   - [ ] Test with mock: `pip install fake-rpigpio`

4. **Configuration errors?**
   - [ ] File path exists: `ls -la {output_dir}`
   - [ ] Permissions ok: `chmod 755 {output_dir}`
   - [ ] Syntax valid: Open in text editor, check brackets

5. **Database errors?**
   - [ ] Database not corrupted: `sqlite3 db.db ".tables"`
   - [ ] Permissions ok: `chmod 666 {sequence_path}/capture.db`
   - [ ] No concurrent access issues

## System Information

Record for documentation:

```bash
# Your setup
Raspberry Pi model: ____________
OS version: ____________
Python version: ____________
OpenCV version: ____________
Camera model: ____________
GPIO light pin: ____________
```

To collect:
```bash
cat /proc/device-tree/model  # Pi model
cat /etc/os-release          # OS version
python3 --version            # Python version
python3 -c "import cv2; print(cv2.__version__)"  # OpenCV
grep "Module" /proc/devicetree/aliases  # Camera
```

---

## Ready to Use!

If all checkboxes are checked, you're ready to start real experiments! 🚀

**Next:** Follow workflows in [USAGE.md](USAGE.md)

---

**Notes for future reference:**

_Empty space for your own notes and modifications_

```
________________________
________________________
________________________
________________________
________________________
```
