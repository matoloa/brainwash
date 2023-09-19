# %%
# tests for route

# in test_simple.py

import os
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
#from copy import deepcopy

from parse import *


class TestParse(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__.split("/brainwash")[0]) / "brainwash" 
        self.source_folder = self.repo_root / "src/lib/test_data"
        self.proj_folder = Path.home() / "Documents/Brainwash Projects/standalone_test"
        self.list_sources = [str(self.source_folder / "A_21_P0701-S2/2022_07_01_0012.abf.gitkeep"),
                             str(self.source_folder / "KO_02/2022_01_24_0000.abf.gitkeep")]

        return super().setUp()

    
    def test_abf_parse_and_save(self):
        for item in self.list_sources:
            recording_name = os.path.basename(os.path.dirname(item))
            print(" - processing", item, "as recording_name", recording_name)
            df_files = pd.DataFrame({"path": [item], "recording_name": [recording_name]})
            dictmeta = parseProjFiles(proj_folder=self.proj_folder, df=df_files)
            self.assertTrue(type(dictmeta) is dict)

    
    def test_assignStimAndsweep(self):
        df = importabf(filepath=Path(self.list_sources[0]))
        dfss = assignStimAndsweep(df, list_stims=['a'])
        self.assertTrue(dfss.sweepraw.max()==239)
        self.assertTrue(dfss.sweep.max()==239)
        self.assertTrue(dfss.duplicated(subset=['channel', 'time', 'sweepraw']).sum()==0)
        
        df = importabf(filepath=Path(self.list_sources[0]))
        dfss = assignStimAndsweep(df, list_stims=['a', 'b'])
        self.assertTrue(dfss.sweepraw.max()==239)
        self.assertTrue(dfss.sweep.max()==119)
        self.assertTrue(dfss.duplicated(subset=['channel', 'time', 'sweepraw']).sum()==0)

        df = importabf(filepath=Path(self.list_sources[0]))
        dfss = assignStimAndsweep(df, list_stims=['a', 'b', 'c', 'd'])
        self.assertTrue(dfss.sweepraw.max()==239)
        self.assertTrue(dfss.sweep.max()==59)
        self.assertTrue(dfss.duplicated(subset=['channel', 'time', 'sweepraw']).sum()==0)

        df = importabf(filepath=Path(self.list_sources[1]))
        dfss = assignStimAndsweep(df, list_stims=['a', 'b'])
        self.assertTrue(dfss.sweepraw.max()==239)
        self.assertTrue(dfss.duplicated(subset=['channel', 'time', 'sweepraw']).sum()==0)

        
        
        
    #    df_expected = pd.read_csv("src/lib/test_route_dfs/expected/" + df_name + ".csv.gitkeep")
    #    df_actual = pd.read_csv("src/lib/test_route_dfs/actual/" + df_name + ".csv")
    #    pd.testing.assert_frame_equal(df_expected, df_actual)


    def test_get_dist(self):
        pass
        #self.assertAlmostEqual(self.route.get_dist(coord1=self.config.route['coords'][0], coord2=self.config.route['coords'][1]), 111319, places=0)



    def tearDown(self) -> None:
        return super().tearDown()


if __name__ == "__main__":
    import nose2

    nose2.main()

# %%
