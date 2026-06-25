try:
    from .database import Database
except ImportError:
    Database = None

try:
    from .face_detector import FaceDetector
except ImportError:
    FaceDetector = None

try:
    from .face_recognizer import FaceRecognizer
except ImportError:
    FaceRecognizer = None

try:
    from .hardware import HardwareController, SimulatedHardware
except ImportError:
    HardwareController = None
    SimulatedHardware = None
