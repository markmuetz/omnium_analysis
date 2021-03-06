import os
from logging import getLogger
import csv

import pandas as pd

from omnium import Analyser

logger = getLogger('scaf.energy_bal')


class EnergyBalance(Analyser):
    analysis_name = 'energy_balance'
    single_file = True

    input_dir = 'omnium_output/{version_dir}/suite_{expts}'
    input_filenames = [
        '{input_dir}/surf_flux_plot_final_day_energy_flux.csv',
        '{input_dir}/relaxation_plot_final_day_relaxation_energy_flux.csv',
    ]
    output_dir = 'omnium_output/{version_dir}/suite_{expts}'
    output_filenames = ['{output_dir}/energy_balance.hdf']

    def load(self):
        self.surf_flux_file = open(self.task.filenames[0], 'r')
        self.rel_file = open(self.task.filenames[1], 'r')
        self.surf_flux_csv = csv.reader(self.surf_flux_file)
        self.rel_csv = csv.reader(self.rel_file)

    def run(self):
        self.surf_flux = {}
        self.rel = {}

        # skip header.
        logger.debug(next(self.surf_flux_csv))
        for row in self.surf_flux_csv:
            logger.debug(row)
            self.surf_flux[row[0]] = [float(v) for v in row[1:]]

        # skip header.
        logger.debug(next(self.rel_csv))
        for row in self.rel_csv:
            logger.debug(row)
            self.rel[row[0]] = [float(v) for v in row[1:]]

        self.surf_flux_file.close()
        self.rel_file.close()

    def save(self, state, suite):
        self.df_energy_balance.to_hdf(self.task.output_filenames[0], 'energy_balance')

    def display_results(self):
        cols = ['expt',
                'LHF', 'SHF', 'PFE',
                'TrelFE', 'QRelFE',
                'EnergyIn', 'EnergyOut',
                'MoistureIn', 'MoistureOut',
                'EnergyImbalance',
                'MoistureImbalance']
        data = []
        for expt in self.task.expts:
            sf_row = self.surf_flux[expt]
            rel_row = self.rel[expt]
            # LHF + SHF
            energy_in = sf_row[1] + sf_row[2]
            # TrelFE + QrelFE
            energy_out = rel_row[0] + rel_row[1]  # -ve
            # SHF
            moisture_in = sf_row[1]
            # PFE + QrelFE, N.B. PFE is +ve
            moisture_out = -sf_row[0] + rel_row[1]  # -ve
            logger.info('Energy imbalance for {} [W m-2]: {:.3f} ({:.2f} %)',
                        expt, energy_in + energy_out,
                        100 * (energy_in + energy_out) / energy_in)
            logger.info('Moisture imbalance for {} [W m-2]: {:.3f} ({:.2f} %)',
                        expt, moisture_in + moisture_out,
                        100 * (moisture_in + moisture_out) / moisture_in)

            data.append([expt,
                         sf_row[1], sf_row[2], -sf_row[0],
                         rel_row[0], rel_row[1],
                         energy_in, energy_out,
                         moisture_in, moisture_out,
                         energy_in + energy_out,
                         moisture_in + moisture_out])
        self.df_energy_balance = pd.DataFrame(data=data, columns=cols)
        latex_fn = os.path.splitext(self.task.output_filenames[0])[0] + '.tex'
        self.df_energy_balance.to_latex(latex_fn, float_format='%.1f')

