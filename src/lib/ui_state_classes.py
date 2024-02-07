import pickle
import pandas as pd

class UIstate:
    def __init__(self):
        self.reset()

    def reset(self): # reset all states to False
        self.version = "0.0.0"
        self.selected = []
        self.group_show = {}
        self.checkBox = {
            'EPSP_amp': False,
            'EPSP_slope': True,
            'volley_amp': False,
            'volley_slope': False,
            # break these out to separate mod-class?
            'norm_EPSP': False,
            'paired_stims': False,
        }
        self.lineEdit = {
            'norm_EPSP_on': [0, 0],
        }
        self.zoom = {
            'mean_xlim': (0.006, 0.020),
            'mean_ylim': (-0.001, 0.0002),
            'output_xlim': (0, None),
            'output_ax1_ylim': (0, None),
            'output_ax2_ylim': (0, None),
        }
        self.default = {
            'last_edit_mode': 'EPSP_slope',
            'EPSP_slope_size_default': 0.0003,
            'EPSP_slope_method_default': {},
            'EPSP_slope_params_default': {},
            'volley_slope_size_default': 0.0001,
            'volley_slope_method_default': {},
            'volley_slope_params_default': {},
        }
    
    def toDraw(self, df_p=None):
        show = self.checkBox
        all_aspects = {"EPSP_amp": show['EPSP_amp'], "EPSP_slope": show['EPSP_slope'], "volley_amp": show['volley_amp'], "volley_slope": show['volley_slope']}
        true_aspects = [k for k, v in all_aspects.items() if v is True]
        # returns a dict of what to draw
        if self.selected:
            df_select = df_p.loc[self.selected]
        else: # placeholder df to prevent key error when no rows are selected
            df_select = pd.DataFrame().assign(sweeps=[])
        df_analyzed = df_select[df_select['sweeps'] != "..."]
        print(f"df_analyzed: {df_analyzed}")
        for i, row in df_analyzed.iterrows():
            for aspect in true_aspects:
                print(f"{row['recording_name'].replace('_', ' ')} {aspect.replace('_', ' ')}")
        
    def get_state(self):
        try:
            return {
                'version': self.version,
                'selected': self.selected,
                'group_show': self.group_show,
                'checkBox': self.checkBox,
                'lineEdit': self.lineEdit,
                'zoom': self.zoom,
                'default': self.default,
            }
        except KeyError:
            self.reset()
    
    def set_state(self, state):
        self.version = state.get('version')
        self.selected = state.get('selected')
        self.group_show = state.get('group_show')
        self.checkBox = state.get('checkBox')
        self.lineEdit = state.get('lineEdit')
        self.zoom = state.get('zoom')
        self.default = state.get('default')

    def load_cfg(self, projectfolder, bw_version): # load state from project config file
        path_pkl = projectfolder / "cfg.pkl"
        if path_pkl.exists():
            with open(path_pkl, 'rb') as f:
                data = pickle.load(f)
            if data is not None:
                self.set_state(data)
            #check if version is compatible
            if bw_version != self.version:
                print(f"Warning: project_cfg.yaml is from {self.version} - current version is {bw_version}")
                cfg_v = self.version.split('.')
                bw_v = bw_version.split('.')
                if cfg_v[0] != bw_v[0]:
                    print("Major version mismatch: Project may not load correctly")
                elif cfg_v[1] != bw_v[1]:
                    print("Minor version mismatch: Some settings may not load correctly")
                elif cfg_v[2] != bw_v[2]:
                    print("Patch version mismatch: Minor changes may not load correctly")
        else:
            self.save_cfg(projectfolder, bw_version)

    def save_cfg(self, projectfolder, bw_version=None): # save state to project config file
        path_pkl = projectfolder / "cfg.pkl"
        data = self.get_state()
        if bw_version is not None:
            data['version'] = bw_version
        if not path_pkl.parent.exists():
            path_pkl.parent.mkdir(parents=True, exist_ok=True)
        print(f"Saving project config to {path_pkl}: {data}")
        with open(path_pkl, 'wb') as f:
            pickle.dump(data, f)

    def ampView(self):
        show = self.checkBox
        return (show['EPSP_amp'] or show['volley_amp'])
    
    def slopeView(self):
        show = self.checkBox
        return (show['EPSP_slope'] or show['volley_slope'])
    
    def slopeOnly(self):
        show = self.checkBox
        return (show['EPSP_slope'] and not show['EPSP_amp'])
  
    def anyView(self):
        show = self.checkBox
        return any(show.values())
    

if __name__ == "__main__":
    # test instantiation
    uistate = UIstate()
    assert uistate.anyView() == True
    uistate.checkBox['EPSP_slope'] = False
    assert uistate.anyView() == False
    print("test passed")
    
