from dev.devices.devices import MyDevice

try:
    from .windows_setup import configure_path
    configure_path()
except ImportError:
    configure_path = None
from dev.devices.camera.camera_sdk.tl_camera import TLCameraSDK, TLCamera, Frame
from dev.devices.camera.camera_sdk.tl_camera_enums import SENSOR_TYPE
from dev.devices.camera.camera_sdk.tl_mono_to_color_processor import MonoToColorProcessorSDK

from PIL import Image, ImageTk
import threading
import queue


class MyCamera(MyDevice):
    def __init__(self, name, serial, enabled = True):
        super().__init__(name, serial, "ThorCam", "edtiable", enabled)
        self.image_acquisition_thread = None

    def connection(self):
        try:
            self.sdk = TLCameraSDK()
            self.camera_list = self.sdk.discover_available_cameras()
            if self.serial in self.camera_list:
                self.camera = self.sdk.open_camera(self.serial)
                self.connected = self.sdk._is_sdk_open
            else:
                self.connected = False
        except Exception as e:
            print(f"Unable to connect to device “{self.name}”, serial : “{self.serial}”. {e}")
            self.connected = False
        return self.connected
    

    def run(self):
        if not self.image_acquisition_thread:
            self.camera.frames_per_trigger_zero_for_unlimited = 0
            self.camera.arm(2)
            self.camera.issue_software_trigger()
            self.image_acquisition_thread = ImageAcquisitionThread(self.camera)
            self.image_acquisition_thread.start()
        return self.image_acquisition_thread.get_output_queue()

    def stop(self):
        if self.image_acquisition_thread:
            self.image_acquisition_thread.stop()
            self.image_acquisition_thread.join()
            self.image_acquisition_thread = None


class ImageAcquisitionThread(threading.Thread):

    def __init__(self, camera):
        super(ImageAcquisitionThread, self).__init__()
        self._camera = camera
        self._previous_timestamp = 0

        if self._camera.camera_sensor_type != SENSOR_TYPE.BAYER:
            self._is_color = False
        else:
            self._mono_to_color_sdk = MonoToColorProcessorSDK()
            self._image_width = self._camera.image_width_pixels
            self._image_height = self._camera.image_height_pixels
            self._mono_to_color_processor = self._mono_to_color_sdk.create_mono_to_color_processor(
                SENSOR_TYPE.BAYER,
                self._camera.color_filter_array_phase,
                self._camera.get_color_correction_matrix(),
                self._camera.get_default_white_balance_matrix(),
                self._camera.bit_depth
            )
            self._is_color = True

        self._bit_depth = camera.bit_depth
        self._camera.image_poll_timeout_ms = 0
        self._image_queue = queue.Queue(maxsize=2)
        self._stop_event = threading.Event()

    def get_output_queue(self):
        return self._image_queue

    def stop(self):
        self._stop_event.set()

    def _get_color_image(self, frame):
        width = frame.image_buffer.shape[1]
        height = frame.image_buffer.shape[0]
        if (width != self._image_width) or (height != self._image_height):
            self._image_width = width
            self._image_height = height
            print("Image dimension change detected, image acquisition thread was updated")
        color_image_data = self._mono_to_color_processor.transform_to_24(frame.image_buffer, self._image_width, self._image_height)
        color_image_data = color_image_data.reshape(self._image_height, self._image_width, 3)
        return Image.fromarray(color_image_data, mode='RGB')

    def _get_image(self, frame):
        scaled_image = frame.image_buffer >> (self._bit_depth - 8)
        return Image.fromarray(scaled_image)

    def run(self):
        while not self._stop_event.is_set():
            try:
                frame = self._camera.get_pending_frame_or_null()
                if frame is not None:
                    if self._is_color:
                        pil_image = self._get_color_image(frame)
                    else:
                        pil_image = self._get_image(frame)
                    self._image_queue.put_nowait(pil_image)
            except queue.Full:
                pass
            except Exception as error:
                print("Encountered error: {error}, image acquisition will stop.".format(error=error))
                break
        print("Image acquisition has stopped")
        if self._is_color:
            self._mono_to_color_processor.dispose()
            self._mono_to_color_sdk.dispose()

