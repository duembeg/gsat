import sys
import time

#from kivy.lang import Builder
from kivy.config import Config
from kivy.utils import platform

if platform != 'android':
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
    Config.set('graphics', 'width', '1280')
    Config.set('graphics', 'height', '800')
    # Config.set('graphics', 'width', '800')
    # Config.set('graphics', 'height', '1280')

if platform == 'android':
    pass
    # from android.permissions import request_permissions, Permission
    # request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])

# Config.set('kivy','window_icon','/images/icons/color/gcs_g1_cog_32x32.png')

from kivymd.app import MDApp
from kivymd.uix.screen import Screen
from kivymd.uix.boxlayout import MDBoxLayout
# from kivymd.uix.floatlayout import FloatLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.button import MDFlatButton #, MDRectangleFlatButton, MDIconButton, MDRoundImageButton
from kivymd.uix.textfield import MDTextField #, MDTextFieldRect
from kivymd.uix.list import MDList, OneLineListItem, TwoLineListItem
# from kivymd.uix.dropdownitem import MDDropDownItem
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.list import IRightBodyTouch
from kivymd.uix.selectioncontrol import MDCheckbox #, MDSwitch
from kivymd.uix.dialog import MDDialog
from kivy.clock import Clock
# from kivy.uix.anchorlayout import AnchorLayout
# from kivy.uix.scrollview import ScrollView
from kivy.properties import ObjectProperty, BooleanProperty

#from random import random
import random

from modules.version_info import *

import modules.config as gc
import modules.remote_client as rc


class InputDialagoContent(MDBoxLayout):
    ''' General config custom input dialog content '''

    value = ObjectProperty(None)
    enter = ObjectProperty(None)

    def __init__(self, val, **kwargs):
        ''' init function for object
        '''
        super(InputDialagoContent, self).__init__(**kwargs)
        self.value = val

        Clock.schedule_once(self.on_init)
        # self.on_init()

    def on_init(self, *args):
        #self.ids.text_field.focus = True
        self.ids.text_field.text = self.value

    def on_number_button_release(self, instance):
        ''' replace txt field with button text
        '''
        self.ids.text_field.text = instance.text
        self.value = self.ids.text_field.text
        self.ids.text_field.focus = True

    def on_open(self, instance):
        self.ids.text_field.focus = True

    def on_text_validate(self, instance):
        self.value = instance.text
        self.enter = True


class StepSizeDialagoContent(InputDialagoContent):
    ''' Step size config custom dialog content '''

    def on_init(self, *args):
        super(StepSizeDialagoContent, self).on_init(args)

        self.height = "200dp"
        self.ids.text_field.input_filter = 'float'

        for bt_text in ['0.1', '0.5', '1', '5', '10', '20', '50','100', '150', '200', '400', '500']:
            bt = MDFlatButton(text=bt_text, on_release=self.on_number_button_release)
            self.ids.step_size_buttons.add_widget(bt)

        self.size_hint_y=None
        bt = MDFlatButton(text='dummy', on_release=self.on_number_button_release)


class ServerDialagoContent(InputDialagoContent):
    ''' Server config custom dialog content '''
    def __init__(self, hostname, tcp_port, udp_port, **kwargs):
        ''' init function for object
        '''
        self.hostname = hostname
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        super(ServerDialagoContent, self).__init__(hostname, **kwargs)

    def on_init(self, *args):
        super(ServerDialagoContent, self).on_init(args)

        self.height = "200dp"
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


class OneListItemWithCheckbox(OneLineListItem):
    '''Custom list item.'''


class TwoListItemWithCheckbox(TwoLineListItem):
    '''Custom list item.'''


class RightCheckbox(IRightBodyTouch, MDCheckbox):
    '''Custom right container.'''


