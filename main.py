from driver import Driver, FANTASTAT_PATH, HOME, DATA_PATH
from player import Player
from scraper import Scraper

import numpy as np
import pandas as pd

# Scrap and save data
raw = Scraper(n_years=1)
raw.ScrapAll()
# raw.UpdateAll()

