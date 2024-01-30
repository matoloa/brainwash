class UIstate:
    def __init__(self):
        self.aspect = {
        'EPSP_amp': False,
        'EPSP_slope': False,
        'volley_amp': False,
        'volley_slope': False
        }

    def loopConnectViews(self, uisub):
        aspect = self.aspect
        for key in aspect.keys():
            key_checkBox = getattr(uisub, f"checkBox_aspect_{key}")
            key_checkBox.setChecked(aspect[key])
            print(f"loopConnectViews_{key} {aspect[key]}, checkBox_aspect_{key}")
            key_checkBox.stateChanged.connect(lambda state: self.viewSettingsChanged(uisub, key, state))

    def viewSettingsChanged(self, uisub, key, state):
        aspect = self.aspect
        uisub.usage(f"viewSettingsChanged_{key}")
        aspect[key] = (state == 2)
        print(f"viewSettingsChanged_{key} {aspect[key]}")
        uisub.setGraph()
    
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
    
