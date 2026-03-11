from dev.debugHelp import debugp
from .windows_setup import configure_path
from .camera_sdk.tl_camera import TLCameraSDK
from .camera_sdk.tl_camera_enums import SENSOR_TYPE
from .camera_sdk.tl_color_enums import FILTER_ARRAY_PHASE
from .camera_sdk.tl_mono_to_color_processor import MonoToColorProcessorSDK

from PIL import Image
import threading
import queue
import numpy as np
import ctypes

configure_path()

# Cache for .NET interop - avoids repeated reflection calls
_dotnet_marshal = None
_dotnet_gc_handle_type = None

def _get_dotnet_marshal():
    """Lazy-load .NET Marshal class for efficient memory copy."""
    global _dotnet_marshal
    if _dotnet_marshal is None:
        try:
            from System.Runtime.InteropServices import Marshal
            _dotnet_marshal = Marshal
        except Exception:
            _dotnet_marshal = False
    return _dotnet_marshal if _dotnet_marshal else None


class DotNetFrame:
    """Wrapper that adapts a .NET Frame object to match the ctypes SDK Frame interface."""
    
    # Class-level cache for reflection objects
    _image_data_method = None
    _gc_handle_type = None
    _gc_handle_class = None
    
    def __init__(self, dotnet_frame, width, height):
        self._dotnet_frame = dotnet_frame
        self._width = width
        self._height = height
        self._image_buffer = None
    
    @property
    def image_buffer(self):
        """Return frame data as numpy array matching the ctypes SDK Frame interface."""
        if self._image_buffer is None:
            imgdata = self._dotnet_frame.ImageData
            
            # Cache the reflection method at class level
            if DotNetFrame._image_data_method is None:
                DotNetFrame._image_data_method = imgdata.GetType().GetMethod('get_ImageData_monoOrBGR')
            
            buf = DotNetFrame._image_data_method.Invoke(imgdata, None)
            
            # Fast path: use GCHandle pinning + ctypes.memmove for efficient memory transfer
            Marshal = _get_dotnet_marshal()
            if Marshal is not None:
                try:
                    # Cache GCHandle types at class level
                    if DotNetFrame._gc_handle_class is None:
                        from System.Runtime.InteropServices import GCHandle, GCHandleType
                        DotNetFrame._gc_handle_class = GCHandle
                        DotNetFrame._gc_handle_type = GCHandleType.Pinned
                    
                    # Pin the .NET array and copy directly to numpy buffer
                    num_pixels = self._width * self._height
                    self._image_buffer = np.empty(num_pixels, dtype=np.uint16)
                    
                    # Get pointer to the .NET array
                    handle = DotNetFrame._gc_handle_class.Alloc(buf, DotNetFrame._gc_handle_type)
                    try:
                        src_ptr = handle.AddrOfPinnedObject().ToInt64()
                        # Copy directly into numpy array's buffer
                        ctypes.memmove(
                            self._image_buffer.ctypes.data,
                            src_ptr,
                            num_pixels * 2  # 2 bytes per uint16
                        )
                    finally:
                        handle.Free()
                    
                    self._image_buffer = self._image_buffer.reshape((self._height, self._width))
                except Exception as e:
                    # Fallback to slower method if fast copy fails
                    debugp("CCD", f"Fast copy failed, using slow path: {e}")
                    self._image_buffer = np.array(list(buf), dtype=np.uint16).reshape((self._height, self._width))
            else:
                # Slow fallback: convert via Python list
                self._image_buffer = np.array(list(buf), dtype=np.uint16).reshape((self._height, self._width))
        
        return self._image_buffer


