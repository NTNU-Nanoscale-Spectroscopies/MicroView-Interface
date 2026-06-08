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
app = MyApp('v',(100,100),3,'backup')
# create dummy button whose configure method logs arguments
class DummyButton(CTkButton):
    def configure(self, **kwargs):
        print('DummyButton.configure called with', kwargs)
        # call super to ensure no errors when state set
        try:
            super().configure(**kwargs)
        except Exception:
            pass

app.spec_power_toggle_button = DummyButton(app, text='test')
app.selected_microscope = mic
# now exercise state update
pm.connected=False
app.update_spec_pwr_toggle_state()
pm.connected=True
app.update_spec_pwr_toggle_state()
