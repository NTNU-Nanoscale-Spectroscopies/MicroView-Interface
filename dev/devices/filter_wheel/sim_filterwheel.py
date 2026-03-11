from .filterwheel import MyFilterWheel

class MySimFilterWheel(MyFilterWheel):
    """Simple simulator for the Thorlabs filter wheel hardware.

    It behaves like the real device but keeps all state in Python variables
    and never touches the SDK or DLL.  Useful for GUI testing when the
    physical wheel is not connected.
    """

    def __init__(self, name, serial, enable=False):
        super().__init__(name, serial, enable)
        # pre‑define a sensible number of positions for simulation (12‑slot wheel)
        self.position_count = 12
        self.current_position = 1
        # super().__init__ already loaded any saved filter names from disk; we
        # rely on inherited save_settings() to persist changes as usual.

    def connect(self):
        # simply mark the device as connected and initialise state
        self.connected = True
        # ensure we have a position count
        if self.position_count is None:
            self.position_count = 5
        if self.current_position is None:
            self.current_position = 1
        # let the GUI know it can populate itself
        self.post_connect_update()
        return True

    def disconnect(self):
        self.connected = False

    # the following methods just operate on in‑memory variables
    def get_position_count(self):
        return self.position_count

    def get_position(self):
        return self.current_position

    def set_position(self, pos):
        if not self.connected:
            return False
        if pos is None:
            return False
        if 1 <= pos <= (self.position_count or 0):
            self.current_position = pos
            return True
        return False

    def step(self, delta):
        # reuse parent logic once connected and count is known
        if not self.connected:
            return None
        # update current_position manually to bypass SDK call
        count = self.position_count
        curr = self.current_position
        new = ((curr - 1 + delta) % count) + 1
        self.current_position = new
        return new
