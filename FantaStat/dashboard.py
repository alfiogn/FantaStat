import dash
from dash import dcc, html, Input, Output
import plotly.graph_objects as go
from plotly.validators.scatter.marker import SymbolValidator

import pandas as pd
import numpy as np

def create_df(season_data):
        return pd.DataFrame({
            "name": list(season_data.map.keys()),
            "team": [season_data[n].team for n in season_data.map.keys()],
            "role": [season_data[n].role for n in season_data.map.keys()],
            "presence_type": [season_data[n].presence_type for n in season_data.map.keys()],
            "mv": [season_data[n].mv for n in season_data.map.keys()],
            "fmv": [season_data[n].fmv for n in season_data.map.keys()],
            "quota": [season_data[n].quotc for n in season_data.map.keys()],
            "quot": [season_data[n].price for n in season_data.map.keys()],
            "dquot": [None if season_data[n].price is None else [0] + np.diff(season_data[n].price).tolist() for n in season_data.map.keys()],
            "fvmc": [season_data[n].fvmc for n in season_data.map.keys()],
            "voto": [season_data[n].voto for n in season_data.map.keys()],
            "fvoto": [season_data[n].fvoto for n in season_data.map.keys()]
        })

# Creazione della Dash app
class Dashboard():
    def __init__(self, player_list, fanta=None):
        self.app = dash.Dash(__name__)
        self.data = player_list
        self.fanta = fanta
        self.seasons = list(player_list.keys())

        # Layout dell'app con dropdown per filtri e grafico
        self.app.layout = html.Div([
            html.H1("Statistiche Giocatori"),

            # Dropdown per selezionare la stagione
            dcc.Dropdown(
                id='season-filter',
                options=[{'label': season, 'value': season} for season in self.seasons],
                placeholder="Seleziona stagione",
                value=self.seasons[-1]  # Seleziona l'ultima stagione disponibile come default
            ),

            # Dropdown per selezionare il tipo di presenza
            dcc.Dropdown(
                id='presence-filter',
                options=[
                    {'label': 'Titolare', 'value': 'Titolare'},
                    {'label': 'Entrato', 'value': 'Entrato'}
                ],
                placeholder="Seleziona tipo di presenza",
                multi=True
            ),

            # Dropdown per svincolati o altre squadre
            dcc.Dropdown(
                id='fantateam-filter',
                options=[
                    {'label': l, 'value': l}
                    for l in self.fanta['fantateam'].unique()
                ],
                placeholder="Seleziona tipo di FantaSquadra",
                multi=True
            ),

            # Dropdown per selezionare la squadra e il ruolo
            dcc.Dropdown(id='team-filter', placeholder="Seleziona squadra", multi=True),
            dcc.Dropdown(id='role-filter', placeholder="Seleziona ruolo", multi=True),

            # RangeSlider per selezionare i valori di quotazione, media voto e fantamedia voto
            dcc.RangeSlider(id='quot-filter', step=1),
            dcc.RangeSlider(id='mv-filter', step=0.5),
            dcc.RangeSlider(id='fmv-filter', step=0.5),

            # Dropdown per selezionare il tipo di valore da visualizzare nel grafico
            dcc.Dropdown(
                id='series-selector',
                options=[
                    {'label': 'Quotazione', 'value': 'quot'},
                    {'label': 'd(Quotazione)/dt', 'value': 'dquot'},
                    {'label': 'Voto', 'value': 'voto'},
                    {'label': 'Fanta Voto', 'value': 'fvoto'}
                ],
                value='quot'  # Default su quotazione
            ),

            # Grafico per la visualizzazione dei dati
            dcc.Graph(id='player-chart')
        ])

        # Callback per aggiornare i filtri in base alla stagione selezionata
        @self.app.callback(
            [
                Output('team-filter', 'options'),
                Output('role-filter', 'options'),
                Output('quot-filter', 'min'),
                Output('quot-filter', 'max'),
                Output('mv-filter', 'min'),
                Output('mv-filter', 'max'),
                Output('fmv-filter', 'min'),
                Output('fmv-filter', 'max')
            ],
            Input('season-filter', 'value')
        )
        def update_filters(selected_season):
            # Creazione DataFrame con le statistiche dei giocatori della stagione selezionata
            season_data = self.data[selected_season]
            players_data = create_df(season_data)
            players_data = players_data[players_data['mv'].notna()]

            # Aggiornamento delle opzioni dei filtri
            return (
                [{'label': team, 'value': team} for team in players_data['team'].unique()],
                [{'label': role, 'value': role} for role in players_data['role'].unique()],
                min([min(pd) for pd in players_data['quot']]), max([max(pd) for pd in players_data['quot']]),
                players_data['mv'].min(), players_data['mv'].max(),
                players_data['fmv'].min(), players_data['fmv'].max()
            )

        # Callback per aggiornare il grafico in base ai filtri selezionati
        @self.app.callback(
            Output('player-chart', 'figure'),
            Input('season-filter', 'value'),
            Input('presence-filter', 'value'),
            Input('fantateam-filter', 'value'),
            Input('team-filter', 'value'),
            Input('role-filter', 'value'),
            Input('quot-filter', 'value'),
            Input('mv-filter', 'value'),
            Input('fmv-filter', 'value'),
            Input('series-selector', 'value')
        )
        def update_graph(selected_season, selected_presence, selected_fantateam, selected_teams, selected_roles, quot_range, mv_range, fmv_range, selected_series):
            # Creazione DataFrame con i dati della stagione selezionata
            season_data = self.data[selected_season]
            players_data = create_df(season_data)
            players_data = players_data[players_data['mv'].notnull()]


            # Applicazione dei filtri
            filtered_df = players_data.copy()
            if selected_fantateam:
                filtered_df['fantateam'] = ''
                for i,row in filtered_df.iterrows():
                    if np.sum(self.fanta['name'].str.lower() == row['name'].lower()) > 0:
                        filtered_df.at[i, 'fantateam'] = self.fanta.loc[self.fanta['name'].str.lower() == row['name'].lower(), 'fantateam'].values[0]
                    else:
                        print('Missing', row['name'])
                filtered_df = filtered_df[filtered_df['fantateam'].isin(selected_fantateam)]
            if selected_teams:
                filtered_df = filtered_df[filtered_df['team'].isin(selected_teams)]
            if selected_roles:
                filtered_df = filtered_df[filtered_df['role'].isin(selected_roles)]
            if quot_range:
                filtered_df = filtered_df[(filtered_df['quota'] >= quot_range[0]) & (filtered_df['quota'] <= quot_range[1])]
            if mv_range:
                filtered_df = filtered_df[(filtered_df['mv'] >= mv_range[0]) & (filtered_df['mv'] <= mv_range[1])]
            if fmv_range:
                filtered_df = filtered_df[(filtered_df['fmv'] >= fmv_range[0]) & (filtered_df['fmv'] <= fmv_range[1])]


            # Filtro per presenza, mascherando i dati
            if selected_presence:
                for i,row in filtered_df.iterrows():
                    mask = [pt in selected_presence for pt in row['presence_type']]
                    filtered_df.at[i, selected_series] = [pt if pm else np.nan for pt,pm in zip(row[selected_series], mask)]

            # Filtro per valori uguali a -1, mascherando i dati
            for i,row in filtered_df.iterrows():
                mask = [pv != -1 and pq != 0 and pv != 0 for pq,pv in zip(row['quot'], row['voto'])]
                filtered_df.at[i, selected_series] = [pt if pm else np.nan for pt,pm in zip(row[selected_series], mask)]

            # Creazione del grafico
            fig = go.Figure()
            symbols = {v: SymbolValidator().values[i] for i,v in enumerate(filtered_df['role'].unique())}
            for _, row in filtered_df.iterrows():
                fig.add_trace(go.Scatter(
                    y=row[selected_series],
                    x=list(range(1, len(row[selected_series]) + 1)),
                    mode='lines+markers',
                    name=row['name'],
                    marker_symbol=symbols[row['role']]
                ))

            fig.update_layout(title="Andamento Giocatori", xaxis_title="Giornate", yaxis_title="Valore")
            return fig

    def run(self, debug=False):
        self.app.run_server(debug=debug)
