from .andor_setup import configure_path


__all__ = [
    "configure_path",
    "MyKymera328i",
    "MySimKymera328i",
]


def __getattr__(name):
    if name == "MyKymera328i":
        from .kymera_328i import MyKymera328i

        return MyKymera328i

    if name == "MySimKymera328i":
        from .sim_kymera_328i import MySimKymera328i

        return MySimKymera328i

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
