from PIL import Image


class Screen:
    """A page in the rotation. render() returns the frame and seconds until it changes."""
    name = "screen"

    def ready(self) -> bool:
        return True

    def render(self, now: float) -> tuple[Image.Image, float]:
        raise NotImplementedError
