from driver import Driver, FANTASTAT_PATH, HOME, DATA_PATH
from player import Player
from scraper import Scraper

import numpy as np

# Scrap and save data
raw = Scraper(n_years=9)
raw.ScrapAll()


