from PIL import Image


class Screen:
    """A page in the rotation. render() returns the frame and seconds until it changes."""
    name = "screen"
    shows_empty = False  # True: render() has a useful "nothing to show" state (single mode keeps it)

    def ready(self) -> bool:
        return True

    def render(self, now: float) -> tuple[Image.Image, float]:
        raise NotImplementedError