class MDBoxLayoutDRO(MDBoxLayout):
    ''' Class to handle DRO panel list items
    '''
    rc_connect = ObjectProperty(None)
    jog_step_size = ObjectProperty(None)
    jog_feed_rate = ObjectProperty(None)
    jog_spindle_rpm = ObjectProperty(None)
    server_hostname  = ObjectProperty(None)
    server_tcp_port  = ObjectProperty(None)
    server_udp_port  = ObjectProperty(None)
    serial_port_open  = ObjectProperty(None)

    def __init__(self, **kwargs):
        ''' Constructor
        '''
        super(MDBoxLayoutDRO, self).__init__(**kwargs)

        Clock.schedule_once(self.on_init)
        # self.on_init()

    def init_a_menu (self, data, list_items):
        ''' Init a single menu from data array
        '''
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
                            #"viewclass": "MDMenuItem",
                            "icon": di['icon'],
                            "text": di['name'],
                            "font_style": "Caption",
                            # "height": "36dp",
                            # "top_pad": "10dp",
                            # "bot_pad": "10dp",
                            "divider": None,
                            "disable": True,
                        })
            else:
                menu_items.append({"viewclass": "MDSeparator", "height": 1})

        menu = MDDropdownMenu(caller=self, items=menu_items, width_mult=4)
        menu.bind(on_release=self.menu_callback)

        if type(list_items) is not list:
            list_items = [list_items]

        for li in list_items:
            if li in self.list_items:
                self.list_items[li].menu = menu

        return menu

    def init_dialog(self):
        self.jog_step_size_dialog = self.on_init_value_dialog('jsz')
        self.jog_feed_rate_dialog = self.on_init_value_dialog('jfr')
        self.jog_spindle_rpm_dialog = self.on_init_value_dialog('jrpm')
        self.server_config_dialog = self.on_init_value_dialog('server_config')

    def init_list(self):
        ''' Init MD lists
        '''
        # update DRO list
        items = list(self.ids.dro_list.children)
        for li in items:
            self.ids.dro_list.remove_widget(li)

        for li in self.dro_list_enable:
            self.ids.dro_list.add_widget(self.list_items[li])

        # update info list
        items = list(self.ids.info_list.children)
        for li in items:
            self.ids.info_list.remove_widget(li)

        for li in self.info_list_enable:
            self.ids.info_list.add_widget(self.list_items[li])

    def init_menu(self):
        ''' Init menus for the different widgets
        '''
        icon = 'icon'
        name = 'name'

        # axis menus
        items = [
            {icon: "numeric-0-circle-outline", name: "Zero Axis"},
            {icon: "home-search-outline", name: "Home Axis"},
        ]
        self.init_a_menu(items, self.axis_list_items)

        # device menu
        items = [
            {icon: "power-plug", name: "Connect"},
            {icon: "power-plug-off", name: "Disconnect"},
            {icon: "refresh", name: "Refresh"},
            {icon: "power", name: "Reset"},
        ]
        self.init_a_menu(items, 'mi')

        # server menu
        items = [
            {icon: "lan-connect", name: "Connect"},
            {icon: "lan-disconnect", name: "Disconnect"},
            {icon: "cog-outline", name: "Configure"},
        ]
        self.init_a_menu(items, 'rc')

        # jog step size menu
        items = [
            {icon: "ruler", name: "{}".format(x)} for x in [0.1,0.25,0.5,1,5,10,20,50,100,150,200,400]
        ]
        self.init_a_menu(items, 'jsz')

        # # server menu
        # items = [
        #     {icon: "lan-connect", name: "Connect"},
        #     {icon: "lan-disconnect", name: "Disconnect"},
        # ]
        # self.init_a_menu(items, 'rc')

    def menu_callback(self, instance_menu, instance_menu_item):
        ''' menu callback event handler
        '''
        list_item = instance_menu.caller
        instance_menu.dismiss()

        # identify instance
        li = ""
        for i in self.list_items:
            if self.list_items[i] == list_item:
               li = i
               break

        # handle remote server
        if li == 'rc':
            if instance_menu_item.text == "Connect":
                self.rc_connect = True
            elif instance_menu_item.text == "Disconnect":
                self.rc_connect = False
            elif instance_menu_item.text == "Configure":
                self.value_dialog_data_key = "server_config"
                self.value_dialog = self.server_config_dialog
                self.value_dialog.open()

        # handle device
        elif li == 'mi' and gc.gsatrc_remote_client:
            if instance_menu_item.text == "Connect" and not self.serial_port_open:
                gc.gsatrc_remote_client.add_event(gc.EV_CMD_OPEN)
            elif instance_menu_item.text == "Disconnect" and self.serial_port_open:
                gc.gsatrc_remote_client.add_event(gc.EV_CMD_CLOSE)
            elif instance_menu_item.text == "Refresh" and self.serial_port_open:
                gc.gsatrc_remote_client.add_event(gc.EV_CMD_GET_STATUS)
            elif instance_menu_item.text == "Reset" and self.serial_port_open:
                gc.gsatrc_remote_client.add_event(gc.EV_CMD_RESET)

        # handle axis menus
        elif li in self.axis_list_items and gc.gsatrc_remote_client:
            if instance_menu_item.text == "Zero Axis":
                gc.gsatrc_remote_client.add_event(gc.EV_CMD_SET_AXIS, {li: 0})
            elif instance_menu_item.text == "Home Axis":
                gc.gsatrc_remote_client.add_event(gc.EV_CMD_HOME, {li: 0})

        # handle step size
        elif li in 'jsz':
            self.jog_step_size = instance_menu_item.text
            self.list_items[li].text = "{}".format(self.jog_step_size)

    def on_init(self, *args):
        ''' init event after construction
        '''
        self.axis_list_items = ['x', 'y', 'z', 'a', 'b', 'c']
        self.dro_list_enable = ['x', 'y', 'z', 'a', 'fr', 'st', 'swst']
        self.info_list_enable = ['mi', 'pc', 'rt', 'rc', 'jsz', 'jfr', 'jrpm']
        #self.dro_list_enable = []
        #self.info_list_enable = []

        if (set(self.dro_list_enable) & set(self.info_list_enable)):
            raise Exception("Cannot have same item in multiple MD lists!!")

        self.list_items = {
            'x': self.ids.x_axis,
            'y': self.ids.y_axis,
            'z': self.ids.z_axis,
            'a': self.ids.a_axis,
            'b': self.ids.b_axis,
            'c': self.ids.c_axis,
            'fr': self.ids.feed_rate,
            'st': self.ids.status,
            'swst': self.ids.sw_status,
            'mi': self.ids.device,
            'pc': self.ids.gcode_pos,
            'rt': self.ids.run_time,
            'rc': self.ids.remote_server,
            'jsz': self.ids.jog_step_size,
            'jfr': self.ids.jog_feed_rate,
            'jrpm': self.ids.jog_spindle_rpm,
        }

        for li in self.list_items:
            self.list_items[li].menu = None

        # TODO get this value form config/settings
        self.jog_step_size = MDApp.get_running_app().config.get(__appname__, 'jog_step_size')
        self.list_items['jsz'].text = "{}".format(self.jog_step_size)

        self.jog_feed_rate = MDApp.get_running_app().config.get(__appname__, 'jog_feed_rate')
        self.list_items['jfr'].text = "{}".format(self.jog_feed_rate)

        self.jog_spindle_rpm = MDApp.get_running_app().config.get(__appname__, 'jog_spindle_rpm')
        self.list_items['jrpm'].text = "{}".format(self.jog_spindle_rpm)

        self.server_hostname = MDApp.get_running_app().config.get(__appname__, 'server_hostname')
        self.server_tcp_port = MDApp.get_running_app().config.get(__appname__, 'server_tcp_port')
        self.server_udp_port = MDApp.get_running_app().config.get(__appname__, 'server_udp_port')

        self.init_menu()
        self.init_list()
        self.init_dialog()

    def on_init_value_dialog(self, data_key):
        ''' setup jog step size dialog
        '''
        button_text_color = MDApp.get_running_app().theme_cls.primary_color

        dialog_buttons=[
            MDFlatButton(text="CANCEL", text_color=button_text_color, on_release=self.on_value_dialog_cancel),
            MDFlatButton(text="OK", text_color=button_text_color, on_release=self.on_value_dialog_ok),
        ]

        dialog_title = ""
        content_cls = None
        value_dialog = None

        if data_key in ['jsz']:
            content_cls=StepSizeDialagoContent(val=self.list_items[data_key].text)
            dialog_title = 'Jog Step Size'
        elif data_key == 'jfr':
            content_cls=InputDialagoContent(val=self.list_items[data_key].text)
            dialog_title = 'Jog Feed Rate'
            dialog_buttons.insert(
                0, MDFlatButton(
                    text="RAPID", text_color=button_text_color, on_release=self.on_value_dialog_rapid_button))
        elif data_key == 'jrpm':
            content_cls=InputDialagoContent(val=self.list_items[data_key].text)
            dialog_title = 'Jog Spindle RPM'
        elif data_key == "server_config":
            content_cls=ServerDialagoContent(self.server_hostname, self.server_tcp_port, self.server_udp_port)
            dialog_title = 'Remote Server'

        if content_cls is not None:
            content_cls.bind(enter=self.on_value_dialog_value)
            value_dialog = MDDialog(
                title=dialog_title, type='custom', content_cls=content_cls,
                buttons=dialog_buttons, on_open=content_cls.on_open
            )

        # value_dialog.open()
        return value_dialog

    def on_jog_step_size(self, instance, value):
        value_key = 'jog_step_size'
        old_value = MDApp.get_running_app().config.get(__appname__, value_key)
        if value != old_value:
            MDApp.get_running_app().config.set(__appname__, value_key, value)
            MDApp.get_running_app().config.write()


    def on_jog_step_size_release(self, instance):
        ''' setup jog step size dialog
        '''
        self.value_dialog_data_key = 'jsz'
        self.value_dialog = self.jog_step_size_dialog
        self.value_dialog.open()

    def on_jog_feed_rate(self, instance, value):
        value_key = 'jog_feed_rate'
        old_value = MDApp.get_running_app().config.get(__appname__, value_key)
        if value != old_value:
            MDApp.get_running_app().config.set(__appname__, value_key, value)
            MDApp.get_running_app().config.write()

    def on_jog_feed_rate_release(self, instance):
        ''' setup jog step size dialog
        '''
        self.value_dialog_data_key = 'jfr'
        self.value_dialog = self.jog_feed_rate_dialog
        self.value_dialog.open()

    def on_jog_spindle_rpm(self, instance, value):
        value_key = 'jog_spindle_rpm'
        old_value = MDApp.get_running_app().config.get(__appname__, value_key)
        if value != old_value:
            MDApp.get_running_app().config.set(__appname__, value_key, value)
            MDApp.get_running_app().config.write()

    def on_jog_spindle_rpm_release(self, instance):
        ''' setup jog step size dialog
        '''
        self.value_dialog_data_key = 'jrpm'
        self.value_dialog = self.jog_spindle_rpm_dialog
        self.value_dialog.open()

    def on_list_item_release(self, instance):
        ''' On list item release event handler
        '''
        if instance is not None:
            # print(instance.text, instance.x, instance.y)
            # print(instance.to_window(instance.center_x, instance.center_y), instance.text)
            if instance.menu:
                instance.menu.caller = instance
                instance.menu.open()

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

    def on_update(self, sr):
        ''' Update DRO fields
        '''
        if 'st' in self.dro_list_enable and 'stat' in sr:
            if self.list_items['st'].text != sr['stat']:
                self.list_items['st'].text = sr['stat']

        if 'x' in self.dro_list_enable and 'posx' in sr:
            if self.list_items['x'].text != "{:.3f}".format(sr['posx']):
                self.list_items['x'].text = "{:.3f}".format(sr['posx'])

        if 'y' in self.dro_list_enable and 'posy' in sr:
            if self.list_items['y'].text != "{:.3f}".format(sr['posy']):
                self.list_items['y'].text = "{:.3f}".format(sr['posy'])

        if 'z' in self.dro_list_enable and 'posz' in sr:
            if self.list_items['z'].text != "{:.3f}".format(sr['posz']):
                self.list_items['z'].text = "{:.3f}".format(sr['posz'])

        if 'a' in self.dro_list_enable and 'posa' in sr:
            if self.list_items['a'].text != "{:.3f}".format(sr['posa']):
                self.list_items['a'].text = "{:.3f}".format(sr['posa'])

        if 'b' in self.dro_list_enable and 'posb' in sr:
            if self.list_items['b'].text != "{:.3f}".format(sr['posb']):
                self.list_items['b'].text = "{:.3f}".format(sr['posb'])

        if 'c' in self.dro_list_enable and 'posc' in sr:
            if self.list_items['c'].text != "{:.3f}".format(sr['posc']):
                self.list_items['c'].text = "{:.3f}".format(sr['posc'])

        if 'fr' in self.dro_list_enable and 'vel' in sr:
            if self.list_items['fr'].text != "{:.2f}".format(sr['vel']):
                self.list_items['fr'].text = "{:.2f}".format(sr['vel'])

        if 'pc' in self.info_list_enable and 'prcnt' in sr:
            if self.list_items['pc'].text != sr['prcnt']:
                self.list_items['pc'].text = sr['prcnt']

        if 'rt' in self.info_list_enable and 'rtime' in sr:
            rtime = sr['rtime']
            hours, reminder = divmod(rtime, 3600)
            minutes, reminder = divmod(reminder, 60)
            seconds, mseconds = divmod(reminder, 1)
            run_time = "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)

            if self.list_items['rt'].text != run_time:
                self.list_items['rt'].text = run_time

        if 'rc' in self.info_list_enable and 'rc' in sr:
            if self.list_items['rc'].text != sr['rc']:
                self.list_items['rc'].text = sr['rc']

        if 'mi' in self.info_list_enable and 'mi' in sr:
            if self.list_items['mi'].text != sr['mi']:
                self.list_items['mi'].text = sr['mi']

        if 'swst' in self.dro_list_enable and 'swst' in sr:
            if self.list_items['swst'].text != sr['swst']:
                self.list_items['swst'].text = sr['swst']

    def on_value_dialog_cancel(self, instance):
        self.value_dialog.dismiss()
        self.value_dialog = None

    def on_value_dialog_ok(self, instance):
        # value = self.value_dialog.content_cls.value
        value = self.value_dialog.content_cls.ids.text_field.text
        if len(value):
            if self.value_dialog_data_key == 'jsz':
                self.jog_step_size = value
                self.list_items[self.value_dialog_data_key].text = "{}".format(self.jog_step_size)
            elif self.value_dialog_data_key == 'jfr':
                self.jog_feed_rate = value
                self.list_items[self.value_dialog_data_key].text = "{}".format(self.jog_feed_rate)
            elif self.value_dialog_data_key == 'jrpm':
                self.jog_spindle_rpm = value
                self.list_items[self.value_dialog_data_key].text = "{}".format(self.jog_spindle_rpm)
            elif self.value_dialog_data_key == 'server_config':
                self.server_hostname = self.value_dialog.content_cls.tf_server.text
                self.server_tcp_port = self.value_dialog.content_cls.tf_tcp_port.text
                self.server_udp_port = self.value_dialog.content_cls.tf_udp_port.text

        self.value_dialog.dismiss()
        self.value_dialog = None

    def on_value_dialog_value(self, instance, val):
        self.on_value_dialog_ok(instance)

    def on_value_dialog_rapid_button(self, instance):
        self.value_dialog.content_cls.ids.text_field.text = "Rapid"
        self.on_value_dialog_ok(instance)


