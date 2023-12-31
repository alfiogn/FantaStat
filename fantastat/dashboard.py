from . import driver
from . import utils, championship

import os, sys, pickle, pdb, threading, time
import xlrd
import pandas as pd
import numpy as np

# from flask_caching import Cache
from dash import Dash, dash_table, dcc, html, ctx
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
from sklearn.cluster import KMeans
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
pio.templates.default = 'ggplot2'

class dashboard():
    def __init__(self, y0, y1, q, s, v, sa,
                 prob=None, rig=None, approb=None, headless=True,
                 last=None, update=False):
        self.year0 = y0
        self.year1 = y1
        self.nyears = y1 - y0 + 1
        self.lastDays = last
        # update data
        browser = driver.driver(headless=headless)
        self.download_path = browser.download_path
        utils.DownloadXLSX(browser, q, s, v, update=update)
        self.SerieA = championship.Archive(y0, y1, browser, sa, last=last,
                                           prob=prob, rig=rig, approb=approb, update=update)
        browser.quit()

        # dashboard creation
        self.app = Dash(
            __name__,
            external_stylesheets=[dbc.themes.BOOTSTRAP,
                                  '/'.join([driver.FANTASTAT_PATH, '/assets/dashboard.css']),
                                  'https://codepen.io/chriddyp/pen/bWLwgP.css'],
            meta_tags=[
                {"name": "viewport", "content": "width=device-width, initial-scale=1"}
            ]
        )
        # self.cache = Cache(self.app.server, config={
        #     'CACHE_TYPE': 'filesystem',
        #     'CACHE_DIR': '__flaskcache__'
        # })
        # self.app.config.suppress_callback_exceptions = True
        # self.timeout = 20
        self.app.title = 'FantaStat'
        # object ids
        self.ID_table = 'fantastat-datatable'
        self.ID_filt_graphs = 'fantastat-graphs-filter'
        self.ID_old_graphs_names = None
        self.ID_glob_graphs = 'fantastat-graphs-global'
        self.ID_dd_year = 'fantastat-list-year'
        self.default_year = 'Last Days'
        self.old_year = 'Last Days'
        self.ID_dd_howmanydays = 'fantastat-list-howmanydays'
        self.default_howmanydays = '%d' % self.lastDays
        self.old_howmanydays = '%d' % self.lastDays
        self.default_howmanydays0 = 1
        self.old_howmanydays0 = 1
        self.ID_dd_doy = 'fantastat-list-days-or-year'
        self.default_doy = 'Last Days'
        self.old_doy = 'Last Year'
        self.ID_dd_role = 'fantastat-list-role'
        self.default_role = 'Tutti'
        self.old_role = 'Tutti'
        self.ID_dd_q_colors = 'fantastat-list-qcolors'
        self.default_q_colors = 'By team'
        self.old_q_colors = 'By team'
        self.ID_btn_backup = 'fantastat-btn-backup'
        self.ID_btn_export = 'fantastat-btn-export'
        # load database
        self.db = self.SerieA.GetLastStats(n0=self.lastDays - self.SerieA.Present.last_day, n1=self.lastDays)

        # auxiliary variables to update data
        # flag: top, semi-top, low cost, hype e hidden
        self.cols_to_remember = ['Team', 'Costo', 'Flag', 'Note']
        self.cols_to_data = ['Pg', 'Mv', 'Mf', 'Gf', 'Rigori', 'Ass', 'Malus']
        self.cols_to_barplot = ['Qt.A', 'FVM', 'Pg', 'Mv', 'Mf', 'Gf']
        self.cols_to_quant = self.cols_to_barplot[:-1]
        self.orig_new_idxs = np.arange(self.db.shape[0])
        self.old_backup_count = 0

        # notes
        self.backup_notes_file = self.download_path + '/asta_notes_backup.pickle'
        self.loadBackup()

        # team data
        self.backup_asta_file = self.download_path + '/asta_teams_backup.pickle'
        self.MlnBudget = 500
        self.MyName, self.Teams, self.Lega, self.dbAsta = None, None, None, None
        self.RoleDict = {'P': 3, 'D': 8, 'C': 8, 'A': 6}
        self.loadBackupAsta()
        self.computeAsta()

        # Prepare run
        self.app.layout = self.Layout()
        self.RegisterCallbacks()



    def backup(self, data):
        # merge self.db with virtual data of table
        merge_cols = ['R', 'Nome', 'Squadra']
        self.db = self.db.merge(
            pd.DataFrame.from_dict(data).loc[:, merge_cols + self.cols_to_remember],
            left_on=merge_cols, right_on=merge_cols, how='left'
        )
        for c in self.cols_to_remember:
            idxs = self.db[c + '_y'].isna()
            self.db.loc[idxs, c + '_y'] = self.db.loc[idxs, c + '_x'].values
        self.db.drop(columns=[ci + '_x'  for ci in self.cols_to_remember], inplace=True)
        self.db.columns = [ci.replace('_y', '') for ci in self.db.columns]
        col_preso = self.db.pop("Team")
        self.db.insert(loc=0, column="Team", value=col_preso)
        # save pickle
        with open(self.backup_notes_file, 'wb') as f:
            pickle.dump(self.db.loc[:, merge_cols + self.cols_to_remember], f)

    def backupAsta(self):
        with open(self.backup_asta_file, 'wb') as f:
            pickle.dump(
                [self.MyName, self.Teams, self.Lega, self.dbAsta],
                f
            )

    def loadBackup(self):
        if os.path.isfile(self.backup_notes_file):
            with open(self.backup_notes_file, 'rb') as f:
                notes = pd.read_pickle(f)
                merge_cols = ['R', 'Nome', 'Squadra']
                self.db = self.db.merge(notes, left_on=merge_cols, right_on=merge_cols, how='left')
                col_preso = self.db.pop("Team")
                self.db.insert(loc=0, column="Team", value=col_preso)
                col_preso = self.db.pop("Costo")
                self.db.insert(loc=1, column="Costo", value=col_preso)
        else:
            self.db.insert(loc=0, column='Team', value='')
            self.db.insert(loc=1, column='Costo', value=0)
            for nc in self.cols_to_remember[1:]:
                self.db[nc] = ''

    def loadBackupAsta(self):
        if os.path.isfile(self.backup_asta_file):
            with open(self.backup_asta_file, 'rb') as f:
                self.MyName, self.Teams, self.Lega, self.dbAsta = pd.read_pickle(f)
        else:
            self.MyName = 'banana steakhouse'
            self.Teams = [self.MyName, 'Case', 'Piegro', 'Fore', 'Barney', 'Taffo', 'Niub', 'Lomba', 'Ismo', 'Fusto']
            self.dbAsta = pd.DataFrame.from_dict({t+'M':[0]*5 for t in self.Teams})
            for i,t in enumerate(self.Teams):
                self.dbAsta.insert(loc=3*i+1, column=t+'%', value=0)
                self.dbAsta.insert(loc=3*i+2, column=t+'-', value=0)
            self.Lega = dict()
            for t in self.Teams:
                self.Lega[t] = dict()
                for r in self.db['R'].unique():
                    self.Lega[t][r] = dict()

    def computeAsta(self):
        self.dbAsta = pd.DataFrame.from_dict({t+'M':[0]*5 for t in self.Teams})
        for i,t in enumerate(self.Teams):
            self.dbAsta.insert(loc=3*i+1, column=t+'%', value=0)
            self.dbAsta.insert(loc=3*i+2, column=t+'-', value=0)
        for i,t in enumerate(self.Teams):
            for j,r in enumerate(self.Lega[t].keys()):
                for p in self.Lega[t][r].keys():
                    self.dbAsta.iloc[j, 3*i] += self.Lega[t][r][p]
                    self.dbAsta.iloc[j, 3*i+1] += int(self.Lega[t][r][p]/self.MlnBudget*100)
                self.dbAsta.iloc[j, 3*i+2] += self.RoleDict[r] - len(self.Lega[t][r].keys())
            self.dbAsta.iloc[-1, 3*i] = self.MlnBudget - np.sum(self.dbAsta.iloc[:-1, 3*i])
            self.dbAsta.iloc[-1, 3*i+1] = 100 - np.sum(self.dbAsta.iloc[:-1, 3*i+1])

    def exchangeData(self, data, year, n0=1, n1=20):
        new_data = None
        if year == 'Last Days':
            new_data = self.SerieA.GetLastStats(n0=n0, n1=n1)
        elif int(year) == (2000 + self.year1 + 1):
            new_data = self.db
        else:
            new_data = self.SerieA.Players[-(int(year) - 2000 - self.year1) - 1].db
        data = pd.DataFrame.from_dict(data).merge(
            new_data.loc[:, ['Nome'] + self.cols_to_data],
            left_on=['Nome'], right_on=['Nome'], how='left'
        )
        data.drop(columns=[ci + '_x'  for ci in self.cols_to_data], inplace=True)
        data.columns = [ci.replace('_y', '') for ci in data.columns]
        return data.to_dict('records')

    def App(self):
        return self.app

    def Style(self):
        return False

    def Header(self):
        table_league_columns = []
        df = pd.DataFrame.from_dict({t:[0]*4 for t in self.Teams*2})
        for i in df.columns:
            table_league_columns += [
                {"name": [i, 'M'], "id": i+'M'},
                {"name": [i, '%'], "id": i+'%'},
                {"name": [i, '-'], "id": i+'-'}
            ]
        obj_style = lambda x: {'width': str(x)+'%', 'padding': '10px'}
        perc = [8, 17, 25, 50]
        roles = ['P', 'D', 'C', 'A']
        per_role = [1, 3.8, 4.3, 2.75]
        perc_per_role = ""
        role_per_team = ""
        col_qt = 'FVM'
        for i in range(4):
            perc_per_role += roles[i] + " " + str(perc[i]) \
                    + "% (" + str(int(self.MlnBudget*perc[i]/100)) + "M)"
            qtl70 = self.db[self.db['R'] == roles[i]]['FVM'].quantile(0.70)
            qtl85 = self.db[self.db['R'] == roles[i]]['FVM'].quantile(0.9)
            utili       = int(np.sum(self.db[self.db['R'] == roles[i]]['FVM'].values > qtl70)/len(self.Teams))
            utili_small = int(np.sum(self.db[self.db['R'] == roles[i]]['FVM'].values > qtl85)/len(self.Teams))
            role_per_team += "%s %d(%d)" % (roles[i], utili, utili_small if utili_small > 0 else 1)
            if i != 3:
                perc_per_role += "    -    "
                role_per_team += "    -    "

        obj = html.Div([
            dbc.Col([
                dbc.Row([
                    html.Div(
                        dcc.Dropdown(self.Teams, self.MyName, id='input-register-team'),
                        style=obj_style(35)
                    ),
                    html.Div(
                        dcc.Dropdown(list(self.db['Nome']), '', id='input-register-player'),
                        style=obj_style(25)
                    ),
                    html.Div(
                        dcc.Input(id='input-register-cost', type='number', style=obj_style(100)),
                        style=obj_style(20)
                    ),
                    html.Div(
                        html.Button('Submit', n_clicks=0, id='btn-register-buy', style=obj_style(100)),
                        style=obj_style(10)
                    ),
                    html.Div(
                        html.Button('Remove', n_clicks=0, id='btn-register-rm', style=obj_style(100)),
                        style=obj_style(10)
                    ),
                ], style=obj_style(100)),
                dbc.Row([
                    html.H6("Statistiche generali", style={"font-weight": "bold"}),
                    html.P("Spesa % per ruolo: " + perc_per_role),
                    html.P("Giocatori utili per squadra: " + role_per_team),
                    html.P("Flags: hype (Y), hidden (H), no (N); fasce (+-);"),
                    html.P("top (T), semi-top (ST), buono (B), low-cost (LC);")
                ], style=obj_style(100)),
                # ASTA-CHANGE: Appunti vari
                dbc.Row([
                    html.H6("Appunti...", style={"font-weight": "bold"}),
                #     html.P("Miglior difesa", style={"font-weight": "bold"}),
                #     html.P("    2022 - Top: Napoli, Lazio, Juve, Roma;    Semi-top: Torino, Inter, Milan, Lecce;    Medi: Udinese, Empoli, Monza"),
                #     html.P("Corrente - Top: Inter, Juve, Lecce;    Semi-top: Napoli, Lazio, Atalanta;    Medi: Roma, Juve, Monza, Milan"),
                #     html.P("Commenti: nel 22, non si sono confermate Atalanta e Salernitana, ma hanno stupito Monza e Lazio (risp 21)"),
                #     html.P(""),
                #     html.P("Miglior attacco", style={"font-weight": "bold"}),
                #     html.P("    2022 - Top: Napoli, Inter, Atalanta, Milan, Lazio;    Semi-top: Juve, Fiorentina, Roma, Salernitana;    Medi: Udinese, Sassuolo"),
                #     html.P("Corrente - Top: Inter, Roma, Juve;    Semi-top: Milan, Sassuolo, Fiorentina, Napoli, Lecce;    Medi: ND"),
                #     html.P("Commenti: nel 22, non si è confermata Udinese, ma hanno stupito Lazio, Fiorentina, Sassuolo"),
                    # html.P("")
                ], style=obj_style(100)),
            ], width=6),
            dbc.Col(
                html.Div(
                    dash_table.DataTable(
                        self.dbAsta.to_dict('records'),
                        table_league_columns,
                        id='table-league',
                        # styles
                        style_header={
                            'backgroundColor': 'rgb(230, 230, 230)',
                            'color': 'black',
                            'fontWeight': 'bold',
                            'border': '3px solid black',
                            'height': '35px'
                        },
                        style_data={},
                        style_cell={'font-family': 'sans-serif'},
                        merge_duplicate_headers=True,
                    ),
                    style=obj_style(100)
                ),
                width=6
            ),
        ], className='fantastat-options')
        return obj

    def VizOptions(self):
        dd_style = {'padding': '10px', 'width': '15%'}
        ddL_style = {'padding': '10px', 'width': '20%'}
        obj1 = html.Div([
            html.Div(
                dcc.RangeSlider(
                    1, self.lastDays, 1, value=[self.lastDays - self.SerieA.Present.last_day, self.lastDays],
                    id=self.ID_dd_howmanydays
                ), style={'padding': '35px', 'width': '50%'},
                # dcc.Dropdown(
                #     ['%d' % (i + 1)  for i in range(self.lastDays)],
                #     self.default_howmanydays,
                #     id=self.ID_dd_howmanydays,
                # ),
            )
        ], className='fantastat-options')
        obj0 = html.Div([
            # select year data
            html.Div(
                dcc.Dropdown(
                    ['Last Days'] + ['20' + str(i) for i in range(self.year1+1, self.year0-1, -1)],
                    self.default_year,
                    id=self.ID_dd_year,
                ), style=dd_style
            ),
            # NOTE: not very useful, better to use the filters of datatable
            # # select role to visualize
            # html.Div(
            #     dcc.Dropdown(
            #         [self.default_role, 'P', 'D', 'C', 'A'], self.default_role,
            #         id=self.ID_dd_role,
            #     ),
            #     style=dd_style
            # ),
            # select colors by team or globally, in general by role
            html.Div(
                dcc.Dropdown(
                    [self.default_q_colors, 'Global'], self.default_q_colors,
                    id=self.ID_dd_q_colors,
                ),
                style=dd_style
            ),
            # save some editable columns
            html.Div(
                html.Button('Backup changes', id=self.ID_btn_backup,
                            n_clicks=0),
                style=dd_style,
            ),
            html.Div(
                html.Button('Export excel', id=self.ID_btn_export,
                            n_clicks=0),
                style=dd_style,
            ),
            dcc.Interval(id='backup-interval', interval=180*1000, n_intervals=0),
        ], className='fantastat-options')

        return obj0, obj1

    def DataConditional(self, group, db):
        inj_color = '#FF413633'
        # alternate rows colors and team colors
        base_style = [
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': 'rgb(245, 245, 245)',
            }
        ] + self.SerieA.TeamColors()
        inf_style = [
            {
                'if': {
                    'filter_query': '{{Inf}} != ""'.format(db.loc[index, :]),
                    'column_id': ['Team', 'R', 'RM', 'Nome']
                },
                'backgroundColor': inj_color
            } for index in range(db.shape[0])
        ]
        # coloring by role
        q_colors = ['#FF69614D', '#AEC6CF4D', '#77DD774D']
        quantiles = [0.6, 0.75, 0.9]
        t_quantiles = [0.3, 0.6, 0.8]
        role_style = []
        for i,q in enumerate(quantiles):
            for r in db['R'].unique():
                if group == self.default_q_colors:
                    for col in self.cols_to_quant:
                        role_style += [
                            {
                                'if': {
                                    'filter_query': '{{{}}} = {} && {{{}}} >= {}'.format(
                                        'R', r, col,
                                        db[db['R'] == r][col].quantile(q)
                                    ),
                                    'column_id': col
                                },
                                'backgroundColor': q_colors[i],
                            }
                        ]
                else:
                    for t in db['Squadra'].unique():
                        for col in self.cols_to_quant:
                            role_style += [
                                {
                                    'if': {
                                        'filter_query': '{{{}}} = {} && {{{}}} = {} && {{{}}} >= {}'.format(
                                            'Squadra', t, 'R', r, col,
                                            db[np.logical_and(db['Squadra'] == t, db['R'] == r)][col].quantile(t_quantiles[i])
                                        ),
                                        'column_id': col
                                    },
                                    'backgroundColor': q_colors[i],
                                }
                            ]
        return base_style + inf_style + role_style

    def Layout(self):
        numeric = ['Qt.A', 'FVM', 'Pg', 'Mv', 'Mf', 'Gf', 'Rigori', 'Ass', 'Malus',
                   'N.Tit', 'Rig', 'Pun']
        return html.Div([
            self.Header(),
            *self.VizOptions(),
            dash_table.DataTable(
                id=self.ID_table,
                columns=[
                    {"name": i, "id": i,
                     "type": "numeric" if i in numeric else 'text',
                     "hideable": True, "editable": True}
                    for i in self.db
                ],
                # styles
                style_header={
                    'backgroundColor': 'rgb(230, 230, 230)',
                    'color': 'black',
                    'fontWeight': 'bold',
                    'border': '3px solid black',
                    'height': '70px'
                },
                style_data={},
                style_cell={'font-family': 'sans-serif'},
                style_data_conditional=self.DataConditional(self.default_q_colors, self.db),
                # style_data_conditional=[],
                style_cell_conditional=[
                    {
                        'if': {'column_id': 'Note'},
                        'width': '40%',
                    }
                ],
                # virtualization=True,
                fill_width=False,
                persistence=True,
                data=self.db.to_dict('records'),
                editable=True,
                filter_action="native",
                sort_action="native",
                sort_mode="multi",
                column_selectable="single",
                row_selectable=False,
                row_deletable=False,
                selected_columns=[],
                selected_rows=[],
                # ASTA-CHANGE: delete Note from list, add 'Inf'
                hidden_columns=['Rm', 'RM', 'Note'],
                # fixed_rows={'headers': True},
                page_action="native",
                page_current=0,
                page_size=205,
            ),
            html.Div(id=self.ID_filt_graphs), #, className='fantastat-options'),
            html.Div(id=self.ID_glob_graphs),
        ])

    def run_server(self, debug=False, port=8050, run=True):
        if run:
            self.app.run_server(port=port, debug=debug)

    ####### ####### #### #######
    #######   Callbacks  #######
    ####### ####### #### #######
    def RegisterCallbacks(self):
        # NOTE: only one callback can have an output
        @self.app.callback(
            Output(self.ID_table, 'data'),
            Output(self.ID_table, 'style_data_conditional'),
            Output('table-league', 'data'),
            # Statistiche
            Input(self.ID_table, "derived_virtual_data"),
            Input(self.ID_table, "derived_virtual_selected_rows"),
            Input(self.ID_btn_backup, 'n_clicks'),
            Input(self.ID_btn_export, 'n_clicks'),
            Input(self.ID_dd_q_colors, 'value'),
            Input(self.ID_dd_year, 'value'),
            Input(self.ID_dd_howmanydays, 'value'),
            # Asta
            Input('btn-register-buy', 'n_clicks'),
            Input('btn-register-rm', 'n_clicks'),
            Input('input-register-team', 'value'),
            Input('input-register-player', 'value'),
            Input('input-register-cost', 'value'),
            # States
            State(self.ID_table, 'data'),
            State(self.ID_table, 'style_data_conditional'),
            State('table-league', 'data'),
            prevent_initial_call=True
        )
        # @self.cache.memoize(timeout=self.timeout)
        def change_highlight_and_backup_stats_and_asta(
            # Stats
            vdata, vrows, bckp_clicks, exprt_clicks, group, year, days,
            # Asta
            asta_buy, asta_rm, asta_team, asta_player, asta_cost,
            # States
            data, sdcond, asta_data
        ):
            trig_id = ctx.triggered_id
            if trig_id is None or trig_id in ['input-register-team', 'input-register-player', 'input-register-cost']:
                raise PreventUpdate

            print("    Modifying", trig_id)
            print("    ", end="")
            if (trig_id == 'btn-register-buy' or trig_id == 'btn-register-rm') \
                and asta_player is not None:
                asta_rm = trig_id == 'btn-register-rm'
                if (not asta_rm and asta_cost is not None and asta_team is not None) or asta_rm:
                    idx = np.where(pd.DataFrame.from_dict(data)['Nome'].values == asta_player)[0][0]
                    si_o_no = asta_team
                    if asta_rm:
                        si_o_no = ''
                    if data[idx]['Team'] != si_o_no:
                        idx0 = np.where(self.db['Nome'].values == asta_player)[0][0]
                        role = self.db.loc[idx0, 'R']

                        if asta_rm:
                            asta_team = self.db.loc[idx0, 'Team']
                            self.db.loc[idx0, 'Team'] = ''
                            data[idx]['Team'] = ''
                            self.db.loc[idx0, 'Costo'] = 0
                            data[idx]['Costo'] = 0
                            tmp_cost = self.Lega[asta_team][role].pop(asta_player)
                            print("Removing", asta_player, "("+str(tmp_cost)+") from asta_team "+asta_team)
                        elif asta_team is not None:
                            self.db.loc[idx0, 'Team'] = asta_team
                            data[idx]['Team'] = asta_team
                            self.db.loc[idx0, 'Costo'] = asta_cost
                            data[idx]['Costo'] = asta_cost
                            self.Lega[asta_team][role][asta_player] = asta_cost
                            print("Adding", asta_player, "("+str(asta_cost)+") to asta_team "+asta_team)

                    self.computeAsta()

                else:
                    print(asta_player, 'already taken' if not asta_rm else 'not taken yet')

                return data, sdcond, self.dbAsta.to_dict('records')

            if trig_id == self.ID_btn_export:
                thread = threading.Thread(target=self.toExcel, args=[data])
                thread.start()
                raise PreventUpdate

            if trig_id == self.ID_btn_backup and self.old_backup_count < bckp_clicks:
                print("Saving to", self.backup_notes_file, 'and', self.backup_asta_file)
                self.old_backup_count = bckp_clicks
                # TODO: save data backup, look also in constructor
                thread0 = threading.Thread(target=self.backup, args=[vdata])
                thread0.start()
                thread1 = threading.Thread(target=self.backupAsta)
                thread1.start()
                raise PreventUpdate

            if trig_id == self.ID_dd_q_colors: # and self.old_q_colors.lower() != group.lower():
                print("Coloring", group.lower())
                self.old_q_colors = group
                return data, self.DataConditional(group, db=pd.DataFrame(vdata)), asta_data

            if trig_id == self.ID_dd_year and year != self.old_year:
                print("Get data from", year)
                self.old_year = year
                return self.exchangeData(data, year), self.DataConditional(group, db=pd.DataFrame(vdata)), asta_data

            if trig_id == self.ID_dd_howmanydays and year == 'Last Days' and days != [self.old_howmanydays0, self.old_howmanydays]:
                time.sleep(2)
                print("Get data from last ", days)
                self.old_howmanydays0, self.old_howmanydays = days
                return self.exchangeData(data, year, n0=self.old_howmanydays0, n1=self.old_howmanydays), self.DataConditional(group, db=pd.DataFrame(vdata)), asta_data

            # NOTE: avoid using this, better to use the data filter
            # if trig_id == self.ID_dd_role and role != self.old_role and False:
            #     print("Filter by role", role)
            #     self.old_role = role
            #     if role != self.default_role:
            #         return self.db[self.db['R'] == role].to_dict('records'), sdcond
            #     else:
            #         return self.db.to_dict('records'), sdcond, asta_data

            print(" -- * -- * -- ")

            raise PreventUpdate

        @self.app.callback(
            Output(self.ID_filt_graphs, "children"),
            Input(self.ID_table, "derived_virtual_data"),
            # Input(self.ID_table, "derived_virtual_selected_rows"),
            Input(self.ID_dd_howmanydays, 'value'),
        )
        # @self.cache.memoize(timeout=self.timeout)
        def update_graphs(vdata, n):
            # if sel_vdata is None:
            #     sel_vdata = []

            if vdata is None or len(vdata) == 0:
                raise PreventUpdate

            vdata = pd.DataFrame.from_dict(vdata)
            if self.ID_old_graphs_names is None:
                self.ID_old_graphs_names = np.sort(vdata['Nome'].values)
            elif n == self.old_howmanydays:
                if len(self.ID_old_graphs_names) == len(vdata['Nome'].values):
                    if np.all(self.ID_old_graphs_names == np.sort(vdata['Nome'].values)):
                        raise PreventUpdate


            print("    Update graphs for %d players" % len(vdata))

            player_story = None
            if n is None:
                player_story = self.SerieA.GetPlayerStory()
            else:
                player_story = self.SerieA.GetPlayerStory(n0=n[0], n1=n[1])

            df = vdata.merge(
                player_story, left_on=['R', 'Nome', 'Squadra'],
                right_on=['R', 'Nome', 'Squadra'], how='left'
            )
            df.drop(columns=[ci for ci in df.columns if '_x' in ci], inplace=True)
            df.columns = [ci.replace('_y', '') for ci in df.columns]
            df = df.loc[:, ['R', 'Nome', 'Squadra', 'Day', 'Mean', 'FantaMean', 'Bonus']]
            df.drop(index=df.index[df.Mean.isna()], inplace=True)

            # # highlight selected data
            # cls = self.SerieA.TeamColorsDict(only_bg=True)
            # colors = [cls[dff['Squadra'].values[i]] + '80'
            #           if i in derived_virtual_selected_rows else cls[dff['Squadra'].values[i]]
            #           for i in range(len(dff))]

            df['Day'] += -np.max(df['Day']) + self.SerieA.Present.last_day - (self.lastDays - n[1])

            color_map = self.SerieA.TeamColorsDict(only_bg=True)
            color_map_name = {df.loc[i, 'Nome']:color_map[df.loc[i, 'Squadra']] for i in df.index}
            fig0 = px.line(df, x='Day', y='Mean', color='Nome', markers=True,
                           title='Media', #log_y=True,
                           color_discrete_map=color_map_name)#, line_shape="spline")
            fig1 = px.line(df, x='Day', y='FantaMean', color='Nome', markers=True,
                           title='Fantamedia', #log_y=True,
                           color_discrete_map=color_map_name)#, line_shape="spline")
            fig2 = px.line(df, x='Day', y='Bonus', color='Nome', markers=True,
                           title='Bonus',
                           color_discrete_map=color_map_name)#, line_shape="spline")
            # fig2.update_xaxes(range=(0, n[1] - n[0] + 1), constrain='domain')
            style = {'width': '48%'}
            return [html.H6("Andamento giocatori", style={"font-weight": "bold"})] + [
                html.Div([
                    dcc.Graph(figure=fig0, style=style),
                    dcc.Graph(figure=fig1, style=style),
                ], style={'display': 'flex', 'height': '400px'}),
                html.Div([
                    dcc.Graph(figure=fig2, style={'width': '80%'}),
                ], style={'display': 'flex'})
            ]

        @self.app.callback(
            Output(self.ID_glob_graphs, "children"),
            Input(self.ID_dd_year, 'value')
        )
        # @self.cache.memoize(timeout=self.timeout)
        def glob_graphs(year):
            if year == 'Last Days':
                year = str(2000 + self.year1 + 1)
            print("    Update global graphs for year", year)
            style = {'width': '33%'}
            em0 = self.SerieA.PlotEnglishMean()
            em1 = self.SerieA.PlotEnglishMeanYear(int(year[-2:]) - 1)
            em2 = self.SerieA.PlotEnglishMeanYear(int(year[-2:]))
            for ei in em2:
                ei.update_xaxes(range=(0, self.SerieA.Present.last_day + 1), constrain='domain')
            return [html.H6("Grafici per squadra", style={"font-weight": "bold"})] + [
                html.Div([
                    dcc.Graph(figure=em0[i], style=style),
                    dcc.Graph(figure=em1[i], style=style),
                    dcc.Graph(figure=em2[i], style=style),
                ], style={'display': 'flex'})
                for i in [2, 1, 0]
            ]

    ####### ####### ####### ####### #######
    #######   Write the excel file  #######
    ####### ####### ####### ####### #######
    def toExcel(self, data):
        # Initial sorting
        df = pd.DataFrame.from_dict(data)
        writer = pd.ExcelWriter('/'.join([self.download_path, 'asta_sheet.xls']), engine='xlsxwriter')
        workbook  = writer.book
        df.to_excel(writer, sheet_name="Statistiche", index=False)
        worksheet = writer.sheets['Statistiche']

        # Formatting
        XXL, XL, L, M, S = 70, 30, 20, 12, 5
        lengths = [S, S, S, S, L, L] + 14*[S] + [L, S, S, S, S, XXL]
        aligns = ['center' if i == S else 'left' for i in lengths]
        for l in range(len(lengths)):
            cf = workbook.add_format()
            cf.set_align(aligns[l])
            worksheet.set_column(l, l, lengths[l], cf)

        # Settings
        worksheet.autofilter(0, 0, df.shape[0], df.columns.shape[0]-1)
        worksheet.set_zoom(100)

        ####### Analysis formatting for better view
        def markfont(sheet, rows, col, c=0):
            col_dict = {0:'#008c1b', 1:'#8c0013', 2:'#0e008c', 3:'#8c6200'}
            color   = workbook.add_format({'bold' : True, 'font_color': col_dict[c]})
            for i in range(len(rows)):
                sheet.conditional_format(rows[i]+1, col, rows[i]+1, col,
                        {'type' : 'unique', 'format' : color})

        def markcells(sheet, rows, col, c=0):
            col_dict = {0:'#C6EFCE', 1:'#FFF0C7', 2:'#C7D4FF', 3:'#FFC7CE', 4:'#E7C7FF'}
            color   = workbook.add_format({'bg_color': col_dict[c]})
            for i in range(len(rows)):
                sheet.conditional_format(rows[i]+1, col, rows[i]+1, col,
                        {'type' : 'unique', 'format' : color})

        def markteams(sheet, rows, col, team):
            color = workbook.add_format({'bg_color': self.SerieA.TeamColorsDict(only_bg=True)[team]})
            for i in range(len(rows)):
                sheet.conditional_format(rows[i]+1, col, rows[i]+1, col,
                        {'type' : 'unique', 'format' : color})

        # filter titolari
        df1 = df.loc[df['N.Tit'].isin([2, 1]), :]
        nteams = 10
        un_roles = ['P', 'D', 'C', 'A']
        un_no = [3, 8, 8, 6]
        un_no = [2, 4, 4, 3]
        cols = [['Mv', 'Mf', 'Qt.A'],
                ['Mv', 'Mf', 'Qt.A'],
                ['Mv', 'Mf', 'Qt.A', 'Gf', 'Ass'],
                ['Mv', 'Mf', 'Qt.A', 'Gf', 'Ass']]
        asc  = [[False, False, False, True],
                3*[False],
                5*[False],
                5*[False]]
        for i in range(len(un_roles)):
            df2 = df1.loc[df1.R.isin([un_roles[i]]), :]
            for j in range(len(cols[i])):
                df3 = df2.sort_values(cols[i][j], ascending=asc[i][j])
                for k in range(un_no[i]):
                    markcells(worksheet, df3.index.values[k*nteams : (k+1)*nteams],
                              df3.columns.get_loc(cols[i][j]), c=k)

        # files = ['neopromosse', 'scommesse', 'dacomprare', 'daevitare']
        # colors = [3, 2, 0, 1]
        # cnt = 0
        # for f in files:
        #     data = np.loadtxt('stat/'+f, delimiter=",", dtype="U20")
        #     df2 = df.loc[df.Giocatore.isin(data), :]
        #     markfont(worksheet, df2.index.values, df3.columns.get_loc('Giocatore'), c=colors[cnt])
        #     cnt += 1

        ####### Analysis for general purposes
        alfabeto = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        recapsheet = workbook.add_worksheet("Recap")
        recapsheet.set_column(0, 0, XL)
        cf = workbook.add_format()
        cf.set_align('center')
        bold_font = workbook.add_format({'bold': True})
        recapsheet.set_column(1, 5, S+1, cf)
        recapsheet.write_string(1, 0, 'Numero di giocatori titolari', bold_font)
        recapsheet.write_string(0, 1, 'TOT', bold_font)
        recapsheet.write_formula(1, 1, '=countif(Statistiche!D:D, "=2")')
        recapsheet.write_string(2, 0, 'Numero di riserve', bold_font)
        recapsheet.write_formula(2, 1, '=countif(Statistiche!D:D, "=1")')
        for i in range(len(un_roles)):
            recapsheet.write_string(0, i+2, un_roles[i], bold_font)
            recapsheet.write_formula(1, i+2,
                    '=countifs(Statistiche!D:D, "=2", Statistiche!B:B, "='+un_roles[i]+'")')
            recapsheet.write_formula(2, i+2,
                    '=countifs(Statistiche!D:D, "=1", Statistiche!B:B, "='+un_roles[i]+'")')
            recapsheet.write_formula(3, i+2, '='+alfabeto[i+2]+str(2)+'/10')

        recapsheet.write_string(3, 0, 'Per squadra', bold_font)
        recapsheet.write_formula(3, 1, '='+alfabeto[1]+str(2)+'/10')


        recapsheet.write_string(5, 0, 'Consigliati', bold_font)
        recapsheet.write_string(5, 2, 'Fasce', bold_font)
        # for i in range(len(files)):
        #     recapsheet.write_string(6+i, 0, files[i].capitalize())
        #     markfont(recapsheet, [6+i-1], 0, c=colors[i])

        for i in range(len(un_no)):
            recapsheet.write_string(6+i, 2, 'Fascia '+str(i+1))
            markcells(recapsheet, [6+i-1], 2, c=i)

        writer.close()



