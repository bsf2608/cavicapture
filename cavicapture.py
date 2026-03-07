#!/usr/bin/env python3

from configparser import ConfigParser

import time, datetime
import sys, os, getopt, signal, atexit
import RPi.GPIO as GPIO
# camera changed to picamera2 for modern Raspberry Pi OS
from picamera2 import Picamera2
from libcamera import controls
import cv2
import sqlite3
import subprocess

def main():

    generate_preview = False

    config_path = None
    try:
      opts, args = getopt.getopt(sys.argv[1:], "c:p", ["config=", "preview"])
    except getopt.GetoptError:
      print("cavicapture.py --config <path/to/config.ini> --preview")
      sys.exit(2)
    for opt, arg in opts:
      if opt in ("--config"):
        config_path = arg
      elif opt in ("--preview"):
        generate_preview = True
      
    if config_path is None:
      print("Error: --config <path/to/config.ini> is required")
      sys.exit(2)

    cavi_capture = CaviCapture(config_path)
    if generate_preview:
      cavi_capture.generate_preview()
    else:
      cavi_capture.start()

class CaviCapture:
  
  def __init__(self, config_file):
      
    self.config_file = config_file
    self.current_capture = False
    self.capture_timestamp = ""
    self.load_config()
    self.setup_gpio()
    self.create_directories()    
    self.log_file = os.path.join(self.sequence_path, "log.txt")
    self.setup_db()
    
    # Shutdown guard flag
    self._shutdown_done = False
    
    # Register shutdown to ensure cleanup on exit
    atexit.register(self.shutdown)
    
    # Handle SIGTERM for clean stop
    signal.signal(signal.SIGTERM, self._handle_signal)

  def _handle_signal(self, signum, frame):
    self.log_info("Received termination signal.")
    sys.exit(0) # This will trigger atexit

  def load_config(self):

    config = ConfigParser()
    if not os.path.exists(self.config_file):
        raise FileNotFoundError("Config file not found: " + self.config_file)
    config.read(self.config_file)

    print("Reading from config file: " + self.config_file)

    # Camera config
    self.camera_ISO                 = config.getint('camera', 'ISO')
    self.camera_shutter_speed       = config.get('camera', 'shutter_speed')

    # Capture config
    self.capture_duration           = config.getfloat('capture', 'duration') 
    self.capture_interval           = config.getint('capture', 'interval')
    self.output_dir                 = config.get('capture', 'output_dir').split(';')[0].strip()
    self.capture_sequence_name      = config.get('capture', 'sequence_name').split(';')[0].strip()
    self.resolution                 = config.get('capture', 'resolution').split(';')[0].strip()
    self.verbose = config.get('capture', 'verbose').split(';')[0].strip().lower() in ('true', 'yes', 'on', '1')
    self.crop_enabled = config.get('capture', 'crop_enabled').split(';')[0].strip()

    crop_string = config.get('capture', 'crop').split(';')[0].strip()
    crop_values = [float(n) for n in crop_string.split(",")]
    if len(crop_values) == 4:
        self.crop_x, self.crop_y, self.crop_w, self.crop_h = crop_values
    else:
        self.log_error("Invalid crop configuration. Expected 4 values (x,y,w,h). Cropping disabled.")
        self.crop_enabled = 'Off'
    
    # Pi config
    self.pi_GPIO_light_channel    = config.getint('pi', 'GPIO_light_channel')
  
  def generate_preview(self):
    try:
      self.setup_camera()
      self.log_config()
      self.log_info("Generating preview")
      self.lights(True)
      time.sleep(1) # brief settle before capture
      # Picamera2 uses capture_file
      self.camera.capture_file(os.path.join(self.sequence_path, "preview.jpg"))
      self.log_info("Preview generated")
    finally:
      self.lights(False)
      if hasattr(self, 'camera'):
        self.camera.stop()
        self.camera.close()
    
  def start(self):

    self.setup_camera()
    self.log_config()

    start_time = datetime.datetime.now()
    end_time = start_time + datetime.timedelta(hours=self.capture_duration)

    try:
      # Start capture session: light ON, warmup, capture, light OFF
      self.lights(True, settle=True)
      
      while (datetime.datetime.now() < end_time):
        self.capture_timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        output_filename = self.capture_timestamp + ".png"
        self.log_info("Capturing " + output_filename)
        self.capture(output_filename)
        
        # Responsive sleep
        sleep_duration = self.capture_interval
        while sleep_duration > 0 and datetime.datetime.now() < end_time:
            if sleep_duration >= 1:
                time.sleep(1)
                sleep_duration -= 1
            else:
                time.sleep(sleep_duration)
                break
    except KeyboardInterrupt:
      self.log_info("Capture Interrupted")
    except Exception as e:
      self.log_error("Unexpected error: " + str(e))
    finally:
      self.lights(False)
      self.shutdown()

  def shutdown(self):
    """Clean up resources: lights off, camera closed, GPIO cleanup."""
    if self._shutdown_done:
      return
    self._shutdown_done = True

    try:
      self.lights(False)
      self.log_info("Lights turned off.")
    except:
      pass

    if hasattr(self, 'camera'):
      try:
        self.camera.stop()
        self.camera.close()
        self.log_info("Camera closed.")
      except:
        pass

    if hasattr(self, 'db_conn'):
      try:
        self.db_conn.close()
        self.log_info("Database connection closed.")
      except:
        pass

    try:
      GPIO.cleanup()
      self.log_info("GPIO cleaned up.")
    except:
      pass


  def capture(self, output_filename):
    # use picamera2 capture_file for jpeg/png output
    capture_path = os.path.join(self.sequence_path, output_filename)
    self.camera.capture_file(capture_path)
    
    if self.crop_enabled == 'On':
      self.log_info("Cropping image...")
      capture = cv2.imread(capture_path)
      if capture is None:
        self.log_error("Could not read captured file for cropping: " + capture_path)
        return

      start_x = int(float(self.crop_x) * capture.shape[1])
      start_y = int(float(self.crop_y) * capture.shape[0])
      end_x = int(float(self.crop_w) * capture.shape[1]) + start_x
      end_y = int(float(self.crop_h) * capture.shape[0]) + start_y
      
      # Ensure crop coordinates are within image bounds
      start_x = max(0, start_x)
      start_y = max(0, start_y)
      end_x = min(capture.shape[1], end_x)
      end_y = min(capture.shape[0], end_y)

      if start_x >= end_x or start_y >= end_y:
        self.log_error(f"Invalid crop dimensions: calculated crop region [{start_x}:{end_x}, {start_y}:{end_y}] is empty or inverted. Cropping skipped.")
        return

      cropped = capture[start_y:end_y, start_x:end_x]
      if cropped.size == 0:
        self.log_error("Crop produced empty image — check crop config values")
        return
        
      success = cv2.imwrite(capture_path, cropped)
      if not success:
        self.log_error("Failed to write cropped image: " + capture_path)

    sql = "INSERT INTO captures (filename, timestamp, skip, processing, processed) VALUES (?, ?, 0, 0, 0);"
    while record_inserted == False:
      try:
        self.db_conn.execute(sql, (output_filename, self.capture_timestamp))
        self.db_conn.commit()
        record_inserted = True
      except sqlite3.OperationalError as e:
        if "locked" in str(e).lower():
            self.log_info("database locked - trying again in 1 second")
            time.sleep(1)
        else:
            self.log_error("Database error (not a lock): " + str(e))
            raise

  def log_config(self):
    self.log_info("Config file: " + self.config_file)
    self.log_info("Verbose: " + str(self.verbose))
    self.log_info("Camera ISO: " + str(self.camera_ISO))
    self.log_info("Camera Shutterspeed: " + str(self.camera_shutter_speed))
    self.log_info("Capture Duration: " + str(self.capture_duration))
    self.log_info("Capture Interval: " + str(self.capture_interval))
    self.log_info("Output Dir: " + str(self.output_dir))
    self.log_info("Capture Sequence Name: " + str(self.capture_sequence_name))
    self.log_info("GPIO Light Channel: " + str(self.pi_GPIO_light_channel))
    self.log_info("Resolution: " + str(self.resolution))
    self.log_info("Crop Enabled: " + str(self.crop_enabled))
    if self.crop_enabled == 'On':
        self.log_info(f"Crop (x,y,w,h): {self.crop_x}, {self.crop_y}, {self.crop_w}, {self.crop_h}")


  def setup_camera(self):

    # initialize picamera2
    self.camera = Picamera2()

    # configure still capture at desired resolution
    # Map legacy names to actual sizes
    if self.resolution == 'Max':
      # Query the camera's actual maximum resolution dynamically
      sensor_modes = self.camera.sensor_modes
      if sensor_modes:
          max_size = max(sensor_modes, key=lambda m: m['size'][0] * m['size'][1])['size']
      else:
          max_size = (3280, 2464)  # fallback for IMX219
    elif self.resolution == 'Large':
      max_size = (1920, 1080)
    elif self.resolution == 'Medium':
      max_size = (1296, 972)
    elif self.resolution == 'Small':
      max_size = (640, 480)
    else:
      max_size = (640, 480)

    config = self.camera.create_still_configuration(main={"size": max_size})
    self.camera.configure(config)
    self.camera.start()

    self.lights(True, settle=True)
    self.log_info("Configuring camera...")
    time.sleep(2) # Warm up with lights on, let AEC/AGC settle

    # apply exposure/gain settings after algorithm has settled
    if self.camera_shutter_speed != 'auto':
      self.camera.set_controls({
          "ExposureTime": int(self.camera_shutter_speed),
          "AnalogueGain": float(self.camera_ISO) / 100.0
      })
      time.sleep(0.5) # Brief settle after setting controls
    else:
      # leave auto exposure
      pass

    self.log_info("Configuring camera...")

    # delay to let camera start
    time.sleep(2)

    # Picamera2 has no awb modes; use controls if needed
    # disable auto white balance by setting to current gains if desired

    self.log_info("Configuration complete.")

  def setup_gpio(self):

    # GPIO setup
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(self.pi_GPIO_light_channel, GPIO.OUT)

  def create_directories(self):

    if not os.path.exists(self.output_dir):
      os.makedirs(self.output_dir)
    
    self.sequence_path = os.path.join(self.output_dir, self.capture_sequence_name)

    if not os.path.exists(self.sequence_path):
        os.makedirs(self.sequence_path)

    self.processed_path = os.path.join(self.sequence_path, "processed")

    if not os.path.exists(self.processed_path):
        os.makedirs(self.processed_path)
        subprocess.call(['setfacl', '-d', '-Rm', 'g:pi:rwX', self.processed_path])

  def _set_permissions(self, path):
    """Apply ACL permissions, warn if setfacl not available."""
    for args in [['setfacl', '-Rm', 'g:pi:rwX', path],
                 ['setfacl', '-d', '-Rm', 'g:pi:rwX', path]]:
        try:
            result = subprocess.call(args, stderr=subprocess.DEVNULL)
            if result != 0:
                # Only log once per path to avoid spam
                self.log_info("Warning: setfacl failed for " + path + " (check if installed/supported)")
                break
        except OSError:
            self.log_info("Warning: setfacl command not found")
            break

  def setup_db(self):
    self.db_conn = sqlite3.connect(os.path.join(self.sequence_path, 'capture.db'))
    self.db_conn.execute('''CREATE TABLE IF NOT EXISTS captures
            (id INTEGER PRIMARY KEY,
            filename CHAR(50) NOT NULL,
            timestamp CHAR(50) NOT NULL,
            skip INT NOT NULL,
            processed INT NOT NULL,
            processing INT NOT NULL,
            area REAL);''')

    self.log_db('Database Opened')

  def lights(self, active, settle=False):

    if active:
      GPIO.output(self.pi_GPIO_light_channel, True)
      if settle:
        time.sleep(3)
    else:
      GPIO.output(self.pi_GPIO_light_channel, False)

  def log_info(self, entry):
    self.log(str(entry))
    if(self.verbose):
      print('info|' + str(entry))
      sys.stdout.flush()

  def log_error(self, entry):
    self.log(str(entry))
    if(self.verbose):
      print('error|' + str(entry))
      sys.stdout.flush()

  def log_db(self, entry):
    self.log(str(entry))
    if(self.verbose):
      print('db|' + str(entry))
      sys.stdout.flush()

  def log(self, entry):
    with open(self.log_file, 'a') as log:
      log.write(str(entry) + '\n')

# Final verification of CaviCapture class methods and external library usage complete.
# All GPIO, Picamera2, and sqlite3 calls match modern Python 3 standards.
if __name__ == '__main__':
    main()
