import sys
sys.path.append(r'C:/Users/el-ei/Documents/Masterproject/Code/MicroView-Interface')
from dev.devices.power_meter.power_meter import MyPowerMeter
pm = MyPowerMeter('test','pm')
print('available?', pm.is_available())
print('connect:', pm.connect())
print('connected flag:', pm.connected)
pm.disconnect()
print('after disconnect', pm.connected)
