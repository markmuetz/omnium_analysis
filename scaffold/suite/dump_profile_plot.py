from logging import getLogger

import matplotlib
#from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np

matplotlib.use('Agg')
import pylab as plt

has_metpy = False
try:
    import metpy
    import metpy.calc as mpcalc
    from metpy.plots import SkewT
    from metpy.units import units
    has_metpy = True
except ImportError:
    pass

from omnium import Analyser
from omnium.utils import get_cube
from omnium.consts import p_ref, kappa

from scaffold.utils import cm_to_inch, find_intersections
from scaffold.expt_settings import EXPT_DETAILS

logger = getLogger('scaf.dump_prof_plot')
if not has_metpy:
    logger.warning('metpy not available')

# name, specific density, number conc., colour.
VARS = [
    ('qcl', (0, 254), (0, 75), 'b'),
    ('qcf', (0, 12), (0, 79), 'c'),
    ('qcf2', (0, 271), (0, 78), 'g'),
    ('qgr', (0, 273), (0, 81), 'r'),
    ('qrn', (0, 272), (0, 76), 'k'),
]


def plot_hydrometeor_profile(da, expt, ax1, ax2):
    for var in VARS:
        logger.debug('plotting profile of {} for {}', var, expt)
        varname = var[0]
        qvar = get_cube(da, *var[1])
        nvar = get_cube(da, *var[2])

        z = qvar.coord('atmosphere_hybrid_height_coordinate').points / 1000
        qvar_profile = qvar.data.mean(axis=(1, 2))
        nvar_profile = nvar.data.mean(axis=(1, 2))

        ax1.plot(qvar_profile * 1000, z, var[3], label=varname)
        ax2.plot(nvar_profile * 1000, z, var[3], label=varname)

        ax1.set_xscale('log')
        ax1.set_ylim((0, 20))
        ax1.set_xlim((10e-7, 10e-1))
        # ax1.set_title(expt)

        ax2.set_xscale('log')
        ax2.set_ylim((0, 20))
        ax2.set_xlim((10e-1, 10e8))

def plot_skewT(fig, subplot, name, p_profile, T_profile, Td_profile):
    skew = SkewT(fig=fig, subplot=subplot, rotation=55)

    skew.plot(p_profile.to('hPa'), T_profile.to('degC'), 'r-')
    skew.plot(p_profile.to('hPa'), Td_profile.to('degC'), 'r--')

    skew.ax.set_ylim(1000, 100)
    skew.ax.set_xlim(-35, 30)

    if subplot[2] in [2, 4]:
        plt.setp(skew.ax.get_yticklabels(), visible=False)
        skew.ax.set_ylabel('')
    else:
        skew.ax.set_ylabel('pressure (hPa)')

    if subplot[2] in [1, 2]:
        plt.setp(skew.ax.get_xticklabels(), visible=False)
        skew.ax.set_xlabel('')
    else:
        skew.ax.set_xlabel('temperature ($^\circ$C)')

    # skew.plot_dry_adiabats(t0=np.linspace(253.15, 303.15, 6) * units('K'))
    t0 = np.linspace(-40, 30, 8) * units('degC')
    skew.plot_dry_adiabats(t0=t0)
    skew.plot_moist_adiabats(t0=t0)
    skew.plot_mixing_lines()

    Tparcel_profile = mpcalc.parcel_profile(p_profile, T_profile[0], Td_profile[0]).to('degC')
    skew.plot(p_profile.to('hPa'), Tparcel_profile, 'k-')
    skew.shade_cape(p_profile, T_profile, Tparcel_profile)
    skew.shade_cin(p_profile[:20], T_profile[:20], Tparcel_profile[:20])

    try:
        cape, cin = mpcalc.surface_based_cape_cin(p_profile, T_profile, Td_profile)
        # skew.ax.set_title('{}\n'
        #                   'CAPE = {:.2f} J kg$^{{-1}}$\n'
        #                   'CIN = {:.2f} J kg$^{{-1}}$'
        #                   .format(name, cape.magnitude, cin.magnitude))
        skew.ax.set_title('{}'.format(name))
        lcl = mpcalc.lcl(p_profile[0], T_profile[0], Td_profile[0])
        lfc = mpcalc.lfc(p_profile, T_profile, Td_profile)
        lnb = mpcalc.el(p_profile, T_profile, Td_profile)
        # skew.ax.axhline(lcl[0].to('hPa').magnitude)
        # skew.plot([lcl[0].to('hPa'), lcl[0].to('hPa')], [200 * units('K'), 300 * units('K')], 'k--')
        legend_elements = [
            Patch(facecolor='r', alpha=0.5, label='CAPE={:.0f} J kg$^{{-1}}$'.format(cape.magnitude)),
            Patch(facecolor='b', alpha=0.5, label='CIN={:.0f} J kg$^{{-1}}$'.format(cin.magnitude)),
            Patch(facecolor='w', alpha=0, label='LNB={:.0f} hPa'.format(lnb[0].to('hPa').magnitude)),
            Patch(facecolor='w', alpha=0, label='LFC={:.0f} hPa'.format(lfc[0].to('hPa').magnitude)),
            Patch(facecolor='w', alpha=0, label='LCL={:.0f} hPa'.format(lcl[0].to('hPa').magnitude)),
        ]

        skew.ax.legend(handles=legend_elements, loc='bottom left', framealpha=1, handlelength=0.9)
    except Exception as e:
        logger.debug(e)

    fig.tight_layout()