class DotNetCameraWrapper:
    """Wrapper that adapts a .NET ITLCamera object to match the ctypes SDK TLCamera interface.
    
    This allows the existing ImageAcquisitionThread to work with both the ctypes SDK (Zelux)
    and the .NET SDK (legacy CCD cameras like 8051).
    """
    
    def __init__(self, dotnet_camera, dotnet_sdk):
        self._camera = dotnet_camera
        self._sdk = dotnet_sdk
        self._is_armed = False
    
    # --- Properties matching ctypes SDK interface ---
    
    @property
    def camera_sensor_type(self):
        """Return sensor type matching SENSOR_TYPE enum."""
        sensor = str(self._camera.CameraSensorType)
        if 'Bayer' in sensor:
            return SENSOR_TYPE.BAYER
        elif 'Mono' in sensor:
            return SENSOR_TYPE.MONOCHROME
        return SENSOR_TYPE.MONOCHROME
    
    @property
    def image_width_pixels(self):
        return self._camera.SensorWidth_pixels
    
    @property
    def image_height_pixels(self):
        return self._camera.SensorHeight_pixels
    
    @property
    def bit_depth(self):
        return self._camera.BitDepth
    
    @property
    def color_filter_array_phase(self):
        """Return color filter array phase for Bayer sensors, converted to Python enum."""
        try:
            dotnet_phase = self._camera.ColorFilterArrayPhase
            phase_value = int(dotnet_phase)
            # Map .NET ColorFilterArrayPhase enum values to Python FILTER_ARRAY_PHASE enum
            # .NET: BayerRed=0, BayerBlue=1, BayerGreenLeftOfRed=2, BayerGreenLeftOfBlue=3
            # Python: BAYER_RED=0, BAYER_BLUE=1, GREEN_LEFT_OF_RED=2, GREEN_LEFT_OF_BLUE=3
            return FILTER_ARRAY_PHASE(phase_value)
        except Exception:
            return FILTER_ARRAY_PHASE.GREEN_LEFT_OF_RED  # Common default
    
    @property
    def frames_per_trigger_zero_for_unlimited(self):
        return self._camera.FramesPerTrigger_zeroForUnlimited
    
    @frames_per_trigger_zero_for_unlimited.setter
    def frames_per_trigger_zero_for_unlimited(self, value):
        self._camera.FramesPerTrigger_zeroForUnlimited = int(value)
    
    @property
    def exposure_time_us(self):
        return self._camera.ExposureTime_us
    
    @exposure_time_us.setter
    def exposure_time_us(self, value):
        self._camera.ExposureTime_us = int(value)
    
    @property
    def image_poll_timeout_ms(self):
        return 0  # .NET SDK doesn't have this property
    
    @image_poll_timeout_ms.setter
    def image_poll_timeout_ms(self, value):
        pass  # .NET SDK doesn't have this property
    
    # --- Methods matching ctypes SDK interface ---
    
    def arm(self, frames=2):
        """Arm the camera for acquisition. .NET SDK Arm() takes no parameters."""
        self._camera.Arm()
        self._is_armed = True
    
    def disarm(self):
        """Disarm the camera."""
        if self._is_armed:
            self._camera.Disarm()
            self._is_armed = False
    
    def issue_software_trigger(self):
        """Issue a software trigger."""
        self._camera.IssueSoftwareTrigger()
    
    def get_pending_frame_or_null(self):
        """Get pending frame and wrap it to match ctypes SDK Frame interface."""
        frame = self._camera.GetPendingFrameOrNull()
        if frame is None:
            return None
        return DotNetFrame(frame, self.image_width_pixels, self.image_height_pixels)
    
    def get_color_correction_matrix(self):
        """Get color correction matrix for Bayer sensors, converted to Python list."""
        try:
            ccm = self._camera.GetCameraColorCorrectionMatrix()
            # Convert System.Single[] to Python list of floats
            return [float(x) for x in list(ccm)]
        except Exception:
            return None
    
    def get_default_white_balance_matrix(self):
        """Get default white balance matrix for Bayer sensors, converted to Python list."""
        try:
            wbm = self._camera.GetDefaultWhiteBalanceMatrix()
            # Convert System.Single[] to Python list of floats
            return [float(x) for x in list(wbm)]
        except Exception:
            return None
    
    def dispose(self):
        """Dispose of the camera."""
        try:
            self.disarm()
        except Exception:
            pass
        try:
            self._camera.Dispose()
        except Exception:
            pass


