class UIstate:
    def __init__(self):
        self.aspect = {
            'EPSP_amp': False,
            'EPSP_slope': False,
            'volley_amp': False,
            'volley_slope': False,
        }
        self.mod = { # settings for "modules" TODO: load from list of modules
            'norm_EPSP': False,
            'paired_stims': False,
        }     
#             'norm_EPSP_onset': [0, 0],

    def list_keys(self): # returns a list of keys from aspect and mod
        return [key for dict in [self.aspect, self.mod] for key in dict.keys()]

    def dict_states(self): # return concatenated dicts of aspect and mod
        return {**self.aspect, **self.mod}
    
    def load_cfg(self, dict_cfg): # load state from project config file
        aspect = self.aspect
        for key in aspect.keys():
            aspect[key] = dict_cfg[key]
        for key in self.mod.keys():
            self.mod[key] = dict_cfg[key]

    def update_cfg(self, dict_cfg): # save state to project config file
        aspect = self.aspect
        for key in aspect.keys():
            dict_cfg[key] = aspect[key]
        for key in self.mod.keys():
            dict_cfg[key] = self.mod[key]
        return dict_cfg
   
    def ampView(self):
        aspect = self.aspect
        return (aspect['EPSP_amp'] or aspect['volley_amp'])
    
    def slopeView(self):
        aspect = self.aspect
        return (aspect['EPSP_slope'] or aspect['volley_slope'])
    
    def anyView(self):
        aspect = self.aspect
        return any(aspect.values())
    

if __name__ == "__main__":
    # test instantiation
    uistate = UIstate()
    assert uistate.anyView() == False
    uistate.aspect['EPSP_amp'] = True
    assert uistate.anyView() == True
    print("test passed")
    
