from devices.devices import MyDevice

try:
    from .windows_setup import configure_path
    configure_path()
except ImportError:
    configure_path = None
from devices.camera_sdk.tl_camera import TLCameraSDK, TLCamera, Frame
from devices.camera_sdk.tl_camera_enums import SENSOR_TYPE
from devices.camera_sdk.tl_mono_to_color_processor import MonoToColorProcessorSDK

import tkinter as tk
from PIL import Image, ImageTk
import typing
import threading
import queue


class MyCamera(MyDevice):
    def __init__(self, name, serial, enabled = True):
        super().__init__(name, serial, "ThorCam", "edtiable", enabled)

    def connection(self):
        try:
            self.sdk = TLCameraSDK()
            self.camera_list = self.sdk.discover_available_cameras()
            #self.camera = self.sdk.open_camera(self.camera_list[0])
            #print(self.camera_list)
            self.camera = self.sdk.open_camera(self.serial)
            self.connected = self.sdk._is_sdk_open
        except Exception as e:
            print(f"Erreur de connexion : {e}")
            self.connected = False
        return self.connected
    

    def run(self, canvas):
        print("Generating app...")
        #root = tk.Tk()
        #root.title(self.camera.name)
        self.image_acquisition_thread = ImageAcquisitionThread(self.camera)
        camera_widget = LiveViewCanvas(parent=canvas, image_queue=self.image_acquisition_thread.get_output_queue())

        print("Setting camera parameters...")
        self.camera.frames_per_trigger_zero_for_unlimited = 0
        self.camera.arm(2)
        self.camera.issue_software_trigger()

        print("Starting image acquisition thread...")
        self.image_acquisition_thread.start()

        print("App starting")
        #root.mainloop()

        print("Waiting for image acquisition thread to finish...")
        #image_acquisition_thread.stop()
        #image_acquisition_thread.join()

        print("Closing resources...")
        
        return camera_widget

    def stop(self):
        self.image_acquisition_thread.stop()
        self.image_acquisition_thread.join()
        print("Closing resources...")


class LiveViewCanvas(tk.Canvas):

    def __init__(self, parent, image_queue):
        self.image_queue = image_queue
        self._image_width = 0
        self._image_height = 0
        tk.Canvas.__init__(self, parent)
        self.pack()
        self._get_image()

    def _get_image(self):
        try:
            image = self.image_queue.get_nowait()
            self._image = ImageTk.PhotoImage(master=self, image=image)
            #if (self._image.width() != self._image_width) or (self._image.height() != self._image_height):
            #    self._image_width = self._image.width()
            #    self._image_height = self._image.height()
            #    self.config(width=self._image_width, height=self._image_height)
            self.create_image(0, 0, image=self._image, anchor='nw')
        except queue.Empty:
            pass
        self.after(10, self._get_image)



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
        color_image_data = self._mono_to_color_processor.transform_to_24(frame.image_buffer,
                                                                         self._image_width,
                                                                         self._image_height)
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