class MDGridLayoutPlayControls(MDGridLayout):
    sw_state = ObjectProperty(None)
    serial_port_open = ObjectProperty(None)

    def __init__(self, **args):
        super(MDGridLayoutPlayControls, self).__init__(**args)

        self.gc = gc # for access via kv lang

    def on_cycle_start(self):
        if gc.gsatrc_remote_client:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_CYCLE_START)

    def on_hold(self):
        if gc.gsatrc_remote_client:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_FEED_HOLD)

    def on_pause(self):
        if gc.gsatrc_remote_client:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_PAUSE)

    def on_play(self):
        if gc.gsatrc_remote_client:
            runDict = dict()
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_RUN, runDict)

    def on_refresh(self):
        if gc.gsatrc_remote_client:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_GET_STATUS)

    def on_serial_port_open(self, instance, value):
        self.update_button_state()

    def on_step(self):
        if gc.gsatrc_remote_client:
            runDict = dict()
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_STEP, runDict)

    def on_stop(self):
        if gc.gsatrc_remote_client:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_STOP)

    def on_sw_state(self, instance, value):
        self.update_button_state()

    def update_button_state(self):
        if self.serial_port_open:
            self.ids.machine_refresh.disabled = False
            self.ids.machine_cycle_start.disabled = False
            self.ids.machine_hold.disabled = False

            if self.sw_state in [gc.STATE_RUN]:
                self.ids.play.disabled = True
                self.ids.step.disabled = True
                self.ids.pause.disabled = False
                self.ids.stop.disabled = False
            elif self.sw_state in [gc.STATE_PAUSE]:
                self.ids.play.disabled = False
                self.ids.step.disabled = False
                self.ids.pause.disabled = True
                self.ids.stop.disabled = False
            else:
                self.ids.play.disabled = False
                self.ids.step.disabled = False
                self.ids.pause.disabled = True
                self.ids.stop.disabled = True
        else:
            self.ids.play.disabled = True
            self.ids.pause.disabled = True
            self.ids.step.disabled = True
            self.ids.stop.disabled = True
            self.ids.machine_refresh.disabled = True
            self.ids.machine_cycle_start.disabled = True
            self.ids.machine_hold.disabled = True


