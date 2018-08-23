#!/usr/bin/env python
"""----------------------------------------------------------------------------
   config2json.py:

   Copyright (C) 2018-2018 Wilhelm Duembeg

   This file is part of gsat. gsat is a cross-platform GCODE debug/step for
   Grbl like GCODE interpreters. With features similar to software debuggers.
   Features such as breakpoint, change current program counter, inspection
   and modification of variables.

   gsat is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation, either version 2 of the License, or
   (at your option) any later version.

   gsat is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with gsat.  If not, see <http://www.gnu.org/licenses/>.

----------------------------------------------------------------------------"""

import os
import sys
from optparse import OptionParser

try:
    import simplejson as json
except ImportError:
    import json

import wx

__appname__ = "config to JSON"

__description__ = \
    "converts a gsat config file to JSON format"

__version_info__ = (1, 0, 0)
__version__ = 'v%i.%i.%i' % __version_info__
__revision__ = __version__


def get_cli_params():
    ''' define, retrieve and error check command line interface (cli) params
    '''

    usage = \
        "usage: %prog [options]"

    parser = OptionParser(usage=usage, version="%prog " + __revision__)
    parser.add_option("-c", "--config",
                      dest="config",
                      default=None,
                      help="Use alternate configuration file name, location "
                      "will be in HOME folder regardless of file name.",
                      metavar="FILE")

    parser.add_option("-o", "--outfile",
                      dest="outfile",
                      default=None,
                      help="output file name (optional, if missing will use "
                           "sdtout)",
                      metavar="FILE")

    (options, args) = parser.parse_args()

    if options.config is None:
        parser.error("missing option -c")

    return (options, args)


class toolJsonData():
    """ Provides various data information
    """
    configDefault = {
        "cli": {
            "CmdHistory": "",
            "CmdMaxHistory": 100,
            "SaveCmdHistory": True,
        },
        "code": {
            "AutoScroll": 3,
            "AxisHighlight": "#ff0000",
            "CaretLine": True,
            "CaretLineBackground": "#EFEFEF",
            "CaretLineForeground": "#000000",
            "CommentsHighlight": "#007F00",
            "GCodeHighlight": "#0000ff",
            "GCodeLineNumberHighlight": "#BFBFBF",
            "LineNumber": True,
            "LineNumberBackground": "#99A9C2",
            "LineNumberForeground": "#000000",
            "MCodeHighlight": "#7f007f",
            "Parameters2Highlight": "#f4b730",
            "ParametersHighlight": "#ff0000",
            "ReadOnly": True,
            "WindowBackground": "#FFFFFF",
            "WindowForeground": "#000000"
        },
        "cv2": {
            "CaptureDevice": 0,
            "CaptureHeight": 480,
            "CapturePeriod": 100,
            "CaptureWidth": 640,
            "Crosshair": True,
            "Enable": False
        },
        "jogging": {
            "AutoMPOS": False,
            "Custom1Label": "Custom 1",
            "Custom1Script": "",
            "Custom2Label": "Custom 2",
            "Custom2Script": "",
            "Custom3Label": "Custom 3",
            "Custom3Script": "",
            "Custom4Label": "Custom 4",
            "Custom4Script": "",
            "JogFeedRate": 1000,
            "NumKeypadPendant": False,
            "ProbeDistance": 19.6,
            "ProbeFeedRate": 100.0,
            "ProbeMaxDistance": -40.0,
            "RapidJog": True,
            "ReqUpdateOnJogSetOp": True,
            "SpindleSpeed": 12000,
            "XYZReadOnly": False,
            "ZJogSafeMove": False
        },
        "machine": {
            "AutoRefresh": True,
            "AutoRefreshPeriod": 200,
            "AutoStatus": False,
            "Baud": "115200",
            "Device": "grbl",
            "InitScript": "",
            "InitScriptEnable": True,
            "Port": ""
        },
        "mainApp": {
            "BackupFile": True,
            "DisplayRunTimeDialog": True,
            "RoundInch2mm": 4,
            "Roundmm2Inch": 4,
            "FileHistory": {
                "MaxFiles": 10,
            },
        },
        "output": {
            "AutoScroll": 2,
            "CaretLine": False,
            "CaretLineBackground": "#C299A9",
            "CaretLineForeground": "#000000",
            "LineNumber": False,
            "LineNumberBackground": "#FFFFFF",
            "LineNumberForeground": "#000000",
            "ReadOnly": False,
            "WindowBackground": "#FFFFFF",
            "WindowForeground": "#000000"
        }
    }

    def __init__(self, config_fname):

        self.configFileName = config_fname

        self.workingConfigData = dict()
        self.workingConfigData.update(self.configDefault)

    def add(self, key_path, val):
        """ Add new key value pair
        """
        if type(key_path) is list:
            key_list = key_path
        else:
            key_list = key_path.split("/")

            if key_list[0] == "":
                key_list.pop(0)

        node = self.get(key_list[:-1])

        if node is None:
            node = self.workingConfigData

            for key in key_list[:-1]:
                if key in node:
                    node = node[key]
                else:
                    node[key] = dict()
                    node = node[key]

        node[key_list[-1:][0]] = val

    def get(self, key_path, defualt_rv=None):
        """ Get value for a given key
        """
        return_val = defualt_rv

        if type(key_path) is list:
            key_list = key_path
        else:
            key_list = key_path.split("/")

            if key_list[0] == "":
                key_list.pop(0)

        if key_list:
            node = self.workingConfigData

            for key in key_list:
                if key in node:
                    node = node[key]
                else:
                    key = None
                    break

            if key is not None:
                return_val = node

        return return_val

    def set(self, key_path, val):
        """ Set value for a given key
        """
        self.add(key_path, val)

    def load(self):
        """ Load data from config file
        """
        # if file dosen't exist then use default values
        if os.path.exists(self.configFileName):
            datastore = dict()

            with open(self.configFileName, 'r') as f:
                datastore = json.load(f)

            self.workingConfigData.update(datastore)

    def save(self):
        """ Save data to config file
        """
        with open(self.configFileName, 'w') as f:
            json.dump(self.workingConfigData, f, indent=3, sort_keys=True)

    def dump(self):
        data = json.dumps(self.workingConfigData, indent=3, sort_keys=True)
        print data

