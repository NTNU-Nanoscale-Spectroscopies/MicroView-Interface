from dev.devices.devices import MyDevice


class MyWhiteLight(MyDevice):
    def __init__(self, name, serial, enabled = False):
        super().__init__(name, serial, "ThorWhiteLight", None, enabled)