class MDGridLayoutJogControls(MDGridLayout):
    sw_state = ObjectProperty(None)
    serial_port_open = ObjectProperty(None)

    def __init__(self, **args):
        super(MDGridLayoutJogControls, self).__init__(**args)

        self.gc = gc # for access via kv lang
        self.jog_step_size = ""
        self.jog_feed_rate = ""
        self.jog_spindle_rpm = ""

    def on_jog_home_axis(self, axis):
        if gc.gsatrc_remote_client:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_HOME, axis)

    def on_jog_move_absolute(self, axis):
        if gc.gsatrc_remote_client:
            if self.jog_feed_rate == "Rapid":
                gc_cmd = gc.EV_CMD_JOG_RAPID_MOVE
            else:
                gc_cmd = gc.EV_CMD_JOG_MOVE
                axis['feed'] = int(self.jog_feed_rate)
            gc.gsatrc_remote_client.add_event(gc_cmd, axis)

    def on_jog_move_relative(self, axis_str, direction):
        if gc.gsatrc_remote_client:
            step_size = float(self.jog_step_size)

            if direction<1:
                step_size = step_size * -1

            axis = {axis_str: step_size}
            if self.jog_feed_rate == "Rapid":
                gc_cmd = gc.EV_CMD_JOG_RAPID_MOVE_RELATIVE
            else:
                gc_cmd = gc.EV_CMD_JOG_MOVE_RELATIVE
                axis['feed'] = int(self.jog_feed_rate)
            gc.gsatrc_remote_client.add_event(gc_cmd, axis)

    def on_jog_probe(self, data):
        # TODO: doe spendant really need to keep this config??
        if gc.gsatrc_remote_client:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_SEND, data)

    def on_jog_send_cmd(self, data):
        if gc.gsatrc_remote_client:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_SEND, data)

    def on_jog_set_axis(self, axis):
        if gc.gsatrc_remote_client:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_SET_AXIS, axis)


