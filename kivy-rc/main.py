"""----------------------------------------------------------------------------
   main.py

   Copyright (C) 2021 Wilhelm Duembeg

   gsatrc kivy

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

import sys
import os
import time
import random
import hashlib
import queue
import threading

# from kivy.lang import Builder
from kivy.config import Config
from kivy.utils import platform
from kivy.metrics import sp, dp, mm

# dealing with some issue on scheduling events, coming
# from networking thread, interrupt mode is faster
Config.set('graphics', 'KIVY_CLOCK', 'interrupt')

if platform != 'android':
    Config.set('kivy', 'window_icon', 'gsat-rc-32x32.png')
    # Config.set('kivy','icon','gsat-rc-32x32.png')

    # Lenovo M8 Tablet 1280 x 800
    # Config.set('graphics', 'width', '800')
    # Config.set('graphics', 'height', '1280')
    Config.set('graphics', 'width', '1280')
    Config.set('graphics', 'height', '800')

    # Nexus 7       1920 x 1200
    # Config.set('graphics', 'width', '1920')
    # Config.set('graphics', 'height', '1200')
    # Config.set('graphics', 'width', '1200')
    # Config.set('graphics', 'height', '1920')

    # Amazon HD7    1024 x 600
    # Config.set('graphics', 'width', '1024')
    # Config.set('graphics', 'height', '600')
    # Config.set('graphics', 'width', '600')
    # Config.set('graphics', 'height', '1024')

    # Amazon HD8    1280 x 800
    # Config.set('graphics', 'width', '1280')
    # Config.set('graphics', 'height', '800')
    # Config.set('graphics', 'width', '800')
    # Config.set('graphics', 'height', '1280')

from kivymd.app import MDApp
from kivymd.uix.screen import Screen
from kivymd.uix.boxlayout import MDBoxLayout
# from kivymd.uix.floatlayout import FloatLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.button import MDFlatButton, MDIconButton  # , MDRectangleFlatButton, , MDRoundImageButton
from kivymd.uix.textfield import MDTextField  # , MDTextFieldRect
from kivymd.uix.list import MDList, OneLineListItem, TwoLineListItem, OneLineIconListItem
# from kivymd.uix.dropdownitem import MDDropDownItem
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.list import IRightBodyTouch, IconLeftWidget
from kivymd.uix.selectioncontrol import MDCheckbox  # , MDSwitch
from kivymd.uix.dialog import MDDialog
from kivymd.theming import ThemeManager
from kivymd.toast import toast
from kivymd.uix.label import MDLabel

# from kivy.uix.anchorlayout import AnchorLayout
# from kivy.uix.scrollview import ScrollView
from kivy.properties import ObjectProperty, BooleanProperty, StringProperty
from kivy.clock import Clock, mainthread
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.factory import Factory

if platform == 'android':
    from jnius import autoclass
    from android.runnable import run_on_ui_thread

    # Import Android-specific classes
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    WindowManager = autoclass('android.view.WindowManager')
    LayoutParams = autoclass('android.view.WindowManager$LayoutParams')
    Version = autoclass("android.os.Build$VERSION")
    Version_codes = autoclass("android.os.Build$VERSION_CODES")


from modules.version_info import *
import modules.config as gc
import modules.remote_client as rc


def no_machine_detected():
    toast("There is no machine connected/detected")


def jog_not_permitted_run_state():
    toast("JOG operations not permitted while in RUN state")


class TextInputTouchScroll(TextInput):
    max_lines = ObjectProperty(None)
    max_text = ObjectProperty(None)
    max_text_backoff = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(TextInputTouchScroll, self).__init__(**kwargs)

    def on_touch_down(self, touch):
        if platform != 'android':
            super(TextInputTouchScroll, self).on_touch_down(touch)
        else:
            pass

    # @mainthread
    def append_text(self, str_data, from_undo=False):
        """
        Append text to end of self.text

        """
        try:
            # self.text = "".join([self.text, str_data])
            self.readonly = False
            self.do_cursor_movement('cursor_end', control=True)
            self.insert_text(str_data, False)
            # self.do_cursor_movement('cursor_end', control=True)
            # self.insert_text("** text_size: {}\n".format(len(self.text_out.text)), False)
            self.readonly = True

            if len(self.text) > self.max_text:
                # before = len(self.text)
                self.text = self.text[-(self.max_text-self.max_text_backoff):]
                # print ("Before: {}".format(before))
                # print ("After: {}".format(len(self.text)))
                self.height -= self.line_height

        except:
            # sometimes while rotating screen and heavy output exceptions might
            # happen, ignore since this is a bets effort output window
            pass

    def insert_text(self, substring, from_undo=False):
        super(TextInputTouchScroll, self).insert_text(substring, from_undo)


class InputDialogContent(MDBoxLayout):
    """
    General config custom input dialog content

    """

    value = ObjectProperty(None)
    # enter = ObjectProperty(None)

    def __init__(self, val, **kwargs):
        """
        Init function for object

        """
        super(InputDialogContent, self).__init__(**kwargs)
        self.value = val
        self.register_event_type('on_enter')

        Clock.schedule_once(self.on_init)
        # self.on_init()

    def on_init(self, *args):
        # self.ids.text_field.focus = True
        self.ids.text_field.text = self.value

    def on_number_button_release(self, instance):
        """
        Replace txt field with button text

        """
        self.ids.text_field.text = instance.text
        self.value = self.ids.text_field.text
        # self.ids.text_field.focus = True

    def on_open(self, instance):
        Clock.schedule_once(self.on_open_after, 0.1)
        # self.ids.text_field.focus = True

    def on_open_after(self, *args):
        self.ids.text_field.focus = True

    def on_text_validate(self, instance):
        self.value = instance.text
        self.dispatch('on_enter')
        # self.enter = True
        # self.enter = False

    def on_enter(self, *args):
        pass


class StepSizeDialogContent(InputDialogContent):
    """
    Step size config custom dialog content

    """

    def on_init(self, *args):
        super(StepSizeDialogContent, self).on_init(args)

        self.height = "200dp"
        self.ids.text_field.input_filter = 'float'

        for bt_text in ['0.1', '0.5', '1', '5', '10', '20', '50', '100', '150', '200', '400', '500']:
            bt = MDFlatButton(
                text=bt_text, on_release=self.on_number_button_release,
                text_color=MDApp.get_running_app().theme_cls.primary_color)
            self.ids.step_size_buttons.add_widget(bt)

        self.size_hint_y = None
        bt = MDFlatButton(text='dummy', on_release=self.on_number_button_release)

    def on_number_button_release(self, instance):
        super(StepSizeDialogContent, self).on_number_button_release(instance)
        self.on_text_validate(instance)


class ServerDialogContent(InputDialogContent):
    """
    Server config custom dialog content

    """

    def __init__(self, hostname, tcp_port, udp_port, use_udp_broadcast, **kwargs):
        """
        Init function for object

        """
        self.hostname = hostname
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.use_udp_broadcast = use_udp_broadcast
        super(ServerDialogContent, self).__init__(hostname, **kwargs)

    def on_init(self, *args):
        super(ServerDialogContent, self).on_init(args)

        self.height = "240dp"
        self.ids.text_field.input_filter = None
        self.ids.text_field.input_type = 'text'
        self.ids.text_field.hint_text = "Server Hostname"
        self.tf_server = self.ids.text_field

        tf = MDTextField()
        tf.text = self.tcp_port
        tf.hint_text = "TCP Port"
        tf.input_type = 'number'
        tf.input_filter = 'int'
        tf.on_text_validate = self.on_text_validate
        self.tf_tcp_port = tf
        self.add_widget(tf)

        tf = MDTextField()
        tf.text = self.udp_port
        tf.hint_text = "UDP Port"
        tf.input_type = 'number'
        tf.input_filter = 'int'
        tf.on_text_validate = self.on_text_validate
        self.tf_udp_port = tf
        self.add_widget(tf)

        bl = MDBoxLayout()
        cb_l = MDLabel(text="Use UDP Broadcast")
        cb_l.size_hint_x = None
        cb_l.width = cb_l.text_size[0] + 48
        bl.add_widget(cb_l)
        cb = MDCheckbox(pos_hint={'left': 1})
        cb.active = self.use_udp_broadcast
        cb.size_hint_x = None
        cb.width = "48dp"
        self.cb_use_udp_broadcast = cb
        bl.add_widget(cb)
        self.add_widget(bl)


class OneListItemWithCheckbox(OneLineListItem):
    """
    Custom list item.

    """


class TwoListItemWithCheckbox(TwoLineListItem):
    """
    Custom list item.

    """


class RightCheckbox(IRightBodyTouch, MDCheckbox):
    """
    Custom right container.

    """


class IconListItem(OneLineIconListItem):
    icon = StringProperty()


class MDBoxLayoutDRO(MDBoxLayout):
    """
    Class to handle DRO panel list items

    """
    rc_connect = ObjectProperty(None)
    server_hostname = ObjectProperty(None)
    server_tcp_port = ObjectProperty(None)
    server_udp_port = ObjectProperty(None)
    server_use_udp_broadcast = ObjectProperty(None)
    serial_port_open = ObjectProperty(None)
    jog_feed_rate = ObjectProperty(None)
    sw_state = ObjectProperty(None)

    def __init__(self, **kwargs):
        """
        Constructor

        """
        super(MDBoxLayoutDRO, self).__init__(**kwargs)

        self.register_event_type('on_display_gcode_filename')

        Clock.schedule_once(self.on_init)
        # self.on_init()

    def init_a_menu(self, data, list_items):
        """
        Init a single menu from data array

        """
        menu_items = []
        for di in data:
            if di:
                if list(di.items())[0][1].endswith(">"):
                    menu_items.append(
                        {
                            "right_content_cls": RightContentCls(
                                icon="menu-right-outline",
                            ),
                            "icon": di['icon'],
                            "text": di['name'],
                            "height": "36dp",
                            "top_pad": "10dp",
                            "bot_pad": "10dp",
                            "divider": None,
                        })
                else:
                    menu_items.append(
                        {
                            "viewclass": "IconListItem",
                            "icon": di['icon'],
                            "text": di['name'],
                            # "font_style": "Caption",
                            # "height": "36dp",
                            # "top_pad": "10dp",
                            # "bot_pad": "10dp",
                            "divider": None,
                            "disable": True,
                            "on_release": lambda x=di['name']: self.menu_callback(x, list_items),
                        })
            else:
                menu_items.append({"viewclass": "MDSeparator", "height": 1})

        # menu = MDDropdownMenu(caller=self, items=menu_items, width_mult=4)
        # menu = MDDropdownMenu(caller=self, items=menu_items, always_release=True)
        # menu = MDDropdownMenu(caller=self, items=menu_items, on_release=self.menu_callback)
        menu = MDDropdownMenu(caller=self, items=menu_items)

        if type(list_items) is not list:
            list_items = [list_items]

        for li in list_items:
            if li in self.list_items:
                self.list_items[li].menu = menu

        return menu

    def init_dialog(self):
        self.server_config_dialog = self.on_init_value_dialog('server_config')
        self.got_to_axis_dialog = self.on_init_value_dialog('got_to_axis')
        self.set_value_axis_dialog = self.on_init_value_dialog('set_value_axis')

        # all axis list items have the same dialog
        for li in self.axis_list_items_dialog:
            if li in self.list_items:
                self.list_items[li].dialog = self.got_to_axis_dialog

    def init_list(self):
        """
        Init MD lists

        """
        # update DRO list
        items = list(self.ids.dro_list.children)
        for li in items:
            self.ids.dro_list.remove_widget(li)

        # update info list
        items = list(self.ids.info_list.children)
        for li in items:
            self.ids.info_list.remove_widget(li)

        for li in self.dro_list_enable:
            self.ids.dro_list.add_widget(self.list_items[li])

        for li in self.info_list_enable:
            self.ids.info_list.add_widget(self.list_items[li])

    def init_menu(self):
        """
        Init menus for the different widgets

        """
        icon = 'icon'
        name = 'name'

        # axis menus
        items = [
            {icon: "home-search-outline", name: "Home Axis"},
            {icon: "numeric-0-circle-outline", name: "Zero Axis"},
            {icon: "tools", name: "Set to value"},
        ]
        self.init_a_menu(items, self.axis_list_items_menu)

        # device menu
        items = [
            {icon: "power-plug", name: "Connect"},
            {icon: "power-plug-off", name: "Disconnect"},
            # {icon: "refresh", name: "Refresh"},
            # {icon: "power", name: "Reset"},
            {icon: "refresh", name: "Reset"},
        ]
        self.init_a_menu(items, 'mi')

        # server menu
        items = [
            {icon: "lan-connect", name: "Connect"},
            {icon: "lan-disconnect", name: "Disconnect"},
            # {icon: "power", name: "Reset"},
            {icon: "refresh", name: "Reset"},
            {icon: "cog-outline", name: "Configure"},
        ]
        self.init_a_menu(items, 'rc')

    def menu_callback(self, menu_text, list_item):
        """
        Menu callback event handler

        """
        if isinstance(list_item, list):
            list_item = list_item[0]

        caller = id(self.list_items[list_item].menu.caller)
        self.list_items[list_item].menu.dismiss()

        # identify instance
        li = ""
        for i in self.list_items:
            if id(self.list_items[i]) == caller:
                li = i
                break

        # handle remote server
        if li == 'rc':
            if menu_text == "Connect":
                self.rc_connect = True
            elif menu_text == "Disconnect":
                self.rc_connect = False
            elif menu_text == "Configure":
                self.value_dialog_data_key = "server_config"
                self.value_dialog = self.server_config_dialog
                self.value_dialog.open()
            elif menu_text == "Reset" and gc.gsatrc_remote_client:
                gc.gsatrc_remote_client.add_event(gc.EV_CMD_RMT_RESET)

        # handle device
        elif li == 'mi' and gc.gsatrc_remote_client:
            if menu_text == "Connect" and not self.serial_port_open:
                gc.gsatrc_remote_client.add_event(gc.EV_CMD_OPEN)
            elif menu_text == "Disconnect" and self.serial_port_open:
                gc.gsatrc_remote_client.add_event(gc.EV_CMD_CLOSE)
            elif menu_text == "Refresh" and self.serial_port_open:
                gc.gsatrc_remote_client.add_event(gc.EV_CMD_GET_STATUS)
            elif menu_text == "Reset" and self.serial_port_open:
                gc.gsatrc_remote_client.add_event(gc.EV_CMD_RESET)

        # handle axis menus
        elif li in self.axis_list_items_menu:
            if self.sw_state in [gc.STATE_RUN] and gc.gsatrc_remote_client:
                jog_not_permitted_run_state()
                return

            if gc.gsatrc_remote_client and self.serial_port_open:
                if menu_text == "Zero Axis":
                    gc.gsatrc_remote_client.add_event(gc.EV_CMD_SET_AXIS, {li.lower(): 0})
                elif menu_text == "Home Axis":
                    gc.gsatrc_remote_client.add_event(gc.EV_CMD_HOME, {li.lower(): 0})
                elif menu_text == "Go to Zero":
                    axis = {li.lower(): 0}
                    if self.jog_feed_rate == "Rapid":
                        gc_cmd = gc.EV_CMD_JOG_RAPID_MOVE
                    else:
                        gc_cmd = gc.EV_CMD_JOG_MOVE
                        axis['feed'] = int(self.jog_feed_rate)
                    gc.gsatrc_remote_client.add_event(gc_cmd, axis)
                elif menu_text == "Set to value":
                    self.value_dialog_data_key = f"set_value_axis:{li}"
                    self.value_dialog = self.set_value_axis_dialog
                    self.value_dialog.title = f"Set axis {li.upper()}"
                    self.value_dialog.open()
            else:
                no_machine_detected()

    def on_display_gcode_filename(self, *args):
        pass

    def on_init(self, *args):
        """
        Init event after construction

        """
        self.axis_list_items_menu = ['X', 'Y', 'Z', 'A', 'B', 'C']
        self.axis_list_items_dialog = ['x', 'y', 'z', 'a', 'b', 'c']
        self.dro_list_enable = ['x', 'z', 'fr', 'pc', 'mi', 'swst']
        self.info_list_enable = ['y', 'a', 'st', 'rt', 'rc', 'gfn']
        self.list_items_enable = list(self.dro_list_enable)
        self.list_items_enable.extend(self.info_list_enable)
        # self.dro_list_enable = ['x', 'y', 'z']
        # self.info_list_enable = ['mi', 'pc', 'rt']

        if (set(self.dro_list_enable) & set(self.info_list_enable)):
            raise Exception("Cannot have same item in multiple MD lists!!")

        self.list_items = {
            'x': self.ids.x_axis,
            'X': self.ids.x_axis_icon,
            'y': self.ids.y_axis,
            'Y': self.ids.y_axis_icon,
            'z': self.ids.z_axis,
            'Z': self.ids.z_axis_icon,
            'a': self.ids.a_axis,
            'A': self.ids.a_axis_icon,
            'b': self.ids.b_axis,
            'B': self.ids.b_axis_icon,
            'c': self.ids.c_axis,
            'C': self.ids.c_axis_icon,
            'fr': self.ids.feed_rate,
            'st': self.ids.status,
            'swst': self.ids.sw_status,
            'mi': self.ids.device,
            'pc': self.ids.gcode_pos,
            'rt': self.ids.run_time,
            'rc': self.ids.remote_server,
            'gfn': self.ids.gcode_fname,
        }

        self.list_items_ids = {id(v): k for k, v in self.list_items.items()}

        for li in self.list_items:
            self.list_items[li].menu = None
            self.list_items[li].dialog = None

        self.server_hostname = MDApp.get_running_app().config.get(__appname__, 'server_hostname')
        self.server_tcp_port = MDApp.get_running_app().config.get(__appname__, 'server_tcp_port')
        self.server_udp_port = MDApp.get_running_app().config.get(__appname__, 'server_udp_port')
        self.server_use_udp_broadcast = MDApp.get_running_app().config.get(__appname__, 'server_use_udp_broadcast')

        self.init_menu()
        self.init_list()
        self.init_dialog()

    def on_init_value_dialog(self, data_key):
        """
        Setup jog step size dialog

        """
        button_text_color = MDApp.get_running_app().theme_cls.primary_color

        dialog_title = ""
        content_cls = None
        value_dialog = None

        if data_key == "server_config":
            content_cls = ServerDialogContent(
                self.server_hostname, self.server_tcp_port, self.server_udp_port, eval(self.server_use_udp_broadcast)
            )
            dialog_title = 'Remote Server'

        elif data_key == "got_to_axis":
            content_cls = InputDialogContent(val="")
            content_cls.ids.text_field.input_filter = 'float'
            content_cls.ids.text_field.input_type = 'number'
            dialog_title = 'Go to Axis'

        elif data_key == "set_value_axis":
            content_cls = InputDialogContent(val="")
            content_cls.ids.text_field.input_filter = 'float'
            content_cls.ids.text_field.input_type = 'number'
            dialog_title = 'Set Axis Value'

        if content_cls is not None:

            dialog_buttons = [
                MDFlatButton(text="CANCEL", text_color=button_text_color, on_release=self.on_value_dialog_cancel),
                MDFlatButton(text="OK", text_color=button_text_color, on_release=self.on_value_dialog_ok),
            ]

            content_cls.bind(on_enter=self.on_value_dialog_value)
            value_dialog = MDDialog(
                title=dialog_title, type='custom', content_cls=content_cls,
                buttons=dialog_buttons, on_open=content_cls.on_open
            )

        # value_dialog.open()
        return value_dialog

    def on_list_item_release(self, instance):
        """
        On list item release event handler

        """
        instance_id = id(instance)
        if instance is not None:
            # print(instance.text, instance.x, instance.y)
            # print(instance.to_window(instance.center_x, instance.center_y), instance.text)
            if instance.menu:
                instance.menu.caller = instance
                instance.menu.open()

            elif instance.dialog:
                self.value_dialog = None
                i = self.list_items_ids.get(instance_id)

                if i in self.axis_list_items_dialog:
                    # is one of the axis items
                    self.value_dialog = self.got_to_axis_dialog
                    self.value_dialog_data_key = f"got_to_axis:{i}"
                    self.value_dialog.title = f"Move axis {i.upper()}"

                if self.value_dialog:
                    self.value_dialog.open()

            else:
                pass
                # print("No menu for this item")

    def on_serial_port_open(self, instance, val):

        if not val:
            self.list_items['rt'].text = ""
            self.list_items['pc'].text = ""
            self.list_items['st'].text = "Stop"
            self.list_items['swst'].text = "Idle"
            self.list_items['mi'].text = ""
            self.list_items['gfn'].text = ""

    def on_server_hostname(self, instance, value):
        value_key = 'server_hostname'
        old_value = MDApp.get_running_app().config.get(__appname__, value_key)
        if value != old_value:
            MDApp.get_running_app().config.set(__appname__, value_key, value)
            MDApp.get_running_app().config.write()

    def on_server_tcp_port(self, instance, value):
        value_key = 'server_tcp_port'
        old_value = MDApp.get_running_app().config.get(__appname__, value_key)
        if value != old_value:
            MDApp.get_running_app().config.set(__appname__, value_key, value)
            MDApp.get_running_app().config.write()

    def on_server_udp_port(self, instance, value):
        value_key = 'server_udp_port'
        old_value = MDApp.get_running_app().config.get(__appname__, value_key)
        if value != old_value:
            MDApp.get_running_app().config.set(__appname__, value_key, value)
            MDApp.get_running_app().config.write()

    def on_server_use_udp_broadcast(self, instance, value):
        value_key = 'server_use_udp_broadcast'
        old_value = MDApp.get_running_app().config.get(__appname__, value_key)
        if value != old_value:
            MDApp.get_running_app().config.set(__appname__, value_key, value)
            MDApp.get_running_app().config.write()

    def on_update(self, sr):
        """
        Update DRO fields

        """
        if 'st' in self.list_items_enable and 'stat' in sr:
            if self.list_items['st'].text != sr['stat']:
                self.list_items['st'].text = sr['stat']

        if 'x' in self.list_items_enable and 'posx' in sr:
            if self.list_items['x'].text != "{:.3f}".format(sr['posx']):
                self.list_items['x'].text = "{:.3f}".format(sr['posx'])

        if 'y' in self.list_items_enable and 'posy' in sr:
            if self.list_items['y'].text != "{:.3f}".format(sr['posy']):
                self.list_items['y'].text = "{:.3f}".format(sr['posy'])

        if 'z' in self.list_items_enable and 'posz' in sr:
            if self.list_items['z'].text != "{:.3f}".format(sr['posz']):
                self.list_items['z'].text = "{:.3f}".format(sr['posz'])

        if 'a' in self.list_items_enable and 'posa' in sr:
            if self.list_items['a'].text != "{:.3f}".format(sr['posa']):
                self.list_items['a'].text = "{:.3f}".format(sr['posa'])

        if 'b' in self.list_items_enable and 'posb' in sr:
            if self.list_items['b'].text != "{:.3f}".format(sr['posb']):
                self.list_items['b'].text = "{:.3f}".format(sr['posb'])

        if 'c' in self.list_items_enable and 'posc' in sr:
            if self.list_items['c'].text != "{:.3f}".format(sr['posc']):
                self.list_items['c'].text = "{:.3f}".format(sr['posc'])

        if 'fr' in self.list_items_enable and 'vel' in sr:
            if self.list_items['fr'].text != "{:.2f}".format(sr['vel']):
                self.list_items['fr'].text = "{:.2f}".format(sr['vel'])

        if 'pc' in self.list_items_enable and 'prcnt' in sr:
            if self.list_items['pc'].text != sr['prcnt']:
                self.list_items['pc'].text = sr['prcnt']

        if 'rt' in self.list_items_enable and 'rtime' in sr:
            rtime = sr['rtime']
            hours, reminder = divmod(rtime, 3600)
            minutes, reminder = divmod(reminder, 60)
            seconds, mseconds = divmod(reminder, 1)
            run_time = "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)

            if self.list_items['rt'].text != run_time:
                self.list_items['rt'].text = run_time

        if 'rc' in self.list_items_enable and 'rc' in sr:
            if self.list_items['rc'].text != sr['rc']:
                self.list_items['rc'].text = sr['rc']

        if 'mi' in self.list_items_enable and 'machif' in sr:
            firmware_version_str = ""
            if 'fb' in sr:
                firmware_version_str = sr['fb']

            if 'fv' in sr:
                firmware_version_str = "fb:{} fv:{}".format(firmware_version_str, sr['fv'])

            machif_str = ""
            if len(sr['machif']):
                machif_str = "{} ({})".format(sr['machif'], firmware_version_str)

            if self.list_items['mi'].text != machif_str:
                self.list_items['mi'].text = machif_str

        if 'swst' in self.list_items_enable and 'swst' in sr:
            if self.list_items['swst'].text != sr['swst']:
                self.list_items['swst'].text = sr['swst']

        if 'gfn' in self.list_items_enable and 'gfn' in sr:
            if self.list_items['gfn'].text != sr['gfn']:
                self.list_items['gfn'].text = sr['gfn']

    def on_value_dialog_cancel(self, instance):
        if 'got_to_axis' in self.value_dialog_data_key:
            self.value_dialog.content_cls.ids.text_field.text = ""

        self.value_dialog.dismiss()
        self.value_dialog = None

    def on_value_dialog_ok(self, instance):
        # value = self.value_dialog.content_cls.value
        value = self.value_dialog.content_cls.ids.text_field.text
        if len(value):
            if self.value_dialog_data_key == 'server_config':
                self.server_hostname = self.value_dialog.content_cls.tf_server.text
                self.server_tcp_port = self.value_dialog.content_cls.tf_tcp_port.text
                self.server_udp_port = self.value_dialog.content_cls.tf_udp_port.text
                self.server_use_udp_broadcast = str(self.value_dialog.content_cls.cb_use_udp_broadcast.active)
            elif 'got_to_axis' in self.value_dialog_data_key:
                axis = self.value_dialog_data_key.split(':')[-1]
                value = self.value_dialog.content_cls.ids.text_field.text
                self.value_dialog.content_cls.ids.text_field.text = ""
                # print(f"Move axis {axis} to value: {value}")
                if gc.gsatrc_remote_client and self.serial_port_open:
                    axis_dict = {axis.lower(): value}
                    if self.jog_feed_rate == "Rapid":
                        gc_cmd = gc.EV_CMD_JOG_RAPID_MOVE
                    else:
                        gc_cmd = gc.EV_CMD_JOG_MOVE
                        axis_dict['feed'] = int(self.jog_feed_rate)
                    gc.gsatrc_remote_client.add_event(gc_cmd, axis_dict)
                else:
                    no_machine_detected()
            elif 'set_value_axis' in self.value_dialog_data_key:
                axis = self.value_dialog_data_key.split(':')[-1]
                value = self.value_dialog.content_cls.ids.text_field.text
                self.value_dialog.content_cls.ids.text_field.text = ""
                # print(f"Set axis {axis} to value: {value}")
                if gc.gsatrc_remote_client and self.serial_port_open:
                    gc.gsatrc_remote_client.add_event(gc.EV_CMD_SET_AXIS, {axis.lower(): value})
                else:
                    no_machine_detected()

        self.value_dialog.dismiss()
        self.value_dialog = None

    def on_value_dialog_value(self, instance, *args):
        self.on_value_dialog_ok(instance)

    def on_value_dialog_rapid_button(self, instance):
        self.value_dialog.content_cls.ids.text_field.text = "Rapid"
        self.on_value_dialog_ok(instance)


class MDGridLayoutButtons(MDGridLayout):
    jog_step_size = ObjectProperty(None)
    jog_feed_rate = ObjectProperty(None)
    jog_spindle_rpm = ObjectProperty(None)
    sw_state = ObjectProperty(None)
    serial_port_open = ObjectProperty(None)

    def __init__(self, **args):
        super(MDGridLayoutButtons, self).__init__(**args)

        self.gc = gc  # for access via kv lang

        Clock.schedule_once(self.on_init)

    def on_init(self, *args):
        self.config_dialog = None
        self.jog_step_size_dlg = self.on_init_config_dialog('jsz')
        self.jog_feed_rate_dlg = self.on_init_config_dialog('jfr')
        self.jog_spindle_rpm_dlg = self.on_init_config_dialog('jrpm')
        self.jog_g_code_cmd_dlg = self.on_init_config_dialog('jgcmd')

        self.on_jog_feed_rate_value_update()
        self.on_jog_spindle_rpm_value_update()
        self.on_jog_step_size_value_update()

    def on_init_config_dialog(self, data_key):
        """
        Setup jog step size dialog

        """
        button_text_color = MDApp.get_running_app().theme_cls.primary_color

        dialog_title = ""
        content_cls = None
        content_cls_on_enter = None
        content_cls_on_ok = None
        content_cls_on_cancel = None
        config_dialog = None

        if data_key in ['jsz']:
            content_cls = StepSizeDialogContent(val="")
            content_cls.ids.text_field.input_filter = 'float'
            content_cls.ids.text_field.input_type = 'number'
            dialog_title = 'Jog Step Size'
            content_cls_on_enter = self.on_jog_step_size_value
            content_cls_on_ok = self.on_jog_step_size_value
            content_cls_on_cancel = self.on_jog_step_size_cancel
        elif data_key == 'jfr':
            content_cls = InputDialogContent(val="")
            content_cls.ids.text_field.input_filter = 'int'
            content_cls.ids.text_field.input_type = 'number'
            dialog_title = 'Jog Feed Rate'
            content_cls_on_enter = self.on_jog_feed_rate_value
            content_cls_on_ok = self.on_jog_feed_rate_value
            content_cls_on_cancel = self.on_jog_feed_rate_cancel
        elif data_key == 'jrpm':
            content_cls = InputDialogContent(val="")
            content_cls.ids.text_field.input_filter = 'int'
            content_cls.ids.text_field.input_type = 'number'
            dialog_title = 'Jog Spindle RPM'
            content_cls_on_enter = self.on_jog_spindle_rpm_value
            content_cls_on_ok = self.on_jog_spindle_rpm_value
            content_cls_on_cancel = self.on_jog_spindle_rpm_cancel
        elif data_key == "jgcmd":
            content_cls = InputDialogContent(val="")
            content_cls.ids.text_field.input_filter = None
            content_cls.ids.text_field.input_type = 'text'
            dialog_title = 'G-Code Command'
            content_cls_on_enter = self.on_jog_g_code_cmd_value
            content_cls_on_ok = self.on_jog_g_code_cmd_value
            content_cls_on_cancel = self.on_jog_g_code_cmd_cancel

        if content_cls is not None:

            dialog_buttons = [
                MDFlatButton(text="CANCEL", text_color=button_text_color, on_release=content_cls_on_cancel),
                MDFlatButton(text="OK", text_color=button_text_color, on_release=content_cls_on_ok),
            ]

            if data_key == 'jfr':
                dialog_buttons.insert(
                    0,
                    MDFlatButton(
                        text="RAPID", text_color=button_text_color, on_release=self.on_jog_feed_rate_rapid_bt
                    )
                )

            content_cls.bind(on_enter=content_cls_on_enter)
            config_dialog = MDDialog(
                title=dialog_title, type='custom', content_cls=content_cls,
                buttons=dialog_buttons, on_open=content_cls.on_open
            )

        # config_dialog.open()
        return config_dialog

    def on_jog_feed_rate_bt(self):
        """
        Setup jog step size dialog

        """
        value = MDApp.get_running_app().config.get(__appname__, 'jog_feed_rate')
        self.jog_feed_rate_dlg.content_cls.ids.text_field.text = ""
        if value != "Rapid":
            self.jog_feed_rate_dlg.content_cls.ids.text_field.text = value
        self.jog_feed_rate_dlg.open()

    def on_jog_feed_rate_cancel(self, *args):
        """
        Handle cancel button on dialog

        """
        self.jog_feed_rate_dlg.dismiss()

    def on_jog_feed_rate_rapid_bt(self, *args):
        """
        Handle special Rapid button

        """
        # value = self.jog_feed_rate_dlg.content_cls.ids.text_field.text = "Rapid"
        self.on_jog_feed_rate_value()

    def on_jog_feed_rate_value(self, *args):
        """
        Get and save value

        """
        self.jog_feed_rate_dlg.dismiss()
        value = self.jog_feed_rate_dlg.content_cls.ids.text_field.text
        value_key = 'jog_feed_rate'
        old_value = MDApp.get_running_app().config.get(__appname__, value_key)
        if value != old_value:
            MDApp.get_running_app().config.set(__appname__, value_key, value)
            MDApp.get_running_app().config.write()
            self.on_jog_feed_rate_value_update()

    def on_jog_feed_rate_value_update(self, *args):
        """
        Update UI

        """
        value = MDApp.get_running_app().config.get(__appname__, 'jog_feed_rate')
        self.ids.feed_rate.text = "Feed Rate\n{}".format(value)
        self.jog_feed_rate = value

    def on_jog_g_code_cmd_bt(self):
        """
        Setup G-code cmd dialog

        """
        self.jog_g_code_cmd_dlg.open()

    def on_jog_g_code_cmd_cancel(self, *args):
        """
        Handle cancel button on dialog

        """
        self.jog_g_code_cmd_dlg.dismiss()

    def on_jog_g_code_cmd_value(self, *args):
        """
        Get value and send to remote server

        """
        self.jog_g_code_cmd_dlg.dismiss()
        value = self.jog_g_code_cmd_dlg.content_cls.ids.text_field.text

        if gc.gsatrc_remote_client and self.serial_port_open:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_SEND, "{}\n".format(value))
        else:
            self.on_no_serial_port_open()

    def on_jog_spindle_rpm_bt(self):
        """
        Setup spindle rpm dialog

        """
        value = MDApp.get_running_app().config.get(__appname__, 'jog_spindle_rpm')
        self.jog_spindle_rpm_dlg.content_cls.ids.text_field.text = value
        self.jog_spindle_rpm_dlg.open()

    def on_jog_spindle_rpm_cancel(self, *args):
        """
        Handle cancel button on dialog

        """
        self.jog_spindle_rpm_dlg.dismiss()

    def on_jog_spindle_rpm_value(self, *args):
        """
        Get and save value

        """
        self.jog_spindle_rpm_dlg.dismiss()
        value = self.jog_spindle_rpm_dlg.content_cls.ids.text_field.text
        value_key = 'jog_spindle_rpm'
        old_value = MDApp.get_running_app().config.get(__appname__, value_key)
        if value != old_value:
            MDApp.get_running_app().config.set(__appname__, value_key, value)
            MDApp.get_running_app().config.write()
            self.on_jog_spindle_rpm_value_update()

    def on_jog_spindle_rpm_value_update(self, *args):
        """
        Update UI

        """
        value = MDApp.get_running_app().config.get(__appname__, 'jog_spindle_rpm')
        self.ids.spindle_rpm.text = "Spindle RPM\n{}".format(value)
        self.jog_spindle_rpm = value

    def on_jog_step_size_bt(self):
        """
        Setup jog step size dialog

        """
        value = MDApp.get_running_app().config.get(__appname__, 'jog_step_size')
        self.jog_step_size_dlg.content_cls.ids.text_field.text = value
        self.jog_step_size_dlg.open()

    def on_jog_step_size_cancel(self, *args):
        """
        Handle cancel button on dialog

        """
        self.jog_step_size_dlg.dismiss()

    def on_jog_step_size_value(self, *args):
        self.jog_step_size_dlg.dismiss()
        value = self.jog_step_size_dlg.content_cls.ids.text_field.text
        value_key = 'jog_step_size'
        old_value = MDApp.get_running_app().config.get(__appname__, value_key)
        if value != old_value:
            MDApp.get_running_app().config.set(__appname__, value_key, value)
            MDApp.get_running_app().config.write()
            self.on_jog_step_size_value_update()

    def on_jog_step_size_value_update(self, *args):
        """
        Update UI

        """
        value = MDApp.get_running_app().config.get(__appname__, 'jog_step_size')
        self.ids.step_size.text = "Step Size\n{}".format(value)
        self.jog_step_size = value

    def on_machine_clear_alarm(self):
        if gc.gsatrc_remote_client and self.serial_port_open:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_CLEAR_ALARM)
        else:
            no_machine_detected()

    def on_machine_cycle_start(self):
        if gc.gsatrc_remote_client and self.serial_port_open:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_CYCLE_START)
        else:
            no_machine_detected()

    def on_machine_hold(self):
        if gc.gsatrc_remote_client and self.serial_port_open:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_FEED_HOLD)
        else:
            no_machine_detected()

    def on_machine_queue_flush(self):
        if gc.gsatrc_remote_client and self.serial_port_open:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_QUEUE_FLUSH)
        else:
            no_machine_detected()

    def on_machine_refresh(self):
        if gc.gsatrc_remote_client and self.serial_port_open:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_GET_STATUS)
        else:
            no_machine_detected()

    def on_pause(self):
        if gc.gsatrc_remote_client and self.serial_port_open:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_PAUSE)
        else:
            no_machine_detected()

    def on_run(self):
        if gc.gsatrc_remote_client and self.serial_port_open:
            runDict = dict()
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_RUN, runDict)
        else:
            no_machine_detected()

    def on_serial_port_open(self, instance, value):
        self.update_button_state()

    def on_step(self):
        if gc.gsatrc_remote_client and self.serial_port_open:
            runDict = dict()
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_STEP, runDict)
        else:
            no_machine_detected()

    def on_stop(self):
        if gc.gsatrc_remote_client and self.serial_port_open:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_STOP)
        else:
            no_machine_detected()

    def on_sw_state(self, instance, value):
        self.update_button_state()

    def update_button_state(self):
        return
        if self.serial_port_open:
            self.ids.send_gcode.disabled = False
            self.ids.run.disabled = False
            self.ids.pause.disabled = False
            self.ids.step.disabled = False
            self.ids.stop.disabled = False
            self.ids.machine_clear_alarm.disabled = False
            self.ids.machine_refresh.disabled = False
            self.ids.machine_cycle_start.disabled = False
            self.ids.machine_hold.disabled = False
        else:
            self.ids.send_gcode.disabled = True
            self.ids.run.disabled = True
            self.ids.pause.disabled = True
            self.ids.step.disabled = True
            self.ids.stop.disabled = True
            self.ids.machine_clear_alarm.disabled = True
            self.ids.machine_refresh.disabled = True
            self.ids.machine_cycle_start.disabled = True
            self.ids.machine_hold.disabled = True


class MDGridLayoutJogControls(MDGridLayout):
    sw_state = ObjectProperty(None)
    serial_port_open = ObjectProperty(None)

    def __init__(self, **args):
        super(MDGridLayoutJogControls, self).__init__(**args)

        self.gc = gc  # for access via kv lang
        self.jog_step_size = ""
        self.jog_feed_rate = ""
        self.jog_spindle_rpm = ""
        self.jog_long_press_time = 0.4
        self.jog_long_press_clk_ev = None
        self.jog_long_press_ev = False
        self.jog_long_press_key = ""

        Clock.schedule_once(self.on_init, 3)

    def on_init(self, *args):
        pass
        # # Calculate available space
        # available_width = self.width - sum(child.width for child in self.children)
        # available_height = self.height - sum(child.height for child in self.children)

        # # Calculate spacing
        # h_spacing = available_width / (self.cols + 1)
        # v_spacing = available_height / (self.rows + 1)

        # # Set spacing
        # self.spacing = (h_spacing, v_spacing)

        # print ("$$$$$$$$$$$$$$$$$  {}".format(self.parent.width))

    # def on_size (self, *args):
    #     Clock.schedule_once(self.on_sz_init, 5)

    def on_sz_init(self, *args):
        # print (self.size)
        # print (self.width)

        br = 7  # 7 buttons per row
        space = self.spacing[0] + 2  # 18 spacing
        sz = abs(int((self.parent.width - (space * (br-1))) / 7))
        # print(self.parent.width)
        # print (self.parent.width - (sp * (br-1)))
        # print (sz)
        # print (sp(1))
        # print ("{:.2f}sp".format(sz/sp(1)))

        if sz > 60:
            for widget in self.walk():
                if type(widget) is MDIconButton:
                    widget.height = sz
                    widget.width = sz
                    # widget.user_font_size = "{:.2f}sp".format((sz/sp(1))*.7)
                    # widget.canvas.ask_update()

    def on_jog_button_long_press(self, time):
        """
        Handle long press for a few jog buttons (part 3)

        """
        if self.sw_state in [gc.STATE_RUN]:
            jog_not_permitted_run_state()
            return

        self.jog_long_press_ev = True

        if self.long_press_clk_ev:
            self.long_press_clk_ev = None

        dir = 0
        big_val = 99999

        if self.jog_long_press_key[:1] == "+":
            dir = 1
        elif self.jog_long_press_key[:1] == "-":
            dir = -1

        self.on_jog_move_relative(self.jog_long_press_key[1:], step_size=float(big_val * dir))

    def on_jog_button_press(self, key):
        """
        Handle long press for a few jog buttons (part 1)

        """
        if self.sw_state in [gc.STATE_RUN]:
            jog_not_permitted_run_state()
            return

        if gc.gsatrc_remote_client and self.serial_port_open:
            self.jog_long_press_key = key
            self.long_press_clk_ev = Clock.schedule_once(self.on_jog_button_long_press, self.jog_long_press_time)

    def on_jog_button_release(self, key):
        """
        Handle long press for a few jog buttons (part 2)

        """
        if self.sw_state in [gc.STATE_RUN]:
            jog_not_permitted_run_state()
            return

        if gc.gsatrc_remote_client and self.serial_port_open:
            if self.jog_long_press_ev:
                self.jog_long_press_ev = False
                gc.gsatrc_remote_client.add_event(gc.EV_CMD_JOG_STOP)
            else:
                if self.long_press_clk_ev:
                    self.long_press_clk_ev.cancel()
                    self.long_press_clk_ev = None
                    self.jog_long_press_ev = False

                # handle regular press
                dir = 0

                if key[:1] == "+":
                    dir = 1
                elif key[:1] == "-":
                    dir = -1

                self.on_jog_move_relative(
                    self.jog_long_press_key[1:], step_size=float(self.jog_step_size * dir)
                )
        else:
            no_machine_detected()

    def on_jog_home_axis(self, axis):
        if self.sw_state in [gc.STATE_RUN]:
            jog_not_permitted_run_state()
            return

        if gc.gsatrc_remote_client and self.serial_port_open:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_HOME, axis)
        else:
            no_machine_detected()

    def on_jog_move_absolute(self, axis):
        if self.sw_state in [gc.STATE_RUN]:
            jog_not_permitted_run_state()
            return

        if gc.gsatrc_remote_client:
            if self.jog_feed_rate == "Rapid":
                gc_cmd = gc.EV_CMD_JOG_RAPID_MOVE
            else:
                gc_cmd = gc.EV_CMD_JOG_MOVE
                axis['feed'] = int(self.jog_feed_rate)
            gc.gsatrc_remote_client.add_event(gc_cmd, axis)

    def on_jog_move_relative(self, axis_str, step_size=None):
        if self.sw_state in [gc.STATE_RUN]:
            jog_not_permitted_run_state()
            return

        if gc.gsatrc_remote_client:
            if step_size is None:
                step_size = float(self.jog_step_size)

            axis = {axis_str: step_size}
            if self.jog_feed_rate == "Rapid":
                gc_cmd = gc.EV_CMD_JOG_RAPID_MOVE_RELATIVE
            else:
                gc_cmd = gc.EV_CMD_JOG_MOVE_RELATIVE
                axis['feed'] = int(self.jog_feed_rate)
            gc.gsatrc_remote_client.add_event(gc_cmd, axis)

    def on_jog_probe(self, data):
        if self.sw_state in [gc.STATE_RUN]:
            jog_not_permitted_run_state()
            return

        # TODO: does pendant really need to keep this config??
        # probe command should be sent to server, server should
        # the information of the prove offset, etc.
        if gc.gsatrc_remote_client and self.serial_port_open:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_SEND, data)
        else:
            no_machine_detected()

    def on_jog_send_cmd(self, data):
        if self.sw_state in [gc.STATE_RUN]:
            jog_not_permitted_run_state()
            return

        if gc.gsatrc_remote_client and self.serial_port_open:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_SEND, data)
        else:
            no_machine_detected()

    def on_jog_set_axis(self, axis):
        if self.sw_state in [gc.STATE_RUN]:
            jog_not_permitted_run_state()
            return

        if gc.gsatrc_remote_client and self.serial_port_open:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_SET_AXIS, axis)
        else:
            no_machine_detected()


class RootWidget(Screen, gc.EventQueueIf):
    serial_port_open = ObjectProperty(None)
    sw_state = ObjectProperty(None)

    def __init__(self, **args):
        super(RootWidget, self).__init__(**args)
        gc.EventQueueIf.__init__(self)

        # register events
        self.register_event_type('on_process_queue')

        # init variables
        self.gc = gc  # for access via kv lang
        gc.gsatrc_remote_client = None
        self.device_detected = False
        self.jog_step_size = ""
        self.jog_feed_rate = ""
        self.jog_spindle_rpm = ""
        self.update_dro = None

        self.ids.dro_panel.bind(rc_connect=self.on_value_rc_connect)
        self.ids.dro_panel.bind(server_hostname=self.on_value_server_hostname)
        self.ids.dro_panel.bind(server_tcp_port=self.on_value_server_tcp_port)
        self.ids.dro_panel.bind(server_udp_port=self.on_value_server_udp_port)
        self.ids.dro_panel.bind(server_use_udp_broadcast=self.on_value_server_use_udp_broadcast)
        self.ids.dro_panel.bind(on_display_gcode_filename=self.on_display_gcode_filename)

        self.ids.button_panel.bind(jog_step_size=self.on_value_jog_step_size)
        self.ids.button_panel.bind(jog_feed_rate=self.on_value_jog_feed_rate)
        self.ids.button_panel.bind(jog_spindle_rpm=self.on_value_jog_spindle_rpm)

        Clock.schedule_once(self.on_init)
        # self.on_init()

    # @mainthread
    def add_event(self, id, data=None, sender=None):
        # print ("{} from root_add_event".format(threading.current_thread().ident))
        gc.EventQueueIf.add_event(self, id, data, sender)
        Clock.schedule_once(self.on_process_queue)
        # self.dispatch('on_process_queue')

    def append_text(self, str_data):
        """ text output
        """
        self.text_out.append_text(str_data)

    def on_open(self):
        if gc.gsatrc_remote_client is None:
            gc.gsatrc_remote_client = rc.RemoteClientThread(
                self, self.server_hostname, self.server_tcp_port, self.server_udp_port, self.server_use_udp_broadcast
            )

    def on_cli_text_validate(self, text, *args):
        if gc.gsatrc_remote_client and self.serial_port_open:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_SEND, "{}\n".format(str(text).strip()))
        else:
            no_machine_detected()

    def on_close(self):
        if gc.gsatrc_remote_client:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_EXIT)

    def on_init(self, *args):
        self.sw_state = gc.STATE_IDLE
        self.serial_port_open = False
        self.update_dro = self.ids.dro_panel.on_update
        self.text_out = self.ids.text_out
        self.remote_gcode_md5 = 0
        self.remote_gcode_filename = ""
        # print ("*******************")
        # print (Window.size)
        # print ("################# {}".format(self.size))

    def on_display_gcode_filename(self, *args):
        if len(self.remote_gcode_filename):
            self.append_text("G-code filename: {}\n".format(self.remote_gcode_filename))

    def on_stop(self):
        self.on_close()
        time.sleep(0.1)

    def on_serial_port_open(self, instance, value):
        self.ids.button_panel.serial_port_open = value
        self.ids.jog_ctrl.serial_port_open = value
        self.ids.dro_panel.serial_port_open = value

        if value is False and self.update_dro:
            self.remote_gcode_md5 = 0
            self.remote_gcode_filename = ""

    def on_sw_state(self, instance, value):
        # print ("{} from on_sw_state".format(threading.current_thread().ident))
        self.ids.button_panel.sw_state = value
        self.ids.jog_ctrl.sw_state = value
        self.ids.dro_panel.sw_state = value

    def on_process_queue(self, *args):
        """
        Process evens on queue

        """
        try:
            ev = self._eventQueue.get_nowait()
        except queue.Empty:
            pass
        else:
            if ev.event_id == gc.EV_DATA_STATUS:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_DATA_STATUS")

                if 'sr' in ev.data:
                    sr = ev.data['sr']
                    self.update_dro(sr)

                # TODO: control this via config
                if 'rx_data' in ev.data:
                    self.append_text("{}".format(ev.data['rx_data']))

                # if 'pc' in ev.data:
                #     if self.stateData.programCounter != ev.data['pc']:
                #         self.SetPC(ev.data['pc'])

                if 'swstate' in ev.data:
                    if self.sw_state != int(ev.data['swstate']):
                        self.sw_state = int(ev.data['swstate'])
                        self.update_dro({'swst': gc.get_sw_status_str(self.sw_state)})

                if 'r' in ev.data:
                    r = ev.data['r']

                    if 'sys' in r:
                        sys_info = r['sys']

                        if 'machif' in sys_info:
                            self.update_dro(sys_info)

                    if 'machif' in r:
                        self.update_dro(r)

            elif ev.event_id == gc.EV_DATA_IN:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_DATA_IN")

                # TODO: control this via config
                self.append_text(ev.data)

            elif ev.event_id == gc.EV_DATA_OUT:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_DATA_OUT")

                # TODO: control this via config
                if ev.data[-1:] != "\n":
                    ev.data = "{}\n".format(ev.data)

                self.append_text("> {}".format(ev.data))

            elif ev.event_id == gc.EV_PC_UPDATE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_PC_UPDATE [%s]" % str(ev.data))

                # self.SetPC(ev.data)

            elif ev.event_id == gc.EV_RUN_END:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_RUN_END")

                # self.runEndWaitingForMachIfIdle = True
                # self.UpdateUI()

            elif ev.event_id == gc.EV_STEP_END:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_STEP_END")

                # self.UpdateUI()

            elif ev.event_id == gc.EV_BRK_PT_STOP:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_HIT_BRK_PT")

            elif ev.event_id == gc.EV_GCODE_MSG:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_HIT_MSG [%s]" % ev.data.strip())

                self.append_text("** MSG: {}\n".format(ev.data.strip()))

            elif ev.event_id == gc.EV_SER_PORT_OPEN:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_SER_PORT_OPEN from 0x{:x} {}".format(id(ev.sender), ev.sender))

                self.serial_port_open = True

                if gc.gsatrc_remote_client is not None:
                    gc.gsatrc_remote_client.add_event(gc.EV_CMD_GET_STATUS)

            elif ev.event_id == gc.EV_SER_PORT_CLOSE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_SER_PORT_CLOSE from 0x{:x} {}".format(id(ev.sender), ev.sender))

                # order matters in this case sw_state must be first
                self.sw_state = gc.STATE_IDLE
                self.serial_port_open = False
                self.device_detected = False

            elif ev.event_id == gc.EV_EXIT:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_EXIT from 0x{:x} {}".format(id(ev.sender), ev.sender))

                if id(ev.sender) == id(gc.gsatrc_remote_client):
                    gc.gsatrc_remote_client = None
                    self.update_dro({'rc': ""})

                    self.sw_state = gc.STATE_IDLE
                    self.serial_port_open = False
                    self.device_detected = False
                    self.ids.dro_panel.rc_connect = False

            elif ev.event_id == gc.EV_DEVICE_DETECTED:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_DEVICE_DETECTED")

                self.device_detected = True

            elif ev.event_id == gc.EV_ABORT:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_ABORT from 0x{:x} {}".format(id(ev.sender), ev.sender))

                self.append_text(ev.data)

                if ev.sender is gc.gsatrc_remote_client:
                    self.on_close()

                self.sw_state = gc.STATE_IDLE
                self.serial_port_open = False
                self.device_detected = False

            elif ev.event_id == gc.EV_RMT_PORT_OPEN:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_RMT_PORT_OPEN from 0x{:x} {}".format(id(ev.sender), ev.sender))

                self.append_text(ev.data)

                if gc.gsatrc_remote_client is not None:
                    gc.gsatrc_remote_client.add_event(gc.EV_CMD_GET_SYSTEM_INFO)
                    gc.gsatrc_remote_client.add_event(gc.EV_CMD_GET_SW_STATE)
                    gc.gsatrc_remote_client.add_event(gc.EV_CMD_GET_GCODE_MD5)

            elif ev.event_id == gc.EV_RMT_PORT_CLOSE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_RMT_PORT_CLOSE from 0x{:x} {}".format(id(ev.sender), ev.sender))

                self.append_text(ev.data)
                self.sw_state = gc.STATE_IDLE
                self.serial_port_open = False
                self.device_detected = False

            elif ev.event_id == gc.EV_RMT_CONFIG_DATA:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_RMT_CONFIG_DATA from 0x{:x} {}".format(id(ev.sender), ev.sender))

                # self.configRemoteData = ev.data
                # self.machineStatusPanel.UpdateSettings(self.configData, self.configRemoteData)

            elif ev.event_id == gc.EV_RMT_HELLO:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_RMT_HELLO from 0x{:x} {}".format(id(ev.sender), ev.sender))

                self.append_text(ev.data)
                hostname = "{}".format(gc.gsatrc_remote_client.get_hostname())
                self.update_dro({'rc': hostname})

            elif ev.event_id == gc.EV_RMT_GOOD_BYE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_RMT_GOOD_BYE from 0x{:x} {}".format(id(ev.sender), ev.sender))

                self.append_text(ev.data)

            elif ev.event_id == gc.EV_SW_STATE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_SW_STATE")

                self.sw_state = ev.data
                self.update_dro({'swst': gc.get_sw_status_str(self.sw_state)})

            elif ev.event_id == gc.EV_GCODE_MD5:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_GCODE_MD5")

                old_md5_hash = self.remote_gcode_md5
                self.remote_gcode_md5 = ev.data

                h = hashlib.md5(str([]).encode('utf-8')).hexdigest()
                if h != ev.data and self.serial_port_open and gc.gsatrc_remote_client:
                    if old_md5_hash != ev.data:
                        gc.gsatrc_remote_client.add_event(gc.EV_CMD_GET_GCODE)

            elif ev.event_id == gc.EV_GCODE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_GCODE")

                if 'gcodeFileName' in ev.data:
                    self.remote_gcode_filename = os.path.basename(ev.data['gcodeFileName'])
                    self.update_dro({'gfn': self.remote_gcode_filename})
                    self.append_text("G-code filename: {}\n".format(self.remote_gcode_filename))

            elif ev.event_id == gc.EV_BRK_PT_CHG:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_BRK_PT_CHG")

                # if self.machifProgExec is not None:
                #     self.machifProgExec.add_event(gc.EV_CMD_GET_BRK_PT)

            elif ev.event_id == gc.EV_BRK_PT:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_BRK_PT")

                # break_points = ev.data

                # if self.gcText.GetBreakPoints() != break_points:
                #     self.gcText.DeleteAllBreakPoints()
                #     for bp in break_points:
                #         self.gcText.UpdateBreakPoint(bp, True)

            else:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.error(
                        "got UNKNOWN event id[{}] from 0x{:x} {}".format(ev.event_id, id(ev.sender), ev.sender))

    def on_value_jog_feed_rate(self, instance, value):
        self.jog_feed_rate = value
        self.ids.jog_ctrl.jog_feed_rate = self.jog_feed_rate
        self.ids.dro_panel.jog_feed_rate = self.jog_feed_rate

    def on_value_jog_spindle_rpm(self, instance, value):
        try:
            self.jog_spindle_rpm = int(value)
        except ValueError:
            self.jog_spindle_rpm = 18000

        self.ids.jog_ctrl.jog_spindle_rpm = self.jog_spindle_rpm

    def on_value_jog_step_size(self, instance, value):
        try:
            self.jog_step_size = float(value)
        except ValueError:
            self.jog_step_size = 1.0

        self.ids.jog_ctrl.jog_step_size = self.jog_step_size

    def on_value_rc_connect(self, instance, value):
        """
        Handle remote server open/close events from DRO panel

        """
        if value:
            self.on_open()
        else:
            self.on_close()

    def on_value_server_hostname(self, instance, value):
        self.server_hostname = value

    def on_value_server_tcp_port(self, instance, value):
        self.server_tcp_port = int(value)

    def on_value_server_udp_port(self, instance, value):
        self.server_udp_port = int(value)

    def on_value_server_use_udp_broadcast(self, instance, value):
        self.server_use_udp_broadcast = eval(value)


class MDBoxLayoutAutoRotate(MDBoxLayout):
    def __init__(self, **kwargs):
        super(MDBoxLayoutAutoRotate, self).__init__(**kwargs)

    def on_size(self, *args):
        # print (self.size)
        # print (self.width)

        if self.width > self.height:
            self.orientation = 'horizontal'
        else:
            self.orientation = 'vertical'


class MainApp(MDApp):
    # icon = "gsat-rc-32x32.png"

    def build(self):
        self.title = __appname_brief__
        self.icon = "gsat-rc-32x32.png"
        config = self.config
        # self.theme_cls.primary_palette = "Green"
        # self.theme_cls.primary_hue = "A700"
        self.theme_cls.theme_style = "Light"
        # screen = Builder.load_string(kv_helper)
        # return screen

        if platform == 'android':
            Clock.schedule_once(self.set_wake_lock, 0)

        return RootWidget()

    def build_config(self, config):
        config.setdefaults(__appname__, {
            'server_hostname': "hostname",
            'server_tcp_port': "61801",
            'server_udp_port': "61802",
            'server_use_udp_broadcast': False,
            'jog_step_size': "1",
            'jog_feed_rate': "Rapid",
            'Jog_spindle_rpm': "18000"
        })

    def on_start(self):
        if platform == 'android':
            # fix issues with text_input below virtual keyboard
            from kivy.core.window import Window
            Window.softinput_mode = 'below_target'

            # fix issue with battery optimization, app doze sleep will
            # mess socket connection, resulting in a non responsive network connection
            # if version M or newer ask user to add this app to the
            # "NO BATT OPTIMIZATION" list

            activity = PythonActivity.mActivity

            Context = autoclass('android.content.Context')
            power = activity.getSystemService(Context.POWER_SERVICE)
            ignore_batt_opt = power.isIgnoringBatteryOptimizations(activity.getPackageName())

            if ignore_batt_opt:
                pass
            else:
                Intent = autoclass('android.content.Intent')
                Settings = autoclass('android.provider.Settings')
                # pm = autoclass('android.content.pm.PackageManager')
                Uri = autoclass('android.net.Uri')

                intent = Intent()

                # try:
                #     intent.setAction(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)
                #     intent.setData(Uri.parse("package:" + activity.getPackageName()))
                #     activity.startActivity(intent)
                # except JavaException as err:
                #     print ("Got Java exceptions")
                #     intent.setAction(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)
                #     toast("Please mark gsat rc as not optimized in the next screen", length_long=20)
                #     activity.startActivity(intent)

                # except Exception as err:
                #     print ("Got exceptions")

                # except:
                #     print ("Why here??")

                intent.setAction(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)
                toast("Please mark ( gsat rc ) as not optimized", length_long=20)
                activity.startActivity(intent)

    def set_wake_lock(self, *args):
        if platform == 'android':
            self._android_set_wake_lock()

    if platform == 'android':
        @run_on_ui_thread
        def _android_set_wake_lock(self):
            activity = PythonActivity.mActivity
            window = activity.getWindow()
            window.addFlags(LayoutParams.FLAG_KEEP_SCREEN_ON)

    def on_stop(self):
        self.root.on_stop()
        self.config.write()

    def get_color_random(self):
        return (random.random(), random.random(), random.random(), 1)


if __name__ == '__main__':
    MainApp().run()
