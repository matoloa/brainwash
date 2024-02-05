class UIstate:
    def __init__(self):
        self.show = {
            'EPSP_amp': False,
            'EPSP_slope': False,
            'volley_amp': False,
            'volley_slope': False,
            'dict_groups': {} # key: group_ID, value: bool (show or don't show group)
        }
        self.defaults = {
            'last_edit_mode': 'EPSP_slope',
            'EPSP_slope_size_default': 0.0003,
            'EPSP_slope_method_default': {},
            'EPSP_slope_params_default': {},
            'volley_slope_size_default': 0.0001,
            'volley_slope_method_default': {},
            'volley_slope_params_default': {},
        }
        self.zoom = {
            'mean_xlim': (0.006, 0.020),
            'mean_ylim': (-0.001, 0.0002),
            'output_xlim': (0, None),
            'output_ax1_ylim': (0, None),
            'output_ax2_ylim': (0, None),
        }
        self.mod = { # settings for "modules" TODO: load from list of modules
            'norm_EPSP': False,
            'norm_EPSP_on': [0, 0],
            'paired_stims': False,            
        }     

    def list_keys(self): # returns a list of keys from show and mod
        return [key for dict in [self.show, self.mod] for key in dict.keys()]

    def dict_states(self): # return concatenated dicts of show and mod
        return {**self.show, **self.mod}
    
    def load_cfg(self, dict_cfg): # load state from project config file
        show = self.show
        for key in show.keys():
            show[key] = dict_cfg[key]
        for key in self.mod.keys():
            self.mod[key] = dict_cfg[key]

    def update_cfg(self, dict_cfg): # save state to project config file
        show = self.show
        for key in show.keys():
            dict_cfg[key] = show[key]
        for key in self.mod.keys():
            dict_cfg[key] = self.mod[key]
        return dict_cfg
   
    def ampView(self):
        show = self.show
        return (show['EPSP_amp'] or show['volley_amp'])
    
    def slopeView(self):
        show = self.show
        return (show['EPSP_slope'] or show['volley_slope'])
    
    def anyView(self):
        show = self.show
        return any(show.values())
    

if __name__ == "__main__":
    # test instantiation
    uistate = UIstate()
    assert uistate.anyView() == False
    uistate.show['EPSP_amp'] = True
    assert uistate.anyView() == True
    print("test passed")
    