class DotNetSDKWrapper:
    """Wrapper for the .NET TL_SDK to match the ctypes TLCameraSDK interface."""
    
    def __init__(self, dotnet_sdk):
        self._sdk = dotnet_sdk
        self._is_sdk_open = True
    
    def discover_available_cameras(self):
        """Discover available cameras."""
        cams = self._sdk.DiscoverAvailableCameras()
        return [str(c) for c in list(cams)] if cams else []
    
    def open_camera(self, serial):
        """Open a camera and return a wrapped object."""
        cam = self._sdk.OpenCamera(str(serial))
        return DotNetCameraWrapper(cam, self._sdk)
    
    def dispose(self):
        """Dispose of the SDK."""
        self._is_sdk_open = False
        try:
            self._sdk.sdk.Dispose()
        except Exception:
            pass


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
        self.is_zelux = False
        self.auto_exposure_enabled = False
        self._auto_exposure_target = 115  # Target mean brightness (0-255 scale)
        self._auto_exposure_min_us = 40  # Minimum exposure in microseconds
        self._auto_exposure_max_us = 1_000_000  # Maximum exposure in microseconds (1000 ms)
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
        _found = False
        _ctypes_sdk_tried = False
        
        # First try the ctypes TSI SDK (modern Zelux/TSI cameras)
        try:
            ctypes_sdk = TLCameraSDK()
            _ctypes_sdk_tried = True
            try:
                camera_list = ctypes_sdk.discover_available_cameras()
            except Exception:
                camera_list = []
            
            if self.serial in (camera_list or []):
                # Found via ctypes SDK - use it (Zelux / TSI camera)
                self.sdk = ctypes_sdk
                self.camera_list = camera_list
                self.is_zelux = True
                try:
                    self.camera = self.sdk.open_camera(self.serial)
                    self.camera.frames_per_trigger_zero_for_unlimited = 0
                    try:
                        self.camera.arm(2)
                        self.camera.issue_software_trigger()
                    except Exception:
                        pass
                    self.connected = getattr(self.sdk, '_is_sdk_open', True)
                    _found = True
                    try:
                        self.software_trigger_timer.start()
                    except Exception:
                        pass
                except Exception:
                    pass
            else:
                # Camera not found in ctypes SDK - dispose it so .NET SDK can initialize
                try:
                    ctypes_sdk.dispose()
                except Exception:
                    pass
        except Exception:
            pass

        # If not found in ctypes TSI SDK, try .NET SDK (legacy CCD cameras like 8051)
        if not _found:
            try:
                from .tl_dotnet_wrapper import TL_SDK
                dotnet_sdk = TL_SDK()
                cams = dotnet_sdk.DiscoverAvailableCameras()
                camera_list = [str(c) for c in list(cams)] if cams else []
                debugp("CCD", f"DotNet SDK discovered cameras: {camera_list}")
                
                if self.serial in camera_list:
                    debugp("CCD", f"Opening camera {self.serial} via DotNet SDK")
                    dotnet_camera = dotnet_sdk.OpenCamera(self.serial)
                    # Wrap the .NET camera to match ctypes SDK interface
                    self.camera = DotNetCameraWrapper(dotnet_camera, dotnet_sdk)
                    self.sdk = DotNetSDKWrapper(dotnet_sdk)
                    
                    self.camera.frames_per_trigger_zero_for_unlimited = 0
                    try:
                        self.camera.arm(2)
                        self.camera.issue_software_trigger()
                    except Exception as e:
                        debugp("CCD", f"Initial trigger failed (expected): {e}")
                    
                    self.connected = True
                    _found = True
                    
                    self.connected = True
                    _found = True
                    try:
                        self.software_trigger_timer.start()
                    except Exception:
                        pass
                    debugp("CCD", f"Camera {self.serial} connected successfully via DotNet SDK")
            except Exception as e:
                debugp("CCD", f"DotNet SDK connection failed: {e}")
                import traceback
                traceback.print_exc()

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

    def set_auto_exposure(self, enabled):
        """Enable or disable software auto-exposure.

        Parameters
        ------------
        enabled : `bool`
            Whether auto-exposure should be active
        """
        self.auto_exposure_enabled = enabled
        if enabled:
            debugp("Camera", "Auto-exposure enabled")
        else:
            debugp("Camera", "Auto-exposure disabled")

    def auto_adjust_exposure(self, pil_image):
        """Analyse the current frame brightness and adjust exposure time.

        Uses a simple proportional controller to steer the mean brightness
        towards `_auto_exposure_target`.  Only adjusts when the camera is
        connected, running, and the initial software-trigger timer has elapsed.

        Parameters
        ------------
        pil_image : `PIL.Image`
            The most recent frame from the camera
        """
        if not (self.auto_exposure_enabled and self.connected and self.is_running and self.sftt_timer):
            return

        try:
            grey = pil_image.convert("L")
            mean_brightness = np.mean(np.array(grey))

            if mean_brightness < 1:
                mean_brightness = 1  # avoid division by zero

            current_us = self.camera.exposure_time_us
            ratio = self._auto_exposure_target / mean_brightness

            # Only adjust if brightness is more than 10 % off target
            if 0.90 < ratio < 1.10:
                return

            # Smooth the adjustment to prevent oscillation
            adjustment = 1 + (ratio - 1) * 0.5
            new_us = int(current_us * adjustment)

            # Clamp to valid range
            new_us = max(self._auto_exposure_min_us, min(new_us, self._auto_exposure_max_us))

            if new_us != current_us:
                self.camera.exposure_time_us = new_us
                debugp("Camera", f"Auto-exposure: brightness={mean_brightness:.1f}, "
                       f"{current_us} -> {new_us} us")
        except Exception as e:
            debugp("Camera", f"Auto-exposure adjustment error: {e}")

    def software_trigger_timer_done(self):
            self.sftt_timer = True
            print("SFTTTimer Done")
            
    def isPluggedIn(self):
        # Prefer ctypes TSI discovery, fall back to .NET SDK discovery
        try:
            sdk = TLCameraSDK()
            try:
                camera_list = sdk.discover_available_cameras()
            except Exception:
                camera_list = []
            if self.serial in (camera_list or []):
                try:
                    sdk.dispose()
                except Exception:
                    pass
                return True
            # Dispose ctypes SDK before trying .NET SDK
            try:
                sdk.dispose()
            except Exception:
                pass
        except Exception:
            pass

        try:
            from .tl_dotnet_wrapper import TL_SDK
            dotnet_sdk = TL_SDK()
            cams = dotnet_sdk.DiscoverAvailableCameras()
            camera_list = [str(c) for c in list(cams)] if cams else []
            found = self.serial in camera_list
            try:
                dotnet_sdk.sdk.Dispose()
            except Exception:
                pass
            return found
        except Exception:
            return False

    def __repr__(self):
        return f"{self.name}, serial : {self.serial}"



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
        import time
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
                else:
                    # No frame available - sleep briefly to reduce CPU usage
                    time.sleep(0.001)
                    
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