from selenium.webdriver import Safari
from selenium.webdriver.safari.service import Service as SafariService
from selenium.webdriver.safari.options import Options as SafariOptions

from selenium.webdriver.edge.service import Service as EdgeService

from selenium import webdriver

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By

import os, glob, re, pickle, time, pdb
import numpy as np
import pandas as pd

from player import Player

FANTASTAT_PATH = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(FANTASTAT_PATH, 'data')
HOME = os.getenv('HOME')
if HOME is None:
    HOME = os.getenv('HOMEPATH')

class Driver():
    def __init__(self, safari=False, edge=False, firefox=False, headless=False):
        self.download_path = DATA_PATH
        if not os.path.exists(self.download_path):
            os.mkdir(self.download_path)
        self.options = None
        self.service = None
        self.instance = None
        if safari:
            exe = '/usr/bin/safaridriver'
            # os.system('safaridriver --enable')
            options = SafariOptions()
            options._profile = None
            self.options = options
            self.service = SafariService(exe)
            self.instance = webdriver.Safari(service=self.service, options=self.options)
        elif edge:
            exe = '.\\msedgedriver.exe'
            data_fld = "C:" + HOME + "\\AppData\\Local\\Microsoft\\Edge\\Profile1"
            options = webdriver.EdgeOptions()
            options.use_chromium = True
            options.add_argument('log-level=3')
            # options.add_argument('--disable-gpu')
            # options.add_argument('--profile-directory=User Data1')
            options.add_argument('--disable-software-rasterizer')
            options.add_argument('--user-data-dir=' + data_fld)
            options.add_experimental_option('prefs', {
                        'download.default_directory': self.download_path,
                        'download.prompt_for_download': False,
                        'download.directory_upgrade': True,
                        'safebrowsing.enabled': True,
                        'profile.default_content_settings.popups': False,
                        'download.default_content_setting_values.automatic_downloads': 1,
            })
            options.add_experimental_option("excludeSwitches", ["enable-logging"])
            if headless:
                options.add_argument("--headless")
            self.options = options
            service = EdgeService(exe)
            self.instance = webdriver.Edge(service=self.service, options=self.options)
        else:
            raise IOError('cannot load service')

    def Get(self, url):
        self.instance.get(url)

    def Click(self, xpath, t=0.2):
        time.sleep(t)
        self.instance.find_elements(By.XPATH, xpath)[0].click()

    def WaitClick(self, xpath, t=8):
        WebDriverWait(self.instance, t).until(
            expected_conditions.element_to_be_clickable(
                (By.XPATH, xpath)
            )
        ).click()

    def FindIn(self, b, xpath, single=True):
        if single:
            return b.find_element(By.XPATH, xpath)
        else:
            return b.find_elements(By.XPATH, xpath)

    def Find(self, xpath, single=True, wait=None):
        res = None
        if wait is not None:
            t = 0
            while t < wait:
                start = time.time()
                stop = time.time()
                try:
                    res = self.FindIn(self.instance, xpath, single)
                    t = 2*wait
                except:
                    pass
                stop = time.time()
                t += (stop - start)
                print(t, start, stop)
        if res is not None:
            return res
        else:
            return self.FindIn(self.instance, xpath, single)

    def CookiesAccept(self):
        time.sleep(1)
        try:
            self.WaitClick("//button[contains(., 'ACCETTO')]")
        except:
            time.sleep(0.1)
            print("Warning! No base cookies found")
        try:
            self.WaitClick('//*[@id="pushengage-opt-in-6-close"]', t=2)
        except:
            time.sleep(0.1)
            print("Warning! No secondary cookies found")


if __name__ == "__main__":
    from scraper import SAFARI, EDGE, FIREFOX
    b = Driver(SAFARI, EDGE, FIREFOX)
    b.Get('https://www.fantacalcio.it/')
    b.CookiesAccept()


