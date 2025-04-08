import pygdsm
import healpy as hp
import matplotlib.pyplot as plt

class SkyMapGenerator:
    def __init__(self, frequency=76):
        self.frequency = frequency
        self.gsm = pygdsm.GlobalSkyModel(freq_unit="MHz")
    
    def generate_projected_map(self):
        # Generate the Global Sky Model at the specified frequency
        sky_map = self.gsm.generate(self.frequency)
        
        # Convert from Galactic to Equatorial coordinates
        rotator = hp.Rotator(coord=["G", "C"])
        equatorial = rotator.rotate_map_pixel(sky_map)
        
        # Project the equatorial map into a 2D Cartesian grid
        projected_map = hp.cartview(
            equatorial,
            norm="hist",
            coord="C",
            flip="geo",
            title="",
            unit="Brightness",
            return_projected_map=True,
            notext=True,
        )
        plt.close()
        return projected_map
