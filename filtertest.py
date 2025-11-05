import time
import sys
import os

# Directory where the DLL and Python wrapper are located
sdk_path = os.path.abspath("dev/devices/filter/dlls/")

# Add the directory to Python path so it can find FWxC_COMMAND_LIB.py
sys.path.append(sdk_path)

# Change working directory so ctypes can find the DLL and its dependencies
os.chdir(sdk_path)



try:
    from FWxC_COMMAND_LIB import *
except OSError as ex:
    print("Library Load Warning:", ex)
    exit(1)

def connect_and_configure_filter_wheel(serial_number):
    print(f"Connecting to device with serial: {serial_number}")
    
    hdl = FWxCOpen(serial_number, 115200, 3)
    if hdl < 0:
        print(f"Failed to connect to device {serial_number}")
        return -1
    print("Connected successfully.")

    if FWxCIsOpen(serial_number) < 0:
        print("Device not open.")
    else:
        print("Device is open.")

    # Get device ID
    dev_id = []
    if FWxCGetId(hdl, dev_id) < 0:
        print("Failed to get device ID.")
    else:
        print(f"Device ID: {dev_id}")

    # Set trigger mode (0=input mode)
    if FWxCSetTriggerMode(hdl, 0) >= 0:
        print("Trigger mode set to: input mode")

    # Get trigger mode
    triggermode = [0]
    if FWxCGetTriggerMode(hdl, triggermode) >= 0:
        print(f"Trigger mode: {'input mode' if triggermode[0] == 0 else 'output mode'}")

    # Set speed mode (0=slow speed)
    if FWxCSetSpeedMode(hdl, 0) >= 0:
        print("Speed mode set to: slow speed")

    # Get speed mode
    speedmode = [0]
    if FWxCGetSpeedMode(hdl, speedmode) >= 0:
        print(f"Speed mode: {'slow speed' if speedmode[0] == 0 else 'high speed'}")

    # Set sensor mode (0=off)
    if FWxCSetSensorMode(hdl, 0) >= 0:
        print("Sensor mode set to: off")

    # Get sensor mode
    sensormode = [0]
    if FWxCGetSensorMode(hdl, sensormode) >= 0:
        print(f"Sensor mode: {'off' if sensormode[0] == 0 else 'on'}")

    # Set wheel position
    target_position = 3
    if FWxCSetPosition(hdl, target_position) >= 0:
        print(f"Position set to {target_position}")
    time.sleep(2)

    # Get current position
    position = [0]
    if FWxCGetPosition(hdl, position) >= 0:
        print(f"Current position: {position[0]}")

    # Get number of positions
    position_count = [0]
    if FWxCGetPositionCount(hdl, position_count) >= 0:
        print(f"Total positions: {position_count[0]}")

    # Save settings to device
    if FWxCSave(hdl) >= 0:
        print("Settings saved.")

    return hdl

def main():
    print("=== Thorlabs Filter Wheel Python Interface ===")

    try:
        devices = FWxCListDevices()
        print("Available devices:", devices)

        if not devices:
            print("No filter wheel devices detected.")
            return

        serial_number = devices[0][0]  # assuming the first device
        hdl = connect_and_configure_filter_wheel(serial_number)

        if hdl >= 0:
            print("Closing connection.")
            FWxCClose(hdl)

    except Exception as e:
        print("Exception occurred:", e)

    print("=== Script Finished ===")

if __name__ == "__main__":
    main()
