import logging
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib import cm
import cartopy.crs as ccrs
import numpy as np
import xarray as xr
import scipy as sp

from .land import add_land

logger = logging.getLogger(__name__)
logging.getLogger('matplotlib.font_manager').disabled = True


class ColormapMapper:
    """A mapper from values to RGB colors using built in colormaps
    and scaling these."""

    def __init__(self, cmap, vmin, vmax, warn_saturated=False):
        """cmap: the matplotlib colormap to use, min: the min value to be plotted,
        max: the max value to be plotted."""
        self.vmin = vmin
        self.vmax = vmax
        self.warn_saturated = warn_saturated
        norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)
        self.normalized_colormap = cm.ScalarMappable(norm=norm, cmap=cmap)

    def get_rgb(self, val):
        """Get the RGB value associated with val given the normalized colormap
        settings."""
        if self.warn_saturated:
            if val < self.vmin:
                print("ColormapMapper warning: saturated low value")
            if val > self.vmax:
                print("ColormapMapper warning: saturated high value")

        return self.normalized_colormap.to_rgba(val)


class Plot:
    ds: xr.Dataset

    # A lon-lat projection with the currently used globe.
    gcrs = None

    DEFAULT_LINE_COLOR = 'gray'

    def __init__(self, ds):
        self.ds = ds
        self.gcrs = ccrs.PlateCarree()

    @property
    def __cartesian__(self):
        return self.ds.traj.crs is None

    def set_up_map(
        self,
        kwargs_d=None,
        **kwargs
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

                'mask' or 'fast' (fastest): use a raster mask generated from GSHHG.

                None: do not add land shapes.

        Returns:

            An matplotlib axes with a Cartopy projection.

        """
        if self.__cartesian__:
            ax = plt.axes()
            return ax

        # By popping the args from kwargs they are not passed onto matplotlib later.
        if kwargs_d is None:
            kwargs_d = kwargs
        else:
            for k,v in kwargs:
                kwargs_d[k] = v

        ax = kwargs_d.pop('ax', None)
        crs = kwargs_d.pop('crs', None)
        margin = kwargs_d.pop('margin', .1)
        corners = kwargs_d.pop('corners', None)
        land = kwargs_d.pop('land', 'auto')
        figsize = kwargs_d.pop('figsize', 11)

        assert crs is None or ax is None, "Only one of `ax` and `crs` may be specified."

        if ax is not None:
            logger.debug('axes already set up')
            return ax

        # It is not possible to change the projection of existing axes. The type of axes object returned
        # by `plt.axes` depends on the input projection.

        # Create a new figure if none exists.
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

        if len(plt.get_fignums()) == 0:
            logger.debug('Creating new figure and axes..')
            meanlat = (latmin + latmax) / 2
            aspect_ratio = float(latmax - latmin) / (float(lonmax - lonmin))
            aspect_ratio = np.abs(aspect_ratio / np.cos(np.radians(meanlat)))

            if aspect_ratio > 1:
                fig = plt.figure(figsize=(figsize / aspect_ratio, figsize))
            else:
                fig = plt.figure(figsize=(figsize, figsize * aspect_ratio))

            # fig.canvas.draw()  # maybe needed?
            plt.tight_layout()

        else:
            fig = plt.gcf()
            if len(fig.axes) > 0:
                logger.debug('Axes already exist on existing figure.')
                return fig.gca()
            else:
                logger.debug('Figure exists, setting up axes.')

        crs = crs if crs is not None else ccrs.Mercator()
        self.gcrs = ccrs.PlateCarree(globe=crs.globe)

        ax = fig.add_subplot(111, projection=crs)
        ax.set_extent([lonmin, lonmax, latmin, latmax], crs=self.gcrs)

        gl = ax.gridlines(self.gcrs, draw_labels=True)
        gl.top_labels = None

        if land is not None:
            add_land(ax, lonmin, latmin, lonmax, latmax,
                 fast=(land == 'mask' or land == 'fast'), lscale=land, globe=crs.globe)

        return ax

    def __call__(self, *args, **kwargs):
        return self.lines(*args, **kwargs)

    def fastplot(self, center_lon_circmean=False):
        """
        Do a fast plot of the data. This uses PlateCarree, no transform on the plotting,
        and circmean to determine the optimal central longitude to use.

        This only plots markers, not lines, to avoid wrapping lines on global datasets.

        Args:

            center_lon_circmean: bool, whether to use the circmean of the longitude
                of the data to set the central_longitude in PlateCarree (if True), or
                the default (0) if False.
        """

        if self.__cartesian__:
            x = self.ds.traj.tx.values.T
            y = self.ds.traj.ty.values.T
        else:
            x = self.ds.traj.tlon.values.T
            y = self.ds.traj.tlat.values.T

        if center_lon_circmean:
            all_y = x.flatten()
            mid_y = 180.0 / np.pi * sp.stats.circmean(all_y * np.pi / 180.0, nan_policy="omit")
        else:
            mid_y = 0.0

        ax = plt.axes(projection=ccrs.PlateCarree(central_longitude=mid_y))
        ax.coastlines()

        if len(x.shape) == 2:
            for crrt_buoy_idx in range(x.shape[1]):
                plt.plot(x[:, crrt_buoy_idx], y[:, crrt_buoy_idx], linestyle="none", marker=".", markersize=1)
        elif len(x.shape) == 1:
            plt.plot(x, y, linestyle="none", marker=".", markersize=1)
        else:
            raise ValueError(f"the position data to plot has shape {x.shape = }; unclear how to plot this!")

        gl = ax.gridlines(transform=ccrs.PlateCarree(central_longitude=mid_y), draw_labels=True)

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

        if 'alpha' not in kwargs and 'trajectory' in self.ds.dims:
            num = self.ds.sizes['trajectory']
            if num>100:  # If many trajectories, make more transparent
                kwargs['alpha'] = np.maximum(.1, 100/np.float64(num))

        if self.__cartesian__:
            x = self.ds.traj.tx.values.T
            y = self.ds.traj.ty.values.T
        else:
            x = self.ds.traj.tlon.values.T
            y = self.ds.traj.tlat.values.T

        if hasattr(kwargs['color'], 'shape'):
            from matplotlib.collections import LineCollection
            c = kwargs.pop('color').T
            if hasattr(c, 'values'):
                c = c.values
            vmin = kwargs.pop('vmin', np.nanmin(c))
            vmax = kwargs.pop('vmax', np.nanmax(c))
            norm = plt.Normalize(vmin, vmax)
            colorbar = kwargs.pop('colorbar', False)

            for i in range(x.shape[1]):
                logger.debug(f'Plotting trajectory {i} of {x.shape[1]} with color')
                points = np.array([x[:,i].T, y[:,i].T]).T.reshape(-1, 1, 2)
                segments = np.concatenate([points[:-1], points[1:]], axis=1)
                if self.__cartesian__:
                    lc = LineCollection(segments, cmap='jet', norm=norm,
                                        *args, **kwargs)
                else:
                    lc = LineCollection(segments, cmap='jet', norm=norm, transform=self.gcrs,
                                        *args, **kwargs)
                # Set the values used for colormapping
                lc.set_array(c[:,i])
                paths = ax.add_collection(lc)
        else:
            if self.__cartesian__:
                paths = ax.plot(x, y, *args, **kwargs)
            else:
                paths = ax.plot(x, y, transform=self.gcrs, *args, **kwargs)

        return paths

    def scatter(self, color_by_trajectory_rank=False, *args, **kwargs):
        """
        Plot the particles as points.

        Args:

            ax: Use existing axes, otherwise a new one is set up.

            crs: Specify crs for new axis.

        Returns:

            Matplotlib lines, and axes.
        """

        logger.debug(f'Plotting points')
        ax = self.set_up_map(kwargs)

        if 'marker' not in kwargs:
            kwargs['marker'] = '.'

        if 'color' not in kwargs:
            kwargs['color'] = self.DEFAULT_LINE_COLOR

        if 'alpha' not in kwargs and 'trajectory' in self.ds.dims:
            num = self.ds.sizes['trajectory']
            if num>100:  # If many particles, make more transparent
                kwargs['alpha'] = np.maximum(.1, 100/np.float64(num))

        if 'color_by_trajectory_rank':
            numb = self.ds.sizes['trajectory']
            colormap_mapper = ColormapMapper(plt.get_cmap("viridis"), 0, self.ds.sizes['trajectory'])
            colors = np.transpose(np.vectorize(colormap_mapper.get_rgb)(np.arange(0, self.ds.sizes['trajectory'], 1.0)))
            colors = np.repeat(colors, len(self.ds.obs))
            kwargs['c'] = colors
            del kwargs['color']

        if self.__cartesian__:
            x = self.ds.traj.tx.values.T
            y = self.ds.traj.ty.values.T
        else:
            x = self.ds.traj.tlon.values.T
            y = self.ds.traj.tlat.values.T

        if self.__cartesian__:
            paths = ax.scatter(x, y, *args, **kwargs)
        else:
            paths = ax.scatter(x, y, transform=self.gcrs, *args, **kwargs)

        return paths

    def convex_hull(self, *args, **kwargs):
        """
        Plot the convex hull around all particles

        Args:

            ax: Use existing axes, otherwise a new one is set up.

            crs: Specify crs for new axis.

        Returns:

            Matplotlib lines, and axes.
        """

        logger.debug(f'Plotting convex hull')
        hull = self.ds.traj.convex_hull()

        ax = self.set_up_map(kwargs)

        if 'color' not in kwargs:
            kwargs['color'] = self.DEFAULT_LINE_COLOR

        # TODO: might not work for cartesian plots
        line_segments = [hull.points[simplex] for simplex in hull.simplices]
        from matplotlib.collections import LineCollection
        paths = ax.add_collection(LineCollection(line_segments, transform=self.gcrs,
                                                 *args, **kwargs))

        return paths

