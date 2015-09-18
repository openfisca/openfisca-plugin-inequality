# -*- coding:utf-8 -*-
# Copyright © 2012 Clément Schaff, Mahdi Ben Jelloul

"""
openFisca, Logiciel libre de simulation du système socio-fiscal français
Copyright © 2011 Clément Schaff, Mahdi Ben Jelloul

This file is part of openFisca.

    openFisca is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    openFisca is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with openFisca.  If not, see <http://www.gnu.org/licenses/>.
"""


from datetime import datetime

from pandas import DataFrame

from openfisca_france_data.surveys import SurveyScenario
from openfisca_france_data.model.common import mark_weighted_percentiles
from openfisca_plugin_inequality.gini import gini


class Inequality(object):
    data = None
    data_default = None
    gini = None
    inequality_data_frame = None
    poverty = None
    survey_scenario = None

    def __init__(self, survey_scenario = None):
        super(Inequality, self).__init__()
        self.data = DataFrame()
        self.vars = {
            'nivvie_ini': ['men'],
            'nivvie_net': ['men'],
            'nivvie': ['men'],
            }
#        self.vars = {'nivvie_prim': ['ind', 'men'],
#                     'nivvie_init': ['ind', 'men'],
#                     'nivvie_net':  ['ind', 'men'],
#                     'nivvie' : ['ind', 'men']}

        if survey_scenario is not None:
            self.survey_scenario(survey_scenario)

    def create_description(self):
        '''
        Creates a description dataframe
        '''
        now = datetime.now()
        descr = [
            u'OpenFisca',
            u'Calculé le {} à {}'.format((now.strftime('%d-%m-%Y'), now.strftime('%H:%M'))),
            u'Système socio-fiscal au {}'.format(self.survey_scenario.simulation.datesim),
            u"Données d'enquêtes de l'année {}".format(self.survey_scenario.survey_year),
            ]
        return DataFrame(descr)

    def compute(self):
        """
        Compute inequality dataframe
        """
        final_df = None
        simulation = self.survey_scenario.new_simulation()
        column_by_name = simulation.tax_benefit_system.column_by_name

        # amounts and beneficiaries from current data and default data if exists
        # Build weights for each entity

        from openfisca_france_data import FILTERING_VARS
        for varname, entities in self.vars.iteritems():
            for entity_key_plural in entities:
                column = column_by_name[varname]
                weight_name = self.survey_scenario.weight_column_name_by_entity_key_plural[column.entity_key_plural]
                filter_by = FILTERING_VARS[0]
                filter_by_name = FILTERING_VARS[0]
                if column.entity_key_plural is not 'menages':
                    filter_by_name = "{}_{}".format(filter_by, column.entity_key_plural)
                val = simulation.calculate(varname)
                weights = simulation.calculate(weight_name)
                filter_var = simulation.calculate(filter_by_name)

            items = []
            # Compute mean
            moy = (weights * filter_var * val).sum() / (weights * filter_var).sum()
            items.append(("Moyenne", [moy]))
            # Compute deciles
            labels = range(1, 11)
            method = 2
            decile, values = mark_weighted_percentiles(val, labels, weights * filter_var,
                                                       method, return_quantiles = True)
            labels = ['D' + str(d) for d in range(1, 11)]
            del decile
            for l, v in zip(labels[:-1], values[1:-1]):
                items.append((l, [v]))

            # Compute Gini
            gini_coeff = gini(val, weights * filter_var)
            items.append((_("Gini index"), [gini_coeff]))
            df = DataFrame.from_items(items, orient = 'index', columns = [varname])
            df = df.reset_index()
            if final_df is None:
                final_df = df
            else:
                final_df = final_df.merge(df, on='index')

        final_df[u"Initial à net"] = (final_df['nivvie_net'] - final_df['nivvie_ini']) / final_df['nivvie_ini']
        final_df[u"Net à disponible"] = (final_df['nivvie'] - final_df['nivvie_net']) / final_df['nivvie_net']
        final_df = final_df[['index', 'nivvie_ini', u"Initial à net", 'nivvie_net', u"Net à disponible", 'nivvie']]
        self.inequality_data_frame = final_df

        # Poverty
        poverty = dict()
        varname = "nivvie"
        for percentage in [40, 50, 60]:
            varname = "pauvre{}".format(percentage)
            column = column_by_name[varname]
            weight_name = self.survey_scenario.weight_column_name_by_entity_key_plural[column.entity_key_plural]
            filter_by_name = FILTERING_VARS[0]
            if column.entity_key_plural is not 'menages':
                filter_by_name = "{}_{}".format(filter_by, column.entity_key_plural)
            val = simulation.calculate(varname)
            weights = simulation.calculate(weight_name)
            filter_var = simulation.calculate(filter_by_name)
            poverty[percentage] = (weights * filter_var * val).sum() / (weights * filter_var).sum()

        self.poverty = poverty

    def set_survey_scenario(self, survey_scenario):
        """
        Set simulation
        """
        if isinstance(survey_scenario, SurveyScenario):
            self.survey_scenario = survey_scenario
        else:
            raise Exception('Inequality: {} should be an instance of {} class'.format(survey_scenario, SurveyScenario))