class toolConfigData():
    """ Provides various data information
    """

    def __init__(self, config_file):
        # -----------------------------------------------------------------------
        # config keys

        self.configFile = config_file

        self.config = {
            #  key                                 CanEval, Default Value
            # main app keys
            '/mainApp/DisplayRunTimeDialog': (True, True),
            '/mainApp/BackupFile': (True, True),
            '/mainApp/MaxFileHistory': (True, 10),
            '/mainApp/RoundInch2mm': (True, 4),
            '/mainApp/Roundmm2Inch': (True, 4),
            # '/mainApp/DefaultLayout/Dimensions' :(False, ""),
            # '/mainApp/DefaultLayout/Perspective':(False, ""),
            # '/mainApp/ResetLayout/Dimensions'   :(False, ""),
            # '/mainApp/ResetLayout/Perspective'  :(False, ""),

            # code keys
            # 0:NoAutoScroll 1:AlwaysAutoScroll 2:SmartAutoScroll
            # 3:OnGoToPCAutoScroll
            '/code/AutoScroll': (True, 3),
            '/code/CaretLine': (True, True),
            '/code/CaretLineForeground': (False, '#000000'),
            # C299A9 #A9C299, 9D99C2
            '/code/CaretLineBackground': (False, '#EFEFEF'),
            '/code/LineNumber': (True, True),
            '/code/LineNumberForeground': (False, '#000000'),
            '/code/LineNumberBackground': (False, '#99A9C2'),
            '/code/ReadOnly': (True, True),
            '/code/WindowForeground': (False, '#000000'),
            '/code/WindowBackground': (False, '#FFFFFF'),
            '/code/GCodeHighlight': (False, '#0000ff'),  # 0000FF'
            '/code/MCodeHighlight': (False, '#7f007f'),  # 742b77
            '/code/AxisHighlight': (False, '#ff0000'),  # 007F00
            '/code/ParametersHighlight': (False, '#ff0000'),
            '/code/Parameters2Highlight': (False, '#f4b730'),
            '/code/GCodeLineNumberHighlight': (False, '#BFBFBF'),
            '/code/CommentsHighlight': (False, '#007F00'),  # FFC300


            # output keys
            # 0:NoAutoScroll 1:AlwaysAutoScroll 2:SmartAutoScroll
            '/output/AutoScroll': (True, 2),
            '/output/CaretLine': (True, False),
            '/output/CaretLineForeground': (False, '#000000'),
            '/output/CaretLineBackground': (False, '#C299A9'),
            '/output/LineNumber': (True, False),
            '/output/LineNumberForeground': (False, '#000000'),
            '/output/LineNumberBackground': (False, '#FFFFFF'),
            '/output/ReadOnly': (True, False),
            '/output/WindowForeground': (False, '#000000'),
            '/output/WindowBackground': (False, '#FFFFFF'),

            # cli keys
            '/cli/SaveCmdHistory': (True, True),
            '/cli/CmdMaxHistory': (True, 100),
            '/cli/CmdHistory': (False, ""),

            # machine keys
            '/machine/Device': (False, "grbl"),
            '/machine/Port': (False, ""),
            '/machine/Baud': (False, "115200"),
            '/machine/AutoStatus': (True, False),
            '/machine/AutoRefresh': (True, False),
            '/machine/AutoRefreshPeriod': (True, 200),
            '/machine/InitScriptEnable': (True, True),
            '/machine/InitScript': (False, ""),

            # jogging keys
            '/jogging/XYZReadOnly': (True, False),
            '/jogging/AutoMPOS': (True, True),
            '/jogging/ReqUpdateOnJogSetOp': (True, True),
            '/jogging/NumKeypadPendant': (True, False),
            '/jogging/ZJogSafeMove': (True, False),
            '/jogging/Custom1Label': (False, "Custom 1"),
            '/jogging/Custom1Script': (False, ""),
            '/jogging/Custom2Label': (False, "Custom 2"),
            '/jogging/Custom2Script': (False, ""),
            '/jogging/Custom3Label': (False, "Custom 3"),
            '/jogging/Custom3Script': (False, ""),
            '/jogging/Custom4Label': (False, "Custom 4"),
            '/jogging/Custom4Script': (False, ""),
            '/jogging/SpindleSpeed': (True, 12000),
            '/jogging/ProbeDistance': (True, 19.6000),
            '/jogging/ProbeMaxDistance': (True, -40.0000),
            '/jogging/ProbeFeedRate': (True, 100.0000),
            '/jogging/JogFeedRate': (True, 1000),
            '/jogging/RapidJog': (True, True),

            # CV2 keys
            '/cv2/Enable': (True, False),
            '/cv2/Crosshair': (True, True),
            '/cv2/CaptureDevice': (True, 0),
            '/cv2/CapturePeriod': (True, 100),
            '/cv2/CaptureWidth': (True, 640),
            '/cv2/CaptureHeight': (True, 480),
        }

    def add(self, key, val, canEval=True):
        """ Add new key value pair
        """
        self.config[key] = (canEval, val)

    def get(self, key):
        """ Get value for a given key
        """
        retVal = None
        if key in self.config.keys():
            configEntry = self.config.get(key)
            retVal = configEntry[1]

        return retVal

    def set(self, key, val):
        """ Set value for a given key
        """
        if key in self.config.keys():
            configEntry = self.config.get(key)
            self.config[key] = (configEntry[0], val)

    def load(self):
        """ Load data from config file
        """
        for key in self.config.keys():
            configEntry = self.config.get(key)
            configRawData = str(self.configFile.Read(key))

            if len(configRawData) > 0:
                if configEntry[0]:
                    configData = eval(configRawData)
                else:
                    configData = configRawData

                self.config[key] = (configEntry[0], configData)

    def save(self):
        """ Save data to config file
        """
        keys = sorted(self.config.keys())
        for key in keys:
            configEntry = self.config.get(key)
            self.configFile.Write(key, str(configEntry[1]))

