from .devices import MyDevice


class MyFilter(MyDevice):
    def __init__(self, name, serial, enabled = True):
        super().__init__(name, serial, "ThorFilter", None, enabled)
