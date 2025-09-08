import os
import shutil
import multiprocessing
import threading
import json
import time
import numpy as np
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS, cross_origin


from ..fantastat import FantaStat, ASTA_BUDGET
from ..player import TEAM_COLORS
from ..driver import DATA_DIR

REACT_BUILD_DIR = 'build'

class Dashboard():
    def __init__(self, fs: FantaStat=None, appunti=None):
        if fs is None:
            return

        self.fanta: FantaStat = fs
        self.appunti = appunti
        self.seasons = list(self.fanta.raw.player_list.keys())
        self.fantasquadre = ['Taffo', 'Alfio', 'Casella', 'Lomba', 'Fore', 'Fatte', 'Niub', 'Barney', 'Carl', 'Fusto']
        self.astabackup = os.path.join(fs.basepath, DATA_DIR, 'asta.json')
        if os.path.isfile(self.astabackup):
            self.asta = json.load(open(self.astabackup, 'r'))
        else:
            self.asta = {team: {
                'nome': team,
                'budget_iniziale': ASTA_BUDGET, 'budget_rimasto': ASTA_BUDGET,
                'spesa_per_ruolo': {'P': 0, 'D': 0, 'C': 0, 'A': 0},
                'acquisti': []
            } for team in self.fantasquadre}
        self.app = Flask(__name__)
        CORS(self.app, resources={r"/api/*": {"origins": "http://localhost:3000"}})
        self.app.config['CORS_HEADERS'] = 'Content-Type'
        self.RegisterPost()
        self.RegisterGet()

    # API Endpoints
    def RegisterPost(self):
        @self.app.route('/api/players')
        def post_players():
            """Endpoint per ottenere tutti i giocatori"""
            try:
                players = self.fanta.stats['Giocatore'].tolist()
                return jsonify({
                    'success': True,
                    'data': players,
                    'count': len(players)
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/auction-teams')
        def post_auction_data():
            """Endpoint per ottenere tutti i giocatori"""
            try:
                return jsonify({
                    'success': True,
                    'data': {'teams': self.fantasquadre, 'budget': ASTA_BUDGET}
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/auction-history')
        def post_history():
            """Endpoint per ottenere tutti i giocatori"""
            try:
                return jsonify({
                    'success': True,
                    'data': self.asta
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/notes')
        def post_notes():
            """Endpoint per ottenere le note sull'asta"""
            try:
                return jsonify({
                    'success': True,
                    'data': '' if not self.appunti else open(self.appunti, 'r', encoding='utf-8-sig').read(),
                    'count': 1
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/team-colors')
        def post_team_colors():
            """Endpoint per ottenere le note sull'asta"""
            try:
                teams = TEAM_COLORS
                return jsonify({
                    'success': True,
                    'data': teams,
                    'count': len(teams)
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/stats-header')
        def post_stats_header():
            """Endpoint per statistiche generali"""
            try:
                return jsonify({
                    'success': True,
                    'data': self.fanta.columns
                })
            except Exception as e:
                print(e)
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

        @self.app.route('/api/stats/<days>')
        def post_stats(days):
            """Endpoint per statistiche generali"""
            try:
                stats = self.fanta.get_stats(days=days).to_dict('records')

                return jsonify({
                    'success': True,
                    'data': stats
                })
            except Exception as e:
                print(e)
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500

    def RegisterGet(self):
        @self.app.route('/api/buy/<buyer>/<role>/<nameurl>/<price>')
        @cross_origin()
        def get_buy(buyer, role, nameurl, price):
            try:
                stats = self.fanta.get_stats()

                update = False

                name = nameurl.replace('%20', ' ')
                print(f'{buyer} buys {name} for {price}')

                if buyer not in self.asta.keys():
                    return jsonify({
                        'success': False,
                        'error': 'No team found ' + buyer
                    }), 500


                for i,aq in enumerate(self.asta[buyer]['acquisti']):
                    if name == aq['nome']:
                        print('   ...update')
                        budget_player = stats.query(f'Giocatore == "{name}"').iloc[0, :]['Budget']
                        if budget_player:
                            budget_player = float(budget_player)
                        else:
                            budget_player = int(price)
                        self.asta[buyer]['acquisti'][i] = {
                            'ruolo': role, 'nome': name, 'prezzo': int(price),
                            'var': np.round((int(price) - budget_player)/budget_player*100, 1),
                            'timestamp': time.time()
                        }
                        update = True
                        break

                if not update:
                    budget_player = stats.query(f'Giocatore == "{name}"').iloc[0, :]['Budget']
                    if budget_player:
                        budget_player = float(budget_player)
                    else:
                        budget_player = int(price)
                    self.asta[buyer]['acquisti'].append({
                        'ruolo': role, 'nome': name, 'prezzo': int(price),
                        'var': np.round((int(price) - budget_player)/budget_player*100, 1),
                        'timestamp': time.time()
                    })

                self.asta[buyer]['budget_rimasto'] = \
                    self.asta[buyer]['budget_iniziale'] - \
                    sum([aq['prezzo'] for aq in self.asta[buyer]['acquisti']])
                for role in self.asta[buyer]['spesa_per_ruolo'].keys():
                    self.asta[buyer]['spesa_per_ruolo'][role] = \
                        sum([aq['prezzo'] for aq in self.asta[buyer]['acquisti'] if aq['ruolo'] == role])

                self.asta_dump()
                return jsonify({
                    'success': True,
                    'data': self.asta
                })
            except Exception as e:
                print(e)
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500


    def asta_dump(self):
        json.dump(self.asta, open(self.astabackup, 'w'), indent=2)

    def setup_react_build(self):
        print("\n📋 To configure react:\n")
        print("1. Create React project:")
        print("   npx create-react-app fantastat-dashboard")
        print("   cd fantastat-dashboard")
        print("\n2. Install dependencies:")
        print("   npm install lucide-react")
        print("   npm install react-markdown react-remark")
        print("   npm install recharts")
        print("   npm install -D tailwindcss@3 postcss autoprefixer")
        print("   npm install @tailwindcss/typography")
        print("   npx tailwindcss init -p")
        print("\n3. Copy frontend source files:")
        src_path = os.path.dirname(os.path.abspath(__file__))
        print("   cp", os.path.join(src_path, 'src', 'App.js'), os.path.join('.', 'src', ''))
        print("   cp", os.path.join(src_path, 'src', 'index.css'), os.path.join('.', 'src', ''))
        print("   cp", os.path.join(src_path, 'assets', 'tailwind.config.js'), os.path.join('.', ''))
        print("\n4. Build:")
        print("   mkdir build")
        print("   npm run build")

    def run(self, debug=False, rebuild=False, help=False):
        if help:
            self.setup_react_build()
            return

        print("🚀 Avviando Flask server per Fantacalcio Dashboard...")

        print("📊 Available API endpoints:")
        print("   - GET /api/players")
        print("   - GET /api/players/role/<role>")
        print("   - GET /api/stats/cur")
        # if rebuild:
        #     os.makedirs('build', exist_ok=True)
        #     os.system('npm run build')
        #     app_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'App.js')
        #     shutil.copy(app_src, os.path.join('src', ''))
        #     app_css = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'index.css')
        #     shutil.copy(app_css, os.path.join('src', ''))
        #     app_css = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'tailwind.config.js')
        #     shutil.copy(app_css, '.')
        print("\n🌐 Opening dashboard su: http://localhost:3000")

        def run_be():
            self.app.run(
                # host='0.0.0.0',
                port=5000,
                debug=debug,
                # use_reloader=False,
                # threaded=True
            )

        def run_fe():
            os.system('npm start')

        # # backend = multiprocessing.Process(target=run_be)
        # # frontend = multiprocessing.Process(target=run_fe)
        # # backend.start()
        # # frontend.start()
        # threads = [threading.Thread(target=run_be), threading.Thread(target=run_fe)]
        # for t in threads:
        #     t.start()
        # for t in threads:
        #     t.join()
        run_be()

