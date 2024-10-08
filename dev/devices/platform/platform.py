from dev.devices.devices import MyDevice


class MyPlatform(MyDevice):
    def __init__(self, name, serial, enabled = True):
        super().__init__(name, serial, "ThorPlatform", "edtiable", enabled)