"""----------------------------------------------------------------------------
   main
----------------------------------------------------------------------------"""
if __name__ == '__main__':

    machifProgExec = None
    gcodeFileLines = []
    (cmd_line_options, cli_args) = get_cli_params()

    # print "Config File = [%s]" % cmd_line_options.config
    # print "Out File = [%s]" % cmd_line_options.outfile

    configFile = wx.FileConfig("gsat",
                               localFilename=cmd_line_options.config,
                               style=wx.CONFIG_USE_LOCAL_FILE)

    configJson = toolJsonData(cmd_line_options.outfile)
    config = toolConfigData(configFile)
    config.load()

    # now special handle a few things
    for key in config.config:
        if key not in ['/mainApp/MaxFileHistory']:
            val = config.get(key)
            configJson.set(key, val)
        else:
            if key == '/mainApp/MaxFileHistory':
                val = config.get(key)
                configJson.set("/mainApp/FileHistory/FilesMaxHistory", val)

                for i in range(1, val + 1):
                    fname = configFile.Read("file%d" % i)
                    if fname:
                        configJson.add("/mainApp/FileHistory/File%d"
                                       % i, fname)

    # other things...
    val = configFile.Read("/mainApp/ResetLayout/Dimensions")
    if val:
        configJson.add("/mainApp/Layout/Reset/Dimensions", val)

    val = configFile.Read("/mainApp/ResetLayout/Perspective")
    if val:
        configJson.add("/mainApp/Layout/Reset/Perspective", val)

    val = configFile.Read("/mainApp/DefaultLayout/Dimensions")
    if val:
        configJson.add("/mainApp/Layout/Default/Dimensions", val)

    val = configFile.Read("/mainApp/DefaultLayout/Perspective")
    if val:
        configJson.add("/mainApp/Layout/Default/Perspective", val)

    if cmd_line_options.outfile is None:
        configJson.dump()
    else:
        configJson.save()
