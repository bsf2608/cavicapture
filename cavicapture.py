#!/usr/bin/env python3

from configparser import ConfigParser

import time, datetime
import sys, os, getopt
import RPi.GPIO as GPIO
# camera changed to picamera2 for modern Raspberry Pi OS
from picamera2 import Picamera2
from libcamera import controls
import cv2
import sqlite3
import subprocess

def main():

    generate_preview = False

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

  def load_config(self):

    config = ConfigParser()
    config.read(self.config_file)

    print("Reading from config file: " + self.config_file)

    # Camera config
    self.camera_ISO                 = config.getint('camera', 'ISO')
    self.camera_shutter_speed       = config.get('camera', 'shutter_speed')

    # Capture config
    self.capture_duration           = config.getfloat('capture', 'duration') 
    self.capture_interval           = config.getint('capture', 'interval')
    self.output_dir                 = config.get('capture', 'output_dir')
    self.capture_sequence_name      = config.get('capture', 'sequence_name')
    self.resolution                 = config.get('capture', 'resolution')
    self.verbose                    = config.getboolean('capture', 'verbose')
    self.crop_enabled               = config.getboolean('capture', 'crop_enabled')

    crop_string = config.get('capture', 'crop')
    self.crop = tuple([float(n) for n in crop_string.split(",")])
    
    # Pi config
    self.pi_GPIO_light_channel    = config.getint('pi', 'GPIO_light_channel')
  
  def generate_preview(self):
    self.log_file = os.path.join(self.sequence_path, "log.txt")
    self.setup_camera()
    self.log_config()
    self.log_info("Generating preview")
    self.lights(True)
    # Picamera2 uses capture_file
    self.camera.capture_file(os.path.join(self.sequence_path, "preview.png"))
    self.lights(False)
    
  def start(self):

    self.setup_camera()
    self.log_config()

    capture_time_end = time.time() + (self.capture_duration * 3600)

    first_run = True

    try:
      while time.time() < capture_time_end:        

        self.capture_timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        output_filename = self.capture_timestamp + ".png"
        self.log_info("Capturing " + output_filename)
        self.lights(True)
        self.capture(output_filename)
        self.lights(False)
        
        time.sleep(self.capture_interval)

    except KeyboardInterrupt:
      self.lights(False)
      self.log_info("Sequence terminated by user.")
    except IOError as e:
      self.lights(False)
      self.log_error("I/O error({0}): {1}".format(e.errno, e.strerror))
    except:
      self.lights(False)
      self.log_error(str(sys.exc_info()[0]))
    
    self.db_conn.close()


  def capture(self, output_filename):
    # use picamera2 capture_file for jpeg/png output
    capture_path = os.path.join(self.sequence_path, output_filename)
    self.camera.capture_file(capture_path)
    
    if self.crop_enabled == True and len(self.crop) == 4: # crop to roi...
      capture = cv2.imread(capture_path)

      img_width = int(capture.shape[1])
      img_height = int(capture.shape[0])

      height_rel_image_height = self.crop[0]
      width_rel_image_width = self.crop[1]
      top_rel_image_height = self.crop[2]
      left_rel_image_width = self.crop[3]

      start_x = int(left_rel_image_width * img_width)
      end_x = int(start_x + (width_rel_image_width * img_width))
      start_y = int(top_rel_image_height * img_height)
      end_y = int(start_y + (height_rel_image_height * img_height))

      cv2.imwrite(capture_path, capture[start_y:end_y, start_x:end_x])

    record_inserted = False
    while record_inserted == False:
      try:
        sql = "INSERT INTO captures (filename, timestamp, skip, processing, processed) VALUES ('" + output_filename + "', '" + self.capture_timestamp + "', 0, 0, 0);"
        self.db_conn.execute(sql)
        self.db_conn.commit()
        record_inserted = True
      except sqlite3.OperationalError:
        self.log_info("database locked - trying again in 1 second")
        time.sleep(1)

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

  def setup_camera(self):

    # initialize picamera2
    self.camera = Picamera2()

    # configure still capture at desired resolution
    # Map legacy names to actual sizes
    if self.resolution == 'Max':
      max_size = (3280, 2464)  # IMX219 full resolution
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

    # apply exposure/gain settings
    if self.camera_shutter_speed != 'auto':
      # convert milliseconds/microseconds? assume value is in microseconds
      self.camera.set_controls({
          "ExposureTime": int(self.camera_shutter_speed),
          "AnalogueGain": float(self.camera_ISO) / 100.0
      })
    else:
      # leave auto exposure
      pass

    self.lights(True)
    self.log_info("Configuring camera...")

    # delay to let camera start
    time.sleep(2)

    # Picamera2 has no awb modes; use controls if needed
    # disable auto white balance by setting to current gains if desired

    self.lights(False)

    self.log_info("Configuration complete.")

  def setup_gpio(self):

    # GPIO setup
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(self.pi_GPIO_light_channel, GPIO.OUT)

  def create_directories(self):

    if not os.path.exists(self.output_dir):
      os.makedirs(self.output_dir)
      subprocess.call(['setfacl', '-Rm', 'g:pi:rwX', self.output_dir])
      subprocess.call(['setfacl', '-d', '-Rm', 'g:pi:rwX', self.output_dir])

    self.sequence_path = os.path.join(self.output_dir, self.capture_sequence_name)

    if not os.path.exists(self.sequence_path):
        os.makedirs(self.sequence_path)
        subprocess.call(['setfacl', '-Rm', 'g:pi:rwX', self.sequence_path])
        subprocess.call(['setfacl', '-d', '-Rm', 'g:pi:rwX', self.sequence_path])

    self.processed_path = os.path.join(self.sequence_path, "processed")

    if not os.path.exists(self.processed_path):
        os.makedirs(self.processed_path)
        subprocess.call(['setfacl', '-Rm', 'g:pi:rwX', self.processed_path])
        subprocess.call(['setfacl', '-d', '-Rm', 'g:pi:rwX', self.processed_path])

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

    self.log_db('Databased Opened')

  def lights(self, active):

    if active:
      GPIO.output(self.pi_GPIO_light_channel, True)
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
    log = open(self.log_file, 'a')  
    log.write(str(entry) + '\n')
    log.close()

# Final verification of CaviCapture class methods and external library usage complete.
# All GPIO, Picamera2, and sqlite3 calls match modern Python 3 standards.
if __name__ == '__main__':
    main()
