"""Detects third-party scripts blocking Meta Pixel execution."""
class PixelProbe:
    async def count_scripts_before_pixel(self, page) -> int:
        """Counts DOM <script> tags that load before fbq() initialization."""
        pass
