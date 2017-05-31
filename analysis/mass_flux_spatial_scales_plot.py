import os
from collections import OrderedDict
from itertools import groupby

import numpy as np
import matplotlib
matplotlib.use('Agg')
import pylab as plt

from omnium.analyzer import Analyzer
from omnium.utils import get_cube_from_attr


class MassFluxSpatialScalesPlotter(Analyzer):
    analysis_name = 'mass_flux_spatial_scales_plot'
    multi_expt = True

    def set_config(self, config):
	super(MassFluxSpatialScalesPlotter, self).set_config(config)
        if 'xlim' in config:
            self.xlim = [float(v) for v in config['xlim'].split(',')]
        else:
            self.xlim = None

        if 'ylim' in config:
            self.ylim = [float(v) for v in config['ylim'].split(',')]
        else:
            self.ylim = None
        self.nbins = config.getint('nbins', None)

    def run_analysis(self):
        pass

    def _plot_mass_flux_spatial(self):
	self.append_log('plotting mass_flux_spatial')

        heights = []
        ns = []

	for expt in self.expts:
	    cubes = self.expt_cubes[expt]
            sorted_cubes = []

            for cube in cubes:
                (height_level_index, thresh_index, n) = cube.attributes['mass_flux_spatial_key']
                mf_key = (height_level_index, thresh_index, n)
                sorted_cubes.append((mf_key, cube))

            # Each element is a tuple like: ((1, 2, 32), cube)
            # Sorting will put in correct order, sorting on initial tuple.
            sorted_cubes.sort()

            # Group on first element of tuple, i.e. on 1 for ((1, 2, 32), cube)
            for height_index, key_cubes in groupby(sorted_cubes, lambda x: x[0][0]):
                if height_index not in heights:
                    heights.append(height_index)
                hist_data = []
                dmax = 0
                for i, key_cube in enumerate(key_cubes):
                    # middle cube is the one with the middle thresh_index.
                    mf_key = key_cube[0]
                    cube = key_cube[1]
                    # Pick out middle element, i.e. thresh_index == 1.
                    if mf_key[1] == 1:
                        hist_data.append((mf_key, cube))
                        dmax = max(cube.data.max(), dmax)

                # assert len(hist_data) == 3
                for mf_key, hist_datam in hist_data:
                    (height_index, thresh_index, n) = mf_key
                    if n not in ns:
                        ns.append(n)
                    name = '{}.{}.z{}.n{}.mass_flux_spatial_hist'.format(self.output_filename, expt, height_index, n)
                    plt.figure(name)
                    plt.clf()
                    plt.title(name)

                    hist_kwargs = {}
                    if self.xlim:
                        hist_kwargs['range'] = self.xlim
                    else:
                        hist_kwargs['range'] = (0, dmax)

                    if self.nbins:
                        hist_kwargs['bins'] = self.nbins
                    y, bin_edges = np.histogram(hist_datam.data, **hist_kwargs)
                    bin_centers = 0.5 * (bin_edges[1:] + bin_edges[:-1])

                    plot_filename = os.path.join(self.results_dir, name + '.png')
                    # N.B. full width bins.
                    width = bin_edges[1:] - bin_edges[:-1]
                    plt.bar(bin_centers, y, width=width)

                    if self.xlim:
                        plt.xlim(self.xlim)
                    plt.yscale('log')
                    if self.ylim:
                        plt.ylim(ymax=self.ylim[1])
                    log_plot_filename = os.path.join(self.results_dir, name + '_log.png')
                    plt.savefig(log_plot_filename)
                    self.append_log('Saved to {}'.format(log_plot_filename))

                    plt.yscale('linear')
                    if self.ylim:
                        plt.ylim(self.ylim)
                    plt.savefig(plot_filename)
                    self.append_log('Saved to {}'.format(plot_filename))

                    plt.figure('combined_expt_z{}'.format(height_index))
                    plt.plot(bin_centers, y, label=expt)

        for height_index in heights:
            plt.figure('combined_expt_z{}'.format(height_index))
            plt.title('combined_expt_z{}'.format(height_index))
            plt.legend()
            plt.yscale('log')
            combined_filename = os.path.join(self.results_dir, self.output_filename + '_z{}_combined.png'.format(height_index))
            plt.savefig(combined_filename)
            self.append_log('Saved to {}'.format(combined_filename))

    def save_analysis(self):
        self._plot_mass_flux_spatial()
        plt.close('all')