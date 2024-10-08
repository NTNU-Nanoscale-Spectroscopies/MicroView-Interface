from dev.devices.devices import MyDevice


class MyLaser(MyDevice):
    def __init__(self, name, serial, enabled = False):
        super().__init__(name, serial, "ThorLaser", "info", enabled)
