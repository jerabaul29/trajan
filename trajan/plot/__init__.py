import logging
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)


class Plot:
    ds: xr.Dataset
    ax: plt.Axes | None = None

    # A lon-lat projection with the currently used globe.
    gcrs = None

    DEFAULT_LINE_COLOR = 'gray'

    @property
    def axes(self):
        return self.ax

    def __init__(self, ds, ax=None):
        self.ds = ds
        self.ax = ax

    def set_up_map(
        self,
        kwargs,
    ):
        """
        Set up axes for plotting.

        Args:

            crs: Use a different crs than Mercator.

            margin: margin (decimal degrees) in addition to extent of trajectories.

            land: Add land shapes based on GSHHG to map.

                'auto' (default): use automatic scaling.

                'c', 'l','i','h','f' or
                'coarse', 'low', 'intermediate', 'high', 'full': use corresponding GSHHG level.

                'mask' (fastest): use a raster mask generated from GSHHG.

                None: do not add land shapes.

        Returns:

            An matplotlib axes with a Cartopy projection.

        """
        # By popping the args from kwargs they are not passed onto matplotlib later.
        ax = kwargs.pop('ax', None)
        crs = kwargs.pop('crs', None)
        margin = kwargs.pop('margin', .1)
        corners = kwargs.pop('corners', None)
        land = kwargs.pop('land', 'auto')

        assert crs is None or ax is None, "Only one of `ax` and `crs` may be specified."

        if ax is not None:
            self.ax = ax

        # It is not possible to change the projection of existing axes. The type of axes object returned
        # by `plt.axes` depends on the input projection.
        if self.ax is not None:
            return self.ax

        if corners is None:
            lonmin = self.ds.lon.min() - margin
            lonmax = self.ds.lon.max() + margin
            latmin = self.ds.lat.min() - margin
            latmax = self.ds.lat.max() + margin
        else:
            lonmin = corners[0]
            lonmax = corners[1]
            latmin = corners[2]
            latmax = corners[3]

        crs = crs if crs is not None else ccrs.Mercator()
        self.gcrs = ccrs.PlateCarree(globe=crs.globe)

        meanlat = (latmin + latmax) / 2
        aspect_ratio = float(latmax - latmin) / (float(lonmax - lonmin))
        aspect_ratio = aspect_ratio / np.cos(np.radians(meanlat))

        # Create a new figure if none exists.
        fig = plt.gcf()
        if fig is None:
            if aspect_ratio > 1:
                fig = plt.figure(figsize=(figsize / aspect_ratio, figsize))
            else:
                fig = plt.figure(figsize=(figsize, figsize * aspect_ratio))

            # fig.canvas.draw()  # maybe needed?
            fig.set_tight_layout(True)

        self.ax = fig.add_subplot(projection=crs)
        self.ax.set_extent([lonmin, lonmax, latmin, latmax], crs=self.gcrs)

        gl = self.ax.gridlines(self.gcrs, draw_labels=True)
        gl.top_labels = None

        # TODO: Add landmask

        return self.ax

    def __call__(self, *args, **kwargs):
        return self.lines(*args, **kwargs)

    def lines(self, *args, **kwargs):
        """
        Plot the trajectory lines.

        Args:

            ax: Use existing axes, otherwise a new one is set up.

            crs: Specify crs for new axis.

        Returns:

            Matplotlib lines, and axes.
        """
        logger.debug(f'Plotting lines')
        ax = self.set_up_map(kwargs)

        if 'color' not in kwargs:
            kwargs['color'] = self.DEFAULT_LINE_COLOR

        paths = ax.plot(self.ds.lon.T,
                        self.ds.lat.T,
                        transform=self.gcrs,
                        *args,
                        **kwargs)

        return paths