class RootWidget(Screen, gc.EventQueueIf):
    serial_port_open = ObjectProperty(None)
    sw_state = ObjectProperty(None)

    def __init__(self, **args):
        super(RootWidget, self).__init__(**args)
        gc.EventQueueIf.__init__(self)

        # register events
        self.register_event_type('on_process_queue')

        # init variables
        self.gc = gc # for access via kv lang
        gc.gsatrc_remote_client = None
        self.device_detected = False
        self.jog_step_size = ""
        self.jog_feed_rate = ""
        self.jog_spindle_rpm = ""

        self.ids.dro_panel.bind(rc_connect=self.on_value_rc_connect)
        self.ids.dro_panel.bind(jog_step_size=self.on_value_jog_step_size)
        self.ids.dro_panel.bind(jog_feed_rate=self.on_value_jog_feed_rate)
        self.ids.dro_panel.bind(jog_spindle_rpm=self.on_value_jog_spindle_rpm)
        self.ids.dro_panel.bind(server_hostname=self.on_value_server_hostname)
        self.ids.dro_panel.bind(server_tcp_port=self.on_value_server_tcp_port)
        self.ids.dro_panel.bind(server_udp_port=self.on_value_server_udp_port)

        Clock.schedule_once(self.on_init)
        # self.on_init()

    def add_event(self, id, data=None, sender=None):
        gc.EventQueueIf.add_event(self, id, data, sender)
        self.dispatch('on_process_queue')

    def append_text(self, str_data):
        # self.text_out.text = self.text_out.text + str_data
        self.text_out.readonly = False
        self.text_out.do_cursor_movement('cursor_end', control=True)
        self.text_out.insert_text(str_data)
        self.text_out.readonly = True

    def on_open(self):
        if gc.gsatrc_remote_client is None:
            gc.gsatrc_remote_client = rc.RemoteClientThread(
                self, self.server_hostname, self.server_tcp_port, self.server_udp_port, True)

    def on_close(self):
        if gc.gsatrc_remote_client:
            gc.gsatrc_remote_client.add_event(gc.EV_CMD_EXIT)

    def on_init(self, *args):
        self.serial_port_open = False
        self.sw_state = gc.STATE_IDLE
        self.update_dro = self.ids.dro_panel.on_update
        self.text_out = self.ids.text_out
        self.update_dro({'swst': gc.get_sw_status_str(self.sw_state)})

    def on_stop(self):
        self.on_close()
        time.sleep(0.1)

    def on_serial_port_open(self, instance, value):
        self.ids.play_ctrl.serial_port_open = value
        self.ids.jog_ctrl.serial_port_open = value
        self.ids.dro_panel.serial_port_open = value

    def on_sw_state(self, instance, value):
        self.ids.play_ctrl.sw_state = value
        self.ids.jog_ctrl.sw_state = value

    def on_process_queue(self, *args):
        ''' Process evens on queue
        '''
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

                #     self.machineStatusPanel.UpdateUI(self.stateData, sr)
                #     self.machineJoggingPanel.UpdateUI(self.stateData, sr)

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
                        sys = r['sys']

                        if 'machif' in sys:
                            self.update_dro({'mi': sys['machif']})

                    if 'machif' in r:
                        self.update_dro({'mi': r['machif']})

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

                self.append_text("** MSG: {}\n".fromat(ev.data.strip()))

                # if lastSwState == gc.STATE_RUN:
                #     if sys.platform in 'darwin':
                #         # because dialog icons where not working correctly in
                #         # Mac OS X
                #         dlg = gmd.GenericMessageDialog(
                #             self, ev.data.strip() +
                #             "\n\nContinue program?", "G-Code Message",
                #             wx.YES_NO | wx.YES_DEFAULT |
                #             wx.ICON_INFORMATION)
                #     else:
                #         dlg = wx.MessageDialog(
                #             self, ev.data.strip() +
                #             "\n\nContinue program?", "G-Code Message",
                #             wx.YES_NO | wx.YES_DEFAULT |
                #             wx.ICON_INFORMATION)
                # else:
                #     if sys.platform in 'darwin':
                #         # because dialog icons where not working correctly in
                #         # Mac OS X
                #         dlg = gmd.GenericMessageDialog(
                #             self, ev.data.strip(),
                #             "G-Code Message", wx.OK | wx.ICON_INFORMATION)
                #     else:
                #         dlg = wx.MessageDialog(
                #             self, ev.data.strip(),
                #             "G-Code Message", wx.OK | wx.ICON_INFORMATION)

                # result = dlg.ShowModal()
                # dlg.Destroy()

                # if result == wx.ID_YES:
                #     self.OnRun()

            elif ev.event_id == gc.EV_SER_PORT_OPEN:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_SER_PORT_OPEN from 0x{:x} {}".format(id(ev.sender), ev.sender))

                self.serial_port_open = True

                if gc.gsatrc_remote_client is not None:
                    gc.gsatrc_remote_client.add_event(gc.EV_CMD_GET_STATUS)

            elif ev.event_id == gc.EV_SER_PORT_CLOSE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_SER_PORT_CLOSE from 0x{:x} {}".format(id(ev.sender), ev.sender))

                self.serial_port_open = False
                self.device_detected = False
                self.update_dro({'mi':""})

            elif ev.event_id == gc.EV_EXIT:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_EXIT from 0x{:x} {}".format(id(ev.sender), ev.sender))

                if id(ev.sender) == id(gc.gsatrc_remote_client):
                    gc.gsatrc_remote_client = None

                    gc.gsatrc_remote_client = None
                    self.serial_port_open = False
                    self.device_detected = False
                    self.sw_state = gc.STATE_IDLE
                    self.ids.dro_panel.rc_connect = False
                    self.update_dro({'rc':"", 'mi':"", 'swst': gc.get_sw_status_str(self.sw_state)})

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

                self.serial_port_open = False
                self.device_detected = False
                self.sw_state = gc.STATE_IDLE
                self.update_dro({'swst': gc.get_sw_status_str(self.sw_state)})

            elif ev.event_id == gc.EV_RMT_PORT_OPEN:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_RMT_PORT_OPEN from 0x{:x} {}".format(id(ev.sender), ev.sender))

                self.append_text(ev.data)

                if gc.gsatrc_remote_client is not None:
                    gc.gsatrc_remote_client.add_event(gc.EV_CMD_GET_SYSTEM_INFO)
                    gc.gsatrc_remote_client.add_event(gc.EV_CMD_GET_SW_STATE)

            elif ev.event_id == gc.EV_RMT_PORT_CLOSE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_RMT_PORT_CLOSE from 0x{:x} {}".format(id(ev.sender), ev.sender))

                self.append_text(ev.data)
                self.serial_port_open = False
                self.device_detected = False
                self.sw_state = gc.STATE_IDLE
                self.update_dro({'swst': gc.get_sw_status_str(self.sw_state)})

            elif  ev.event_id == gc.EV_RMT_CONFIG_DATA:
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

                # self.machifProgExecGcodeMd5 = ev.data

                # h = hashlib.md5(str([])).hexdigest()
                # if h != ev.data and self.machifProgExec is not None:
                #     h = hashlib.md5(str(self.stateData.gcodeFileLines)).hexdigest()
                #     if h != ev.data:
                #         self.machifProgExec.add_event(gc.EV_CMD_GET_GCODE)

            elif ev.event_id == gc.EV_GCODE:
                if gc.VERBOSE_MASK & gc.VERBOSE_MASK_UI_EV:
                    self.logger.info("EV_GCODE")

                # only if there is gcode we should do do something
                # if ev.data.get('gcodeLines', []):
                #     user_response = wx.ID_YES

                #     if self.gcText.GetModify():
                #         title = "Get Remote G-code"
                #         prompt = "Current G-code has been modified, save before overide?"
                #         if sys.platform in 'darwin':
                #             # because dialog icons where not working correctly in
                #             # Mac OS X
                #             dlg = gmd.GenericMessageDialog(
                #                 self, prompt, title,
                #                 wx.YES_NO | wx.CANCEL | wx.YES_DEFAULT | wx.ICON_QUESTION)
                #         else:
                #             dlg = wx.MessageDialog(
                #                 self, prompt, title,
                #                 wx.YES_NO | wx.CANCEL | wx.YES_DEFAULT | wx.ICON_QUESTION)


                #         user_response = dlg.ShowModal()
                #         if user_response == wx.ID_YES:
                #             self.OnFileSaveAs(None)

                #         dlg.Destroy()

                #     if user_response == wx.ID_CANCEL:
                #         # cancel G-code update from remote server
                #         pass
                #     else:
                #         if 'gcodeFileName' in ev.data:
                #             self.stateData.gcodeFileName = ev.data['gcodeFileName']
                #         else:
                #             self.stateData.gcodeFileName = ""

                #         self.SetTitle("{} - {}".format(os.path.basename(self.stateData.gcodeFileName), __appname__))
                #         self.statusbar.SetStatusText(os.path.basename(self.stateData.gcodeFileName))
                #         self.stateData.fileIsOpen = False

                #         if 'gcodeLines' in ev.data:
                #             readOnly = self.gcText.GetReadOnly()
                #             self.gcText.SetReadOnly(False)
                #             self.gcText.ClearAll()
                #             self.gcText.AddText("".join(ev.data['gcodeLines']))
                #             self.gcText.SetReadOnly(readOnly)
                #             self.gcText.DiscardEdits()
                #         else:
                #             readOnly = self.gcText.GetReadOnly()
                #             self.gcText.SetReadOnly(False)
                #             self.gcText.ClearAll()
                #             self.gcText.SetReadOnly(readOnly)
                #             self.gcText.DiscardEdits()

                #         rawText = self.gcText.GetText()
                #         self.stateData.gcodeFileLines = rawText.splitlines(True)
                #         h = hashlib.md5(str(self.stateData.gcodeFileLines)).hexdigest()
                #         self.machifProgExecGcodeMd5 = h

                #         if 'gcodePC' in ev.data:
                #             self.SetPC(ev.data['gcodePC'])
                #         else:
                #             self.SetPC(0)

                #         if 'breakPoints' in ev.data:
                #             break_points = ev.data['breakPoints']
                #             self.gcText.DeleteAllBreakPoints()
                #             for bp in break_points:
                #                 self.gcText.UpdateBreakPoint(bp, True)
                #         else:
                #             self.gcText.DeleteAllBreakPoints()

                #         self.gcText.GoToPC()
                #         self.UpdateUI()

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
        ''' Handle remote server open/close events from DRO panel
        '''
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


class MDBoxLayoutAutoRotate(MDBoxLayout):
    def __init__(self, **kwargs):
        super(MDBoxLayoutAutoRotate, self).__init__(**kwargs)

    def on_size(self, *args):
        if self.width > self.height:
            self.orientation = 'horizontal'
        else:
            self.orientation = 'vertical'

class MainApp(MDApp):
    def build(self):
        config = self.config
        # screen = Builder.load_string(kv_helper)
        # return screen
        return RootWidget()

    def build_config(self, config):
        config.setdefaults(__appname__, {
            'server_hostname': "hostname",
            'server_tcp_port': "61801",
            'server_udp_port': "61802",
            'jog_step_size': "1",
            'jog_feed_rate': "Rapid",
            'Jog_spindle_rpm': "18000"
        })

    def on_start(self):
        pass
        # self.config.update_config(self.config_file)

    def on_stop(self):
        self.root.on_stop()
        self.config.write()

    def get_color_random(self):
        return (random.random(), random.random(), random.random(), 1)

if __name__ == '__main__':
    MainApp().run()