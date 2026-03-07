"""Simple script to verify picamera2 works on Raspberry Pi with libcamera.

Run this on the Pi after installing python3-picamera2.
"""

from picamera2 import Picamera2
import time

picam2 = Picamera2()
config = picam2.create_still_configuration(
    main={"size": (3280, 2464)}
)
picam2.configure(config)

picam2.start()
# give the sensor some time to warm up
time.sleep(2)

picam2.capture_file("test_modern.jpg")
print("Capture complete - check test_modern.jpg")
