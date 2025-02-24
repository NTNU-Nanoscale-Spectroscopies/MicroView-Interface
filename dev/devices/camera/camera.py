from dev.debugHelp import debugp
from .windows_setup import configure_path
from .camera_sdk.tl_camera import TLCameraSDK
from .camera_sdk.tl_camera_enums import SENSOR_TYPE
from .camera_sdk.tl_mono_to_color_processor import MonoToColorProcessorSDK

from PIL import Image
import threading
import queue
configure_path()


class MyCamera():
    """Class for creating an object that communicates with and controls a camera-type device"""

    def __init__(self, name, serial, enable=False):
        """Create a new Camera object for easy communication with the device concerned

        Parameters
        ------------
        name : `str`
            Visible name of this device in the graphical interface
        serial : `str`
            The unique device serial number enabling communication
        enable : `bool`, optional
            Allows or prevents the device from starting once it is connected. False by default
        """
        self.name = name
        self.serial = serial
        self.enable = enable
        self.connected = False
        self.is_running = False
        self.image_acquisition_thread = None
        self.sftt_timer = False
        self.software_trigger_timer = threading.Timer(0.3,self.software_trigger_timer_done)

    def connect(self):
        """Try to establish communication with the device

        Returns
        ------------
        connect : `bool`
            Whether communication is established
        """
        self.connected = False
        self.is_running = False
        try:
            self.sdk = TLCameraSDK()
            self.camera_list = self.sdk.discover_available_cameras()
            if self.serial in self.camera_list:
                self.camera = self.sdk.open_camera(self.serial)
                self.camera.frames_per_trigger_zero_for_unlimited = 0
                self.camera.arm(2)
                self.camera.issue_software_trigger()
                self.connected = self.sdk._is_sdk_open  
                self.software_trigger_timer.start()              
        except Exception as e:
            pass
        return self.connected
    

    def run(self):
        """Starts camera data acquisition thread

        Retruns
        ------------
        run : `bool`
            Whether the thread is started
        """
        if self.connected and not self.is_running and not self.image_acquisition_thread:
            self.image_acquisition_thread = ImageAcquisitionThread(self.camera)
            self.image_acquisition_thread.start()
            debugp("Thread", "Camera thread started")
            #debugp("Thread", f"Camera thread started - {self}")
            self.is_running = True
        return self.image_acquisition_thread.get_output_queue()


    def stop(self):
        """Stops camera data acquisition thread
        """
        if self.connected and self.is_running and self.image_acquisition_thread:
            self.image_acquisition_thread.stop()
            self.image_acquisition_thread.join()
            self.image_acquisition_thread = None
            self.is_running = False


    def disconnect(self):
        """Try to cleanly terminate communication with the device
        """
        if self.connected:
            self.stop()
            self.camera.disarm()
            self.camera.dispose()
            self.sdk.dispose()
            self.connected = False
            
    def update_exposure(self, value):
        """Change the exposure in microseconds
        
            Parameters
            ------------
            value : `float`
                Visible name of this device in the graphical interface
        """
        
        if self.connected and self.is_running and self.sftt_timer:
            """The time, in microseconds (us), that charge is integrated on the image sensor.
            To convert milliseconds to microseconds, multiply the milliseconds by 1,000.
            To convert microseconds to milliseconds, divide the microseconds by 1,000.
            """
            self.camera.exposure_time_us = value * 1000
            print("Exposure time updated : ", self.camera.exposure_time_us)
        else:
            print(f"Can't update exposure time : \nCam connected:{self.connected}\nCam running:{self.is_running}\nTimer Finished{self.sftt_timer}")

    def software_trigger_timer_done(self):
            self.sftt_timer = True
            print("SFTTTimer Done")

    def __repr__(self):
        return f"{self.name}, serial : {self.serial}"



class ImageAcquisitionThread(threading.Thread):
    """Class for creating a camera data acquisition thread"""

    def __init__(self, camera):
        """Create a new thread to acquire and process camera data

        Parameters
        ------------
        camera : `MyCamera`
            Object containing all information about a camera
        """
        
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
            self._mono_to_color_processor.red_gain = 0.7
            self._mono_to_color_processor.green_gain = 1.1
            self._mono_to_color_processor.blue_gain = 1.63
            self._is_color = True

        self._bit_depth = camera.bit_depth
        self._camera.image_poll_timeout_ms = 0
        self._image_queue = queue.Queue(maxsize=1)
        #self._image_queue = queue.SimpleQueue()
        self._stop_event = threading.Event()


    def get_output_queue(self):
        """Returns the last image obtained by the camera

        Returns
        ------------
        get_output_queue : `PIL.Image`
            Returns PIL.Image object obtained by the camera
        """
        return self._image_queue


    def stop(self):
        """Stops cleanly the data acquisition thread
        """
        self._stop_event.set()


    def _get_color_image(self, frame):
        """Converts a monochrome image buffer to a color image

        Parameters
        ------------
        frame : `Frame`
            The frame containing the monochrome image buffer to be converted

        Returns
        ------------
        _get_color_image : `PIL.Image`
            Returns a PIL.Image object in RGB mode representing the converted color image
        """
        width = frame.image_buffer.shape[1]
        height = frame.image_buffer.shape[0]
        if (width != self._image_width) or (height != self._image_height):
            self._image_width = width
            self._image_height = height
        color_image_data = self._mono_to_color_processor.transform_to_24(frame.image_buffer, self._image_width, self._image_height)
        color_image_data = color_image_data.reshape(self._image_height, self._image_width, 3)
        return Image.fromarray(color_image_data, mode='RGB')


    def _get_image(self, frame):
        """Converts a raw image buffer to an 8-bit grayscale image.

        Parameters
        ------------
        frame : `Frame`
            The frame containing the raw image buffer to be scaled and converted.

        Returns
        ------------
        _get_image : `PIL.Image`
            Returns a PIL.Image object in grayscale mode representing the scaled image.
        """
        scaled_image = frame.image_buffer >> (self._bit_depth - 8)
        return Image.fromarray(scaled_image)


    def run(self):
        """Starts the image acquisition loop for the camera.

        This method continuously retrieves frames from the camera, processes them into either color 
        or grayscale images, and stores them in the image queue. The loop runs until a stop event 
        is triggered or an error occurs
        """
        while not self._stop_event.is_set():
            try:
                frame = self._camera.get_pending_frame_or_null()
                if frame is not None:
                    if self._is_color:
                        pil_image = self._get_color_image(frame)
                    else:
                        pil_image = self._get_image(frame)

                    if self._image_queue.full:
                        try:
                            self._image_queue.get_nowait()
                        except queue.Empty:
                            pass

                    self._image_queue.put_nowait(pil_image)
                    
                #Test
                #frame.dispose()
                    
            except queue.Full:
                pass
            except Exception as error:
                print("Encountered error: {error}, image acquisition will stop.".format(error=error))
                break
        if self._is_color:
            self._mono_to_color_processor.dispose()
            self._mono_to_color_sdk.dispose()
    
    