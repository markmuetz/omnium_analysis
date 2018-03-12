from logging import getLogger

import matplotlib
import numpy as np

matplotlib.use('Agg')
import pylab as plt
import iris

from omnium.analyser import Analyser
from omnium.utils import get_cube_from_attr
from cloud_tracking.utils import label_clds

from scaffold.suite_settings import LX, LY, NX, NY

logger = getLogger('scaf.org_an')


class Cloud(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y


class OrgAnalyser(Analyser):
    """Calculates cloud-cloud distances for each pair of clouds, taking into account bicyclic dom.

    Works out where each cloud is (centroid), then calculates the cloud to cloud distance for every
    cloud to every other cloud.
    Performs once for each height level, and each pair of low/low, med/med, high/high threshs."""
    analysis_name = 'org_analysis'
    single_file = True

    def run_analysis(self):
        cubes = self.cubes

        logger.debug('got cube slices')

        cloud_mask_id = 'cloud_mask'
        cloud_mask_cube = get_cube_from_attr(cubes, 'omnium_cube_id', cloud_mask_id)

        w_thresh_coord = cloud_mask_cube.coord('w_thres')
        qcl_thresh_coord = cloud_mask_cube.coord('qcl_thres')
        level_number_coord = cloud_mask_cube.coord('model_level_number')

        # level_number refers to orig cube.
        # height_level_index refers to w as it has already picked out the height levels.
        for height_level_index, level_number in enumerate(level_number_coord.points):
            for thresh_index in range(w_thresh_coord.shape[0]):
                logger.debug('height_index, thresh_index: {}, {}'.format(height_level_index,
                                                                         thresh_index))

                w_thresh = w_thresh_coord.points[thresh_index]
                qcl_thresh = qcl_thresh_coord.points[thresh_index]
                labelled_clouds_cube_id = 'labelled_clouds_z{}_w{}_qcl{}'.format(level_number,
                                                                                 w_thresh,
                                                                                 qcl_thresh)
                labelled_clouds_cube = get_cube_from_attr(cubes,
                                                          'omnium_cube_id',
                                                          labelled_clouds_cube_id)
                # N.B. I just take the diagonal indices.
                dists = []
                total_clouds = 0

                logger.debug('# time indices: {}'.format(cloud_mask_cube.data.shape[0]))
                for time_index in range(cloud_mask_cube.data.shape[0]):
                    # Find each cloud.
                    labelled_clouds = labelled_clouds_cube[time_index].data.astype(int)

                    cp = self._get_cloud_pos(labelled_clouds)
                    clouds = [Cloud(cp[j, 0], cp[j, 1]) for j in range(cp.shape[0])]
                    total_clouds += len(clouds)
                    # Heart of analysis.
                    new_dists = self._calc_cloud_stats(clouds)
                    dists.extend(new_dists)

                mean_clouds = total_clouds / cloud_mask_cube.data.shape[0]

                dist_cube_id = 'dist_z{}_w{}_qcl{}'.format(level_number, thresh_index, thresh_index)
                values = iris.coords.DimCoord(range(len(dists)), long_name='values')
                dist_cube = iris.cube.Cube(dists,
                                           long_name=dist_cube_id,
                                           dim_coords_and_dims=[(values, 0)],
                                           units='')

                dist_cube.attributes['dist_key'] = (height_level_index, thresh_index)
                dist_cube.attributes['dist_mean_total_clouds'] = (mean_clouds, total_clouds)
                self.results[dist_cube_id] = dist_cube

    def display_results(self):
        dist_cube_id = 'dist_z{}_w{}_qcl{}'.format(18, 1, 1)
        dists = self.results[dist_cube_id].data

        n, bins, patch = plt.hist(dists, 700)
        #fig = self.plt.figure()
        plt.clf()

        areas = np.pi * (bins[1:]**2 - bins[:-1]**2)
        cloud_densities = n / areas

        # Normalize based on mean density over domain.
        # WRONG WAY TO DO IT!:
        # mean = cloud_densities[bins < LX / 2.].mean()
        # self.plt.plot((bins[:-1] + bins[1:]) / 2, cloud_densities / mean)
        # calculates the mean of the densities, not the mean density.

        # Correct way to normalize:
        # Divide the total number in a circle by the circle's area.
        imax = np.argmax(bins[1:] > (LX / 2))
        mean_density = n[:imax].sum() / (np.pi * bins[imax]**2)
        xpoints = (bins[:-1] + bins[1:]) / 2
        plt.plot(xpoints / 1000, cloud_densities / mean_density)
        plt.xlabel('Distance (km)')
        plt.ylabel('Normalized cloud number density')
        plt.axhline(y=1, ls='--')
        #print(bins[:21] / 1000)
        #print(n[:20])
        #print(cloud_densities[:20])

        plt.xlim((0, 120))
        plt.ylim((0, 20))
        plt.savefig(self.figpath('dists_hist.png'))

    def _get_cloud_pos(self, clouds):
        "For each cloud, calc its centroid."
        half_dx = LX / (2 * NX)
        half_dy = LY / (2 * NY)
        x = np.linspace(half_dx, LX - half_dx, NX)
        y = np.linspace(half_dy, LY - half_dy, NY)
        X, Y = np.meshgrid(x, y, indexing='xy')
        cloud_pos = []
        for i in range(1, clouds.max() + 1):
            # Averages the x, y coords of all cells with a given index to get each cloud's
            # "centre of mass", AKA centroid.
            cloud_x = X[clouds == i].sum() / (clouds == i).sum()
            cloud_y = Y[clouds == i].sum() / (clouds == i).sum()
            cloud_pos.append((cloud_x, cloud_y))
        return np.array(cloud_pos)

    def _calc_min_dists(self, cloud, test_cloud):
        "Used to calc min distance on cyclic domain."
        dists = []
        for ii in [-1, 0, 1]:
            for jj in [-1, 0, 1]:
                x = test_cloud.x + ii * LX
                y = test_cloud.y + jj * LY
                dist = np.sqrt((cloud.x - x)**2 + (cloud.y - y)**2)
                dists.append(dist)
        return dists

    def _calc_cloud_stats(self, clouds):
        "Calculate the cloud stats of distances between each cloud and each other cloud."
        dists = []
        # For each cloud:
        for i in range(len(clouds)):
            cloud = clouds[i]
            # For each other cloud:
            for j in range(i + 1, len(clouds)):
                test_cloud = clouds[j]
                new_dists = self._calc_min_dists(cloud, test_cloud)
                dists.extend(new_dists)
        return dists
