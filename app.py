import os, sys, pickle
from fantastat.dashboard import dashboard
import pandas as pd
import numpy as np


probabili_formazioni_2324 = 'https://www.fantacalcio.it/news/calcio-italia/05_08_2023/calciomercato-come-cambia-la-serie-a-2023-24-le-probabili-formazioni-446506'
rigoristi = 'https://www.fantacalcio.it/rigoristi-serie-a'
probabili_formazioni = 'https://www.fantacalcio.it/probabili-formazioni-serie-a'

voti = lambda y,n: 'https://www.fantacalcio.it/voti-fantacalcio-serie-a/20'+str(y)+'-'+str(y+1)+'/'+str(n)
statistiche = lambda y: 'https://www.fantacalcio.it/statistiche-serie-a/20'+str(y)+'-'+str(y+1)+'/statistico/riepilogo'
quotazioni = lambda y: 'https://www.fantacalcio.it/quotazioni-fantacalcio/20'+str(y)
seriea = 'https://www.legaseriea.it/it/serie-a'

db = dashboard(15, 22, quotazioni, statistiche, voti, seriea,
               prob=probabili_formazioni, rig=rigoristi, last=20,
               approb=probabili_formazioni_2324)
# NOTE: Set headless=False to see what Firefox does

if __name__ == '__main__':
    # db.run_server(debug=True, run=False)
    # db.run_server(debug=True)
    db.run_server()





