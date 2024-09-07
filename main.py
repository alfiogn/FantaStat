from driver import Driver, FANTASTAT_PATH, HOME, DATA_PATH
from player import Player, TEAM_COLORS
from scraper import Scraper

import os
import numpy as np
import pandas as pd

N_YEARS=1

# Scrap and save data
raw = Scraper(n_years=N_YEARS)
raw.ScrapAll()
# raw.UpdateAll()