class DumpProfilePlotter(Analyser):
    analysis_name = 'dump_profile_plot'
    multi_expt = True

    input_dir = 'share/data/history/{expt}'
    input_filename_glob = '{input_dir}/atmosa_da480.nc'
    output_dir = 'omnium_output/{version_dir}/suite_{expts}'
    output_filenames = ['{output_dir}/atmos.dump_profile_plot.dummy']

    def load(self):
        self.load_cubes()

    def run(self):
        pass

    def save(self, state, suite):
        with open(self.task.output_filenames[0], 'w') as f:
            f.write('done')

    def display_results(self):
        # self._plot_hydrometeors()
        self._plot_skewT()
        self._plot_theta_profiles()
        plt.close('all')

    def _plot_hydrometeors(self):
        fig = plt.figure(dpi=100, figsize=(10, 10))
        axes = []
        num_expts = len(self.task.expts)
        axL = fig.add_subplot(num_expts, 2, 1)
        axR = fig.add_subplot(num_expts, 2, 2, sharey=axL)

        for i, expt in enumerate(self.task.expts):
            da = self.expt_cubes[expt]
            print(i)
            if i == 0:
                ax1, ax2 = axL, axR
            else:
                ax1 = fig.add_subplot(num_expts, 2, i * 2 + 1, sharey=axL, sharex=axL)
                ax2 = fig.add_subplot(num_expts, 2, i * 2 + 2, sharey=axL, sharex=axR)
            axes.append([ax1, ax2])

            plot_hydrometeor_profile(da, expt, ax1, ax2)

            indiv_fig = plt.figure(dpi=100)
            indiv_ax1 = indiv_fig.add_subplot(1, 2, 1)
            indiv_ax2 = indiv_fig.add_subplot(1, 2, 2, sharey=axL)
            plot_hydrometeor_profile(da, expt, indiv_ax1, indiv_ax2)
            indiv_ax1.set_xlabel('mass fraction (g kg$^{-1}$)')
            indiv_ax2.set_xlabel('number (# kg$^{-1}$)')
            indiv_ax2.legend(bbox_to_anchor=(0.8, 0.75))
            indiv_fig.savefig(self.file_path('hydrometeors_{}.png'.format(expt)))

        axR.legend(bbox_to_anchor=(0.8, 0.95))
        for i, expt in enumerate(self.task.expts):
            axes[i][0].set_ylabel('{}\nheight (km)'.format(expt))

            if i != num_expts - 1:
                plt.setp(axes[i][0].get_xticklabels(), visible=False)
                plt.setp(axes[i][1].get_xticklabels(), visible=False)
                plt.setp(axes[i][1].get_yticklabels(), visible=False)

        axes[-1][0].set_xlabel('mass fraction (g kg$^{-1}$)')
        axes[-1][1].set_xlabel('number (# kg$^{-1}$)')

        # plt.tight_layout()
        plt.savefig(self.file_path('hydrometeors.png'))
        plt.show()

    def _plot_skewT(self):
        fig = plt.figure(dpi=100, figsize=cm_to_inch(18, 20))
        for i, expt in enumerate(self.task.expts):
            da = self.expt_cubes[expt]

            exnerp = get_cube(da, 0, 255)
            theta = get_cube(da, 0, 4)

            qvdata = get_cube(da, 0, 10).data
            Tdata = theta.data * exnerp.data
            pdata = exnerp.data ** (1 / kappa) * p_ref

            p = pdata * units('Pa')
            qv = qvdata * units('kg/kg')
            T = Tdata * units('K')
            Td = mpcalc.dewpoint_from_specific_humidity(qv, T, p)

            if expt in EXPT_DETAILS:
                expt_name = EXPT_DETAILS[expt][0]
            else:
                expt_name = expt
            plot_skewT(fig, (2, 2, i + 1), expt_name,
                       p.mean(axis=(1, 2)),
                       T.mean(axis=(1, 2)),
                       Td.mean(axis=(1, 2)))
            # plt.savefig(self.file_path('skewT_{}.png'.format(expt)))

            # fig = plt.figure(dpi=100, figsize=cm_to_inch(10, 12))

            if False and expt in EXPT_DETAILS:
                ucp_kwargs = dict(zip(['label', 'color', 'linestyle'], EXPT_DETAILS[expt]))
                plot_skewT(fig, ucp_kwargs['label'],
                           p.mean(axis=(1, 2)),
                           T.mean(axis=(1, 2)),
                           Td.mean(axis=(1, 2)))
                plt.savefig(self.file_path('UCP_skewT_{}.png'.format(expt)))
        plt.savefig(self.file_path('skewT.png'))

    def _plot_theta_profiles(self):
        fig, axes = plt.subplots(2, 2, sharex=True, sharey=True, figsize=cm_to_inch(18, 16))
        for expt_index, (expt, ax) in enumerate(zip(self.task.expts, axes.flatten())):
            logger.debug('plot thetas for {}', expt)
            da = self.expt_cubes[expt]
            if expt in EXPT_DETAILS:
                ax.set_title(EXPT_DETAILS[expt][0])

            theta_cube = get_cube(da, 0, 4)
            pi_cube = get_cube(da, 0, 255)
            q_cube = get_cube(da, 0, 10)
            q = q_cube.data

            theta = theta_cube.data
            p = pi_cube.data**(1 / kappa) * (p_ref / 100)
            T = theta * pi_cube.data

            z = theta_cube.coord('atmosphere_hybrid_height_coordinate').points

            Td = mpcalc.dewpoint_from_specific_humidity(q * units('kg/kg'), T * units.degK, p * units('hPa'))
            theta_e = mpcalc.equivalent_potential_temperature(p * units('hPa'), T * units.degK, Td)
            theta_es = mpcalc.saturation_equivalent_potential_temperature(p * units('hPa'), T * units.degK)

            theta_profile = theta.mean(axis=(1, 2))
            theta_e_profile = theta_e.mean(axis=(1, 2))
            theta_es_profile = theta_es.mean(axis=(1, 2))
            p_profile = p.mean(axis=(1, 2))

            line_theta, = ax.plot(theta_profile, z / 1000, 'r-', label='$\\theta$')
            line_theta_e, = ax.plot(theta_e_profile, z / 1000, 'g-', label='$\\theta_{e}$')
            line_theta_es, = ax.plot(theta_es_profile, z / 1000, 'b-', label='$\\theta_{es}$')
            line_pa = ax.axvline(x=theta_e_profile[0], linestyle='--', color='k', label='asc.')

            indices, weights = find_intersections(theta_es_profile.magnitude,
                                                  np.ones_like(theta_e_profile) * theta_e_profile[0].magnitude)

            i, w = indices[0], weights[0]
            z_lfc = z[i] + w * (z[i + 1] - z[i])
            p_lfc = p_profile[i] + w * (p_profile[i + 1] - p_profile[i])
            line_lfc, = ax.plot((theta_e_profile.magnitude[0] - 2, theta_e_profile.magnitude[0] + 2),
                                (z_lfc / 1000, z_lfc / 1000),
                                linestyle='--', color='grey', label='LFC={:.1f} km'.format(z_lfc / 1000))

            i, w = indices[1], weights[1]
            z_lnb = z[i] + w * (z[i + 1] - z[i])
            p_lnb = p_profile[i] + w * (p_profile[i + 1] - p_profile[i])
            line_lnb, = ax.plot((theta_e_profile.magnitude[0] - 2, theta_e_profile.magnitude[0] + 2),
                                (z_lnb / 1000, z_lnb / 1000),
                                linestyle='--', color='brown', label='LNB={:.1f} km'.format(z_lnb / 1000))


            logger.debug('LFC: {:.0f} m, {:.0f} hPa'.format(z_lfc, p_lfc))
            logger.debug('LNB: {:.0f} m, {:.0f} hPa'.format(z_lnb, p_lnb))

            if expt_index == 1:
                legend = plt.legend(handles=[line_theta, line_theta_e, line_theta_es, line_pa],
                                    loc=7, handlelength=1)
                plt.gca().add_artist(legend)

            ax.legend(handles=[line_lnb, line_lfc], loc=2, handlelength=1)

            if expt_index in [0, 1]:
                ax.set_xlabel('')
            else:
                ax.set_xlabel('(K)')

            if expt_index in [0, 2]:
                ax.set_ylabel('height (km)')
            ax.set_xlim((290, 360))
            ax.set_ylim((0, 15))

        title = 'thetas'
        plt.savefig(self.file_path(title))
