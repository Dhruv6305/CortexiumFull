import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
SAMPLE_VIDEOS_DIR = os.path.join(DATA_DIR, 'sample_videos')

KNOWN_CAR_HEIGHT = 1.5
FOCAL_LENGTH = 700
CONFIDENCE_THRESHOLD = 0.4
CLASSES_TO_DETECT = [2, 3, 5, 7] # 2: car, 3: motorcycle, 5: bus, 7: truck
