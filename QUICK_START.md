# Quick Start Guide - 5 Minutes to Your First Capture

For the impatient! This gets you running in 5 minutes.

## Prerequisites

- Raspberry Pi with camera enabled
- Python 3.7+ installed
- Dependencies installed

If not done yet, see [INSTALLATION.md](INSTALLATION.md)

---

## 5-Minute Quick Start

### 1. Prepare (1 minute)

```bash
cd .

# Copy example config
cp example_config.ini quick_test.ini

# Create output directory
mkdir -p ./captures
```

### 2. Test Preview (1 minute)

```bash
# Generate single test image
sudo python3 cavicapture.py --config quick_test.ini --preview
```

✅ If works: You see `preview.png` in `./captures/test_sequence/`

❌ If error: See troubleshooting section in README_NEW.md

### 3. Quick Capture (2 minutes)

Edit `quick_test.ini`:

```bash
nano quick_test.ini
```

Change these two lines:
```ini
duration=0.025              # About 1.5 minutes
interval=10                 # Every 10 seconds
```

Then run:
```bash
sudo python3 cavicapture.py --config quick_test.ini
```

Watch images capture! 📷

### 4. Process Images (1 minute)

Open **new terminal** (keep capture running):

```bash
cd .
python3 caviprocess.py --config quick_test.ini
```

Watch processing! 🔄

---

## Check Results

```bash
# List captured images
ls ./captures/test_sequence/*.png | wc -l

# View database
sqlite3 ./captures/test_sequence/capture.db "SELECT COUNT(*) as images, COUNT(CASE WHEN processed=1 THEN 1 END) as processed FROM captures;"
```

---

## Next Steps

- 📖 Read [README_NEW.md](README_NEW.md) for full documentation
- 📚 Read [USAGE.md](USAGE.md) for detailed workflows
- ⚙️ Edit config files for your specific experiment
- 🎓 Run calibration: `python3 calibrate.py --config quick_test.ini`

---

**Done!** You have working Cavicapture! 🎉
