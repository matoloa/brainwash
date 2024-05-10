import pandas as pd
import pickle

class UIstate:
    def __init__(self):
        self.reset()

    def reset(self): # (re)set all persisted states
        print("UIstate: reset")
        self.version = "0.0.0"
        self.colors = ['#8080FF', '#FF8080', '#CCCC00', '#FF80FF', '#80FFFF', '#FFA500', '#800080', '#0080FF', '#800000']
        self.df_groups = pd.DataFrame(columns=['group_ID', 'group_name', 'color', 'show'])
        self.splitter = {
            'h_splitterMaster': [0.105, 0.04, 0.795, 0.09],
            'v_splitterGraphs': [0.2, 0.5, 0.3],
        }
        self.viewTools = {
            'frameToolStim': ["Stim detection", True],
            'frameToolAspect': ["Aspect toggles", True],
            'frameToolScaling': ["Output Scaling", True],
            'frameToolPairedStim': ["Paired stims", False],
            'frameToolExport': ["Image Export", False],
        }

        self.checkBox = { # these are cycled by uisub.connectUIstate; maintain format!
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
        self.x_select = { # selected ranges on mean- and output graphs
            'mean_start': None,
            'mean_end': None,
            'output_start': None,
            'output_end': None,
        }
        self.zoom = {
            'mean_xlim': (0, 1),
            'mean_ylim': (-1, 1),
            'event_xlim': (0.006, 0.020),
            'event_ylim': (-0.001, 0.0002),
            'output_xlim': (0, None),
            'output_ax1_ylim': (0, 1.2),
            'output_ax2_ylim': (0, 1.2),
        }
        self.default = { # default values for df_project
            't_volley_slope_width': 0.0003,
            't_volley_slope_halfwidth': 0.0001,
            't_volley_slope_method': 'auto detect',
            't_volley_slope_params': 'NA',
            't_volley_amp_method': 'auto detect',
            't_volley_amp_params': 'NA',
            't_EPSP_slope_width': 0.0007,
            't_EPSP_slope_halfwidth': 0.0003,
            't_EPSP_slope_method': 'auto detect',
            't_EPSP_slope_params': 'NA',
            't_EPSP_amp_method': 'auto detect',
            't_EPSP_amp_params': 'NA',
        }

    # Do NOT persist these
        self.axm = None # axis of mean graph (top)
        self.axe = None # axis of event graph (middle)
        self.ax1 = None # axis of output for amplitudes (bottom graph)
        self.ax2 = None # axis of output for slopes (bottom graph)
        self.rec_select = [] # list of selected indices in uisub.tableProj
        self.stim_select = [0] # list of selected indices in uisub.tableStim; default to first
        self.dfp_row_copy = None # copy of selected row in uisub.tableProj
        self.dft_row_copy = None # copy of dft for storing measure points until either saved or rejected
        self.df_recs2plot = None # df_project copy, filtered to selected AND parsed recordings (or all parsed, if none are selected)
        self.dict_rec_label_ID_line_axis = {} # dict of all plotted recording lines: key=label(str), value=[rec_ID(str), 2Dline(object), axes(str)]
        self.dict_group_label_ID_line_SEM = {} # dict of all plotted groups: key=label, value=[group_ID, 2Dline object, fill]
        self.new_indices = [] # list of indices in uisub.df_project for freshly parsed recordings; used by uisub.graphPreload()
        self.darkmode = False # set by global bw cfg

    # Mouseover variables
        self.mouseover_action = None # name of action to take if clicked at current mouseover: EPSP amp move, EPSP slope move/resize, volley amp move, volley slope move/resize
        self.mouseover_plot = None # plot of tentative EPSP slope
        self.mouseover_blob = None # scatterplot indicating mouseover of dragable point; move point or resize slope
        self.x_margin = None # for mouseover detection boundaries
        self.y_margin = None # for mouseover detection boundaries
        self.x_on_click = None # x-value closest to mousebutton down
        self.x_drag_last = None # last x-value within the same dragging event; prevents needless update when holding drag still
        self.x_drag = None # x-value of current dragging
        self.dragging = False # True if dragging; allows right-click to cancel drag
        self.mouseover_out = None # output of dragged aspect

        # Mouseover coordinates, for plotting. Set on row selection.
        self.EPSP_amp_xy = None # x,y
        self.EPSP_slope_start_xy = None # x,y
        self.EPSP_slope_end_xy = None # x,y
        self.volley_amp_xy = None # x,y
        self.volley_slope_start_xy = None # x,y
        self.volley_slope_end_xy = None # x,y

        # Mouseover clickzones: coordinates including margins. Set on row selection.
        self.EPSP_amp_move_zone = {} # dict: key=x,y, value=start,end. 
        self.EPSP_slope_move_zone = {} # dict: key=x,y, value=start,end.
        self.EPSP_slope_resize_zone = {} # dict: key=x,y, value=start,end.
        self.volley_amp_move_zone = {} # dict: key=x,y, value=start,end. 
        self.volley_slope_move_zone = {} # dict: key=x,y, value=start,end.
        self.volley_slope_resize_zone = {} # dict: key=x,y, value=start,end.

    def setMargins(self, axe, pixels=10): # set margins for mouseover detection
        self.x_margin = axe.transData.inverted().transform((pixels, 0))[0] - axe.transData.inverted().transform((0, 0))[0]
        self.y_margin = axe.transData.inverted().transform((0, pixels))[1] - axe.transData.inverted().transform((0, 0))[1]

    def updateDragZones(self, aspect=None, x=None, y=None):
        if aspect is None:
            aspect = self.mouseover_action
            x = self.mouseover_plot[0].get_xdata()
            y = self.mouseover_plot[0].get_ydata()
        else:
            self.mouseover_action = aspect

        if self.mouseover_action.startswith("EPSP slope"):
            self.updateSlopeZone('EPSP', x, y)
        elif self.mouseover_action.startswith("volley slope"):
            self.updateSlopeZone('volley', x, y)

        if aspect is None:
            aspect = self.mouseover_action
            x, y = self.mouseover_blob.get_offsets()[0].tolist()
        else:
            self.mouseover_action = aspect

        if aspect == "EPSP amp move":
            self.updateAmpZone('EPSP', x, y)
        elif aspect == "volley amp move":
            self.updateAmpZone('volley', x, y)

    def updateSlopeZone(self, type, x, y):
        slope_start = x[0], y[0]
        slope_end = x[-1], y[-1]
        x_window = min(x), max(x)
        y_window = min(y), max(y)

        setattr(self, f'{type}_slope_start_xy', slope_start)
        setattr(self, f'{type}_slope_end_xy', slope_end)
        getattr(self, f'{type}_slope_move_zone')['x'] = x_window[0]-self.x_margin, x_window[-1]+self.x_margin
        getattr(self, f'{type}_slope_move_zone')['y'] = y_window[0]-self.y_margin, y_window[-1]+self.y_margin
        getattr(self, f'{type}_slope_resize_zone')['x'] = x[-1]-self.x_margin, x[-1]+self.x_margin
        getattr(self, f'{type}_slope_resize_zone')['y'] = y[-1]-self.y_margin, y[-1]+self.y_margin

    def updateAmpZone(self, type, x, y):
        amp_xy = x, y
        amp_move_zone = x-self.x_margin, x+self.x_margin, y-self.y_margin, y+self.y_margin

        setattr(self, f'{type}_amp_xy', amp_xy)
        getattr(self, f'{type}_amp_move_zone')['x'] = amp_move_zone[0], amp_move_zone[1]
        getattr(self, f'{type}_amp_move_zone')['y'] = amp_move_zone[2], amp_move_zone[3]

    def updatePointDragZone(self, aspect=None, x=None, y=None):
        if aspect is None:
            aspect = self.mouseoverAction
            x, y = self.mouseover_blob.get_offsets()[0].tolist()
        else:
            self.mouseoverAction = aspect

        if aspect == "EPSP amp move":
            self.updateAmpZone('EPSP', x, y)
        elif aspect == "volley amp move":
            self.updateAmpZone('volley', x, y)

    def get_recSet(self): # returns a set of all rec IDs that are currently plotted
        return set([value[0] for value in self.dict_rec_label_ID_line_axis.values()])

    def get_groupSet(self): # returns a set of all group IDs that are currently plotted
        return set([value[0] for value in self.dict_group_label_ID_line_SEM.values()])

    def to_axm(self): # dict of lines that are supposed to be on axm - label: index
        df = self.df_recs2plot
        axm = {}
        for index, row in df.iterrows():
            rec_filter = row['filter']
            if rec_filter != 'voltage':
                key = f"mean {row['recording_name']} ({rec_filter})"
            else:
                key = f"mean {row['recording_name']}"
            axm[key] = index
            for stim in range(1, row['stims'] + 1):
                axm[f"mean {key}, stim {stim} marker"] = index
        return axm

    def to_axe(self): # dict of lines that are supposed to be on axe - label: index
        df = self.df_recs2plot
        axe = {}
        for index, row in df.iterrows():
            rec_filter = row['filter']
            if rec_filter != 'voltage':
                key = f"{row['recording_name']} ({rec_filter})"
            else:
                key = row['recording_name']
            if self.checkBox['EPSP_amp']:
                axe[f"{key} EPSP amp marker"] = index
            if self.checkBox['EPSP_slope']:
                axe[f"{key} EPSP slope marker"] = index
            if self.checkBox['volley_amp']:
                axe[f"{key} volley amp marker"] = index
            if self.checkBox['volley_slope']:
                axe[f"{key} volley slope marker"] = index
            axe[key] = index
        return axe

    def to_ax1(self): # dict of lines that are supposed to be on ax1 - label: index
        df = self.df_recs2plot
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

    def to_ax2(self): # dict of lines that are supposed to be on ax2 - label: index
        df = self.df_recs2plot
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
                'colors': self.colors,
                'df_groups': self.df_groups,
                'splitter': self.splitter,
                'viewTools': self.viewTools,
                'checkBox': self.checkBox,
                'lineEdit': self.lineEdit,
                'zoom': self.zoom,
                'default': self.default,
            }
        except KeyError:
            self.reset()
    
    def set_state(self, state):
        self.version = state.get('version')
        self.colors = state.get('colors')
        self.df_groups = state.get('df_groups')
        self.splitter = state.get('splitter')
        self.viewTools = state.get('viewTools')
        self.checkBox = state.get('checkBox')
        self.lineEdit = state.get('lineEdit')
        self.zoom = state.get('zoom')
        self.default = state.get('default')

    def load_cfg(self, projectfolder, bw_version, force_reset=False): # load state from project config file
        path_pkl = projectfolder / "cfg.pkl"
        if path_pkl.exists() and not force_reset:
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
