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

    
    def load_cfg(self, dict_cfg): # load state from project config file
        aspect = self.aspect
        for key in aspect.keys():
            aspect[key] = dict_cfg[key]
            # key_checkBox = getattr(uisub, f"checkBox_aspect_{key}")
            # key_checkBox.setChecked(aspect[key])
            # key_checkBox.stateChanged.connect(lambda state, key=key: self.viewSettingsChanged(uisub, key, state))
        #for key in self.mod.keys():
        #    self.mod[key] = dict_cfg[key]
            # key_checkBox = getattr(uisub, f"checkBox_{key}")
            # key_checkBox.setChecked(self.mod[key])
            # key_checkBox.stateChanged.connect(lambda state, key=key: self.modSettingsChanged(uisub, key, state))

   
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
    
