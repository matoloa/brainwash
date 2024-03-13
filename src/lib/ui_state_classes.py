import pickle

class UIstate:
    def __init__(self):
        self.reset()

    def reset(self): # reset all states to False
        self.version = "0.0.0"
        self.margin = 0.5 # extra space, relative to data range, to include in mouseover zone
        self.axm = [] # list of items that are supposed to be on axm
        self.ax1 = [] # list of items that are supposed to be on ax1
        self.ax2 = [] # list of items that are supposed to be on ax2
        self.changed = [] # these need to be updated, even if they are already on an axis
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
            'output_ax1_ylim': (0, 1.2),
            'output_ax2_ylim': (0, 1.2),
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
        # Do NOT persist these
        self.selected = [] # list of selected indices
        self.plotted = {} # dict: key=name (meanplot), value=[subplots]
        self.row_copy = None # copy of selected row from df_project
        self.mouseover_aspect = None # name of mouseovered aspect
        self.mouseover_plot = None # plot of mouseovered aspect
        self.mouseover_out = None # output of dragged aspect
        self.dragging = False # dragging state
        self.EPSP_slope_zone = {} # dict: key=x,y, value=start,end. clickzone: including margin. Set upon selection.
        self.EPSP_slope_range = {} # dict: key=x,y, value=min,max. Set upon selection.

    def updateSlopeDrag(self, t=None, xdata=None, ydata=None): # update slope drag zone
        # if xdata or ydata are None, use the current mouseover_plot
        if xdata is None or ydata is None:
            x = self.mouseover_plot[0].get_xdata()
            y = self.mouseover_plot[0].get_ydata()
        else:
            x = xdata
            y = ydata
        x_window = min(x), max(x)
        y_window = min(y), max(y)
        x_margin = (max(x)-min(x)) * self.margin
        y_margin = (max(y)-min(y)) * self.margin
        self.EPSP_slope_range['x'] = x
        self.EPSP_slope_range['y'] = y
        self.EPSP_slope_zone['x'] = x_window[0]-x_margin, x_window[1]+x_margin
        self.EPSP_slope_zone['y'] = y_window[0]-y_margin, y_window[1]+y_margin
        if t is not None:
            self.row_copy['t_EPSP_slope'] = t

    def to_axm(self, df): # lines that are supposed to be on axm - label: index
        axm = {}
        for index, row in df.iterrows():
            rec_filter = row['filter']
            if rec_filter != 'voltage':
                key = f"{row['recording_name']} ({rec_filter})"
            else:
                key = row['recording_name']
            if self.checkBox['EPSP_amp']:
                axm[f"{key} EPSP amp marker"] = index
            if self.checkBox['EPSP_slope']:
                axm[f"{key} EPSP slope marker"] = index
            if self.checkBox['volley_amp']:
                axm[f"{key} volley amp marker"] = index
            if self.checkBox['volley_slope']:
                axm[f"{key} volley slope marker"] = index
            axm[key] = index
        return axm

    def to_ax1(self, df):
        ax1 = {}
        for index, row in df.iterrows():
            key = row['recording_name']
            if self.checkBox['norm_EPSP']:
                norm = " norm"
            else:
                norm = ""
            if self.checkBox['EPSP_amp']:
                ax1[f"{key} EPSP amp{norm}"] = index
            if self.checkBox['volley_amp']:
                ax1[f"{key} volley amp mean"] = index
            ax1[key] = index
        return ax1

    def to_ax2(self, df):
        ax2 = {}
        for index, row in df.iterrows():
            key = row['recording_name']
            if self.checkBox['norm_EPSP']:
                norm = " norm"
            else:
                norm = ""
            if self.checkBox['EPSP_slope']:
                ax2[f"{key} EPSP slope{norm}"] = index
            if self.checkBox['volley_slope']:
                ax2[f"{key} volley slope mean"] = index
            ax2[key] = index
        return ax2

    def get_state(self):
        try:
            return {
                'version': self.version,
                'selected': self.selected,
                'axm': self.axm,
                'ax1': self.ax1,
                'ax2': self.ax2,
                'changed': self.changed,
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
        self.axm = state.get('axm')
        self.ax1 = state.get('ax1')
        self.ax2 = state.get('ax2')
        self.changed = state.get('changed')
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
        with open(path_pkl, 'wb') as f:
            pickle.dump(data, f)

    def ampView(self):
        show = self.checkBox
        return (show['EPSP_amp'])
    
    def slopeView(self):
        show = self.checkBox
        return (show['EPSP_slope'])
    
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
    
