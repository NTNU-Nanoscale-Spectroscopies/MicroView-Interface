# Compatibility shim for package import paths
# Historically the package used the lowercase module name `dev.devices.stage` while
# the actual implementation lives in the `Stage` directory. PyInstaller (and other
# importers) may require the lowercase module to exist. Re-export the real
# implementations from the `Stage` package.

try:
    from .Stage.stage import MyStage
except Exception:
    # best-effort fallback: define a minimal stub so imports don't crash hard
    class MyStage:
        def __init__(self, *args, **kwargs):
            self.name = kwargs.get('name', 'Stage') if kwargs else 'Stage'
            self.serial = kwargs.get('serial', '') if kwargs else ''
            self.connected = False
        def connect(self):
            return False
        def disconnect(self):
            pass

try:
    from .Stage.sim_stage import MySimStage
except Exception:
    pass

try:
    from .Stage.mcm301_stage import MyMCM301Stage
except Exception:
    pass

__all__ = ['MyStage', 'MySimStage', 'MyMCM301Stage']
