class UIstate:
    def __init__(self):
        self.aspect = {
        'EPSP_amp': False,
        'EPSP_slope': False,
        'volley_amp': False,
        'volley_slope': False,
        }
    
    def load(self, uisub):
        aspect = self.aspect
        for key in aspect.keys():
            dict_key = f"aspect_{key}"
            aspect[key] = uisub.dict_cfg[dict_key]
            key_checkBox = getattr(uisub, f"checkBox_aspect_{key}")
            key_checkBox.setChecked(aspect[key])
            key_checkBox.stateChanged.connect(lambda state, key=key: self.viewSettingsChanged(uisub, key, state))

    def viewSettingsChanged(self, uisub, key, state):
        aspect = self.aspect
        uisub.usage(f"viewSettingsChanged_{key}")
        aspect[key] = (state == 2)
        print(f"viewSettingsChanged_{key} {aspect[key]}")
        uisub.setGraph()
        self.persist(uisub)
    
    def ampView(self):
        aspect = self.aspect
        return (aspect['EPSP_amp'] or aspect['volley_amp'])
    
    def slopeView(self):
        aspect = self.aspect
        return (aspect['EPSP_slope'] or aspect['volley_slope'])
    
    def anyView(self):
        aspect = self.aspect
        return any(aspect.values())
    
    def persist(self, uisub): # save state to project config file
        aspect = self.aspect
        for key in aspect.keys():
            dict_key = f"aspect_{key}"
            uisub.dict_cfg[dict_key] = aspect[key]
        uisub.write_project_cfg()
        

if __name__ == "__main__":
    # test instantiation
    uistate = UIstate()
    assert uistate.anyView() == False
    uistate.aspect['EPSP_amp'] = True
    assert uistate.anyView() == True
    print("test passed")
    
