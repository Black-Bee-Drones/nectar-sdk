class VisionError(Exception):
    pass


class CameraError(VisionError):
    pass


class CalibrationError(VisionError):
    pass


class ProcessingError(VisionError):
    pass
