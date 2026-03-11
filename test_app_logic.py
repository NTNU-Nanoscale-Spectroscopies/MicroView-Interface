import sys
sys.path.append(r'C:/Users/el-ei/Documents/Masterproject/Code/MicroView-Interface')
from dev.application import MyApp
from dev.devices.power_meter.power_meter import MyPowerMeter
from customtkinter import CTkButton

class DummyMic:
    def __init__(self, devices):
        self.devices = devices
        self.name = 'dummy'

pm = MyPowerMeter('PM','123')
mic = DummyMic([pm])
# create minimal application object (no microscope passed to constructor)
app = MyApp('v',(100,100),3,'backup')
# assign dummy button so update_spec_pwr_toggle_state can operate
app.spec_power_toggle_button = CTkButton(app, text='test')
app.selected_microscope = mic
print('initial button state', app.spec_power_toggle_button['state'])
print('meters', app.find_devices_by_type(mic, MyPowerMeter))
print('connected?', [m.connected for m in app.find_devices_by_type(mic, MyPowerMeter)])
# simulate connection
pm.connected = True
app.update_spec_pwr_toggle_state()
print('button state after connect', app.spec_power_toggle_button['state'])
# simulate disconnection
pm.connected = False
app.update_spec_pwr_toggle_state()
print('button state after disconnect', app.spec_power_toggle_button['state'])
