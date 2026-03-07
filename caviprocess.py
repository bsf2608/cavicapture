#!/usr/bin/env python3

from configparser import ConfigParser
import sys, os, getopt
import sqlite3
import time
import datetime
import cv2
import numpy as np
import matplotlib.pyplot as plt

def main():

  force_reprocess = False
  roi_areas_only = False

  config_path = None
  try:
      opts, args = getopt.getopt(sys.argv[1:], "c:r", ["config=", "reprocess", "roiareas"])
  except getopt.GetoptError:
      print("caviprocess.py --config <path/to/config.ini> --reprocess --roiareas")
      sys.exit(2)
  for opt, arg in opts:
      if opt in ("--config"):
        config_path = arg
      elif opt in ("--reprocess"):
        force_reprocess = True
      elif opt in ("--roiareas"):
        roi_areas_only = True

  if config_path is None:
    print("Error: --config <path/to/config.ini> is required")
    sys.exit(2)

  processor = CaviProcess(config_path, force_reprocess, roi_areas_only)
  processor.init_processing()

  return

class CaviProcess:
  
  def __init__(self, config_file, force_reprocess, roi_areas_only):

    self.force_reprocess = force_reprocess
    self.roi_areas_only = roi_areas_only
    self.config_file = config_file
    self.load_config()    
    self.create_directories()
    self.create_files()
    self.open_db()

  def load_config(self):

    config = ConfigParser()
    if not os.path.exists(self.config_file):
        raise FileNotFoundError("Config file not found: " + self.config_file)
    config.read(self.config_file)

    print("Reading from config file: " + self.config_file)

    # Capture config
    self.output_dir                 = config.get('capture', 'output_dir').split(';')[0].strip()
    self.capture_sequence_name      = config.get('capture', 'sequence_name').split(';')[0].strip()
    self.capture_light_source       = config.get('capture', 'light_source').split(';')[0].strip()
    
    # Processing config
    self.intermediates_enabled      = self.safe_getboolean(config, 'process', 'intermediates_enabled')
    self.outlier_removal_enabled    = self.safe_getboolean(config, 'process', 'outlier_removal_enabled')
    self.filtering_enabled          = self.safe_getboolean(config, 'process', 'filtering_enabled')
    self.thresholding_enabled       = self.safe_getboolean(config, 'process', 'thresholding_enabled')
    self.difference_enabled         = self.safe_getboolean(config, 'process', 'difference_enabled')
    self.filter_threshold           = int(config.get('process', 'filter_threshold').split(';')[0].strip())
    self.verbose                    = self.safe_getboolean(config, 'process', 'verbose')
    self.roi_enabled                = self.safe_getboolean(config, 'process', 'roi_enabled')

    roi_concat_string = config.get('process', 'roi').split(';')[0].strip()
    self.roi = tuple([float(n) for n in roi_concat_string.split(",")])

  def safe_getboolean(self, config, section, key):
    """Read config value, strip comments, and convert to boolean."""
    val = config.get(section, key).split(';')[0].strip().lower()
    return val in ('true', 'yes', 'on', '1')


  def create_directories(self):

    self.sequence_path = os.path.join(self.output_dir, self.capture_sequence_name)
    self.process_dir = os.path.join(self.sequence_path, "processed")
    self.db_path = os.path.join(self.sequence_path, 'capture.db')
    
    self.last_processed_time = datetime.datetime.now()
    self.max_idle_seconds = 60 # Exit if no new work for 60s
    # Removed: self.captures_csv_path = os.path.join(self.sequence_path, "captures.csv")

    if not os.path.exists(self.process_dir):
      os.makedirs(self.process_dir)

  def create_files(self):
    self.log_file = os.path.join(self.process_dir, "log.txt")
    self.areas_file = os.path.join(self.process_dir, "areas.txt")

  def open_db(self):
    # Changed to use self.db_path
    if not os.path.exists(self.db_path):
      self.log_error("Exiting: can't find captures db: " + self.db_path)
      sys.exit()

    self.db_conn = sqlite3.connect(self.db_path)

  def init_processing(self):
    id, filename, timestamp, skip, processed = 0, 1, 2, 3, 4

    if self.roi_areas_only:
      self.init_area_processing()
      return # init_area_processing handles db closure

    if self.force_reprocess:
      self.db_conn.execute("UPDATE captures SET processed = 0, processing = 0")
      self.db_conn.commit()

    try: # Added try block for main processing loop
      while True:
        try:
          conn_cursor = self.db_conn.cursor()
          conn_cursor.execute("SELECT id, filename, timestamp, skip, processed FROM captures ORDER BY id ASC")
          rows = conn_cursor.fetchall()
          previous_row = None 
          any_processed_this_pass = False
          for row in rows:
            if previous_row and not row[skip] and not row[processed]:
              any_processed_this_pass = True
              self.db_conn.execute("UPDATE captures SET processing = 1 WHERE id = ?", (row[id],))
              self.db_conn.commit()
              try:
                  area = self.process(os.path.join(self.sequence_path, row[filename]), os.path.join(self.sequence_path, previous_row[filename]))
              except Exception as e:
                  self.log_error("Process failed for id {0}: {1}".format(row[id], str(e)))
                  self.db_conn.execute("UPDATE captures SET processing = 0 WHERE id = ?", (row[id],))
                  self.db_conn.commit()
                  # If this failed, we shouldn't use it as previous_row for the next one
                  continue
              
              # print "Updating record"
              self.db_conn.execute("UPDATE captures SET processed = 1, processing = 0, area = ? WHERE id = ?", (area, row[id]))
              self.db_conn.commit()
            
            if not row[skip]:
              previous_row = row
          
          if self.force_reprocess:
            # Only do reprocessing once
            self.log_info("Reprocessing complete")
            break # Exit loop after reprocessing
          
          if not any_processed_this_pass:
            idle = (datetime.datetime.now() - self.last_processed_time).total_seconds()
            if idle > self.max_idle_seconds:
                self.log_info("No new images for " + str(self.max_idle_seconds) + "s — exiting.")
                break # break to the finally block to close db
          else:
            self.last_processed_time = datetime.datetime.now()

          time.sleep(6)

        except sqlite3.OperationalError as e:
          if "locked" in str(e).lower():
            self.log_info("database locked - trying again in 1 second")
            time.sleep(1)
          else:
            self.log_error("Database error: " + str(e))
            raise
        except KeyboardInterrupt:
          self.log_info("Processing Interrupted") # Changed print to log_info
          break # Exit loop on KeyboardInterrupt
    finally: # Ensure db is closed
      self.db_conn.close()
      sys.exit()

  def init_area_processing(self):
    id, filename, timestamp, skip, processed = 0, 1, 2, 3, 4

    try: # Added try block for area processing loop
      while True:
        try:
          conn_cursor = self.db_conn.cursor()
          conn_cursor.execute("SELECT id, filename, timestamp, skip, processed FROM captures ORDER BY id ASC")
          rows = conn_cursor.fetchall()
          previous_row = None 
          for row in rows:
            if previous_row and not row[skip] and row[processed]:
              area = self.process_area(os.path.join(self.sequence_path, row[filename]))
              self.db_conn.execute("UPDATE captures SET area = ? WHERE id = ?", (area, row[id]))
              self.db_conn.commit()
            if not row[skip]:
              previous_row = row
          self.log_info("ROI areas processed")
          break # Exit loop after processing all areas
        except sqlite3.OperationalError:
          self.log_info("database locked - trying again in 1 second")
          time.sleep(1)
        except KeyboardInterrupt:
          self.log_info("Processing Interrupted") # Changed print to log_info
          break # Exit loop on KeyboardInterrupt
    finally: # Ensure db is closed
      self.db_conn.close()
      sys.exit()

  def process_area(self, file_1):
    self.log_info("Processing ROI area only")
    self.timer_start_time = datetime.datetime.now()
    self.start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    self.log_info("Start time: " + self.start_time)
    file_name = self.extract_filename(file_1)
    self.output_filename = file_name # Removed trailing semicolon

    processed_image_path = os.path.join(self.process_dir, self.output_filename + ".png") # Corrected path construction
    if not os.path.exists(processed_image_path):
      self.log_error("Processed file required for roi areas calculation: couldn't find " + processed_image_path)
      return 0
    processed_image = cv2.imread(processed_image_path, 0)
    if processed_image is None:
        self.log_error("Cannot read processed image: " + processed_image_path)
        return 0
    return self.get_roi_area_total(processed_image)
    
  
  def process(self, file_1, file_2):

    self.timer_start_time = datetime.datetime.now()
    self.start_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    self.log_info("Start time: " + self.start_time)
    
    file_1_filename = self.extract_filename(file_1)
    self.output_filename = file_1_filename # Removed trailing semicolon

    if self.intermediates_enabled:
      intermediates_path = os.path.join(self.process_dir, self.output_filename)
      if not os.path.exists(intermediates_path):
        os.makedirs(intermediates_path)

    if self.roi_areas_only:
      self.log_info("Processing ROI area only")
      processed_image_path = os.path.join(self.process_dir, self.output_filename + ".png")
      if not os.path.exists(processed_image_path):
        self.log_error("Processed file required for roi areas calculation: couldn't find " + processed_image_path)
        return 0
      processed_image = cv2.imread(processed_image_path, 0)
      return self.get_roi_area_total(processed_image)

    img_1 = cv2.imread(file_1, 0)
    if img_1 is None:
        self.log_error("Cannot read image: " + file_1)
        return 0

    if self.difference_enabled:
      img_2 = cv2.imread(file_2, 0)
      if img_2 is None:
          self.log_error("Cannot read image: " + file_2)
          return 0
      self.log_info("File 1: " + file_1)
      self.log_info("File 2: " + file_2)
    else:
      output = img_1
      self.log_info("File: " + file_1)
      self.log_info("Difference skipped")

    # Process Image Difference
    if self.difference_enabled:
      self.start_timer()
      if self.capture_light_source.strip().lower() == "above": # Made comparison case-insensitive
        output = self.subtract_images(img_1, img_2)
      else:
        output = self.subtract_images(img_2, img_1)
      
      output = self.apply_threshold(output) # Added thresholding here as per instruction
      if self.intermediates_enabled:
        self.write_image(os.path.join(intermediates_path, self.output_filename + "_difference.png"), output)
      self.log_info("Difference completed: " + str(self.stop_timer_return_seconds()) + "s (" + self.capture_light_source + " sample light source)")

    # Filter out pixels below threshold
    if self.filtering_enabled:
      self.start_timer()
      output = self.filter_pixels(output)
      if self.intermediates_enabled:
        self.write_image(os.path.join(intermediates_path, self.output_filename + "_pixels_filtered.png"), output)
      self.log_info("Filtering completed: " + str(self.stop_timer_return_seconds()) + "s")
    else:
      self.log_info("Filtering skipped")

    # Remove outliers
    if self.outlier_removal_enabled:
      self.start_timer()
      output, blurred_image = self.median_filter_using_median_blur(3, output)
      if self.intermediates_enabled:
        self.write_image(os.path.join(intermediates_path, self.output_filename + "_median_blurred.png"), blurred_image)
        self.write_image(os.path.join(intermediates_path, self.output_filename + "_outliers_removed.png"), output)
      self.log_info("Outlier removal completed: " + str(self.stop_timer_return_seconds()) + "s")
    else:
      self.log_info("Outlier removal skipped")

    # Apply threshold
    if self.thresholding_enabled:
      self.start_timer()
      output = self.apply_threshold(output) # Removed trailing semicolon
      if self.intermediates_enabled:
        self.write_image(os.path.join(intermediates_path, self.output_filename + "_thresholded.png"), output)
      self.log_info("Thresholding completed: " + str(self.stop_timer_return_seconds()) + "s")
    else:
      self.log_info("Thresholding skipped")
    
    # Final output
    self.write_image(os.path.join(self.process_dir, self.output_filename + ".png"), output)

    # Calculate the area
    if self.roi_enabled:
      area = self.get_roi_area_total(output)
      self.log_info("Embolism total ROI area: " + str(area))
    else:
      area = len(output[output>0])
      self.log_info("Embolism total area: " + str(area))
    
    return area

  def get_roi_area_total(self, image):

    img_width = int(image.shape[1])
    img_height = int(image.shape[0])

    height_rel_image_height = self.roi[0]
    width_rel_image_width = self.roi[1]
    top_rel_image_height = self.roi[2]
    left_rel_image_width = self.roi[3]

    start_x = int(left_rel_image_width * img_width)
    end_x = int(start_x + (width_rel_image_width * img_width))
    start_y = int(top_rel_image_height * img_height)
    end_y = int(start_y + (height_rel_image_height * img_height))
    roi = image[start_y:end_y, start_x:end_x].copy()
    area = len(roi[roi>0])
    return area

  def extract_filename(self, path):
    head, tail = os.path.split(path)
    filename = tail or os.path.basename(head)
    name, ext = os.path.splitext(filename)
    return name

  def apply_threshold(self, image):
    ret2,image = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)  
    return image

  def write_image(self, path, file):
    cv2.imwrite(path, file)

  def start_timer(self):
    self.timer_start_time = datetime.datetime.now()

  def stop_timer_return_seconds(self):
    return (datetime.datetime.now() - self.timer_start_time).total_seconds()

  def subtract_images(self, img_1, img_2):
    # return cv2.absdiff(img_1, img_2)
    return cv2.subtract(img_1, img_2)

  # Removed dead code: def average_images(self, file_1, file_2):
  # Removed dead code:   #read images and convert to 8 bit
  # Removed dead code:   img_1 = cv2.imread(file_1, 0)
  # Removed dead code:   img_2 = cv2.imread(file_2, 0)
  # Removed dead code:   return cv2.addWeighted(img_1, 0.5, img_2, 0.5, 0)

  def filter_pixels(self, image):
    result = image.copy()
    result[result < self.filter_threshold] = 0
    return result

  def median_filter_using_median_blur(self, radius, image):
    median_blurred_image = cv2.medianBlur(image, radius)
    return cv2.min(image, median_blurred_image), median_blurred_image

  def log(self, entry):
    with open(self.log_file, 'a') as log:
      log.write(str(entry) + '\n')

  def log_info(self, entry):
    self.log(str(entry))
    if(self.verbose):
      print('info|' + str(entry))
      sys.stdout.flush()

  def log_db(self, entry):
    self.log(str(entry))
    if(self.verbose):
      print('db|' + str(entry))
      sys.stdout.flush()
  
  def log_error(self, entry):
    self.log(str(entry))
    if(self.verbose):
      print('error|' + str(entry))
      sys.stdout.flush()

      
if __name__ == '__main__':
    main()