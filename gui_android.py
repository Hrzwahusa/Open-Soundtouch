#!/usr/bin/env python3
"""
SoundTouch GUI for Android
Kivy-based GUI for controlling Bose SoundTouch devices on Android.
Build with: buildozer android debug
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.slider import Slider
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.properties import StringProperty, NumericProperty
from kivy.core.window import Window
from soundtouch_lib import SoundTouchDiscovery, SoundTouchController
import json
import os
import threading


class SoundTouchGUI(BoxLayout):
    """Main GUI layout for SoundTouch control."""
    
    current_track = StringProperty("Track: -")
    current_artist = StringProperty("Artist: -")
    current_album = StringProperty("Album: -")
    current_source = StringProperty("Source: -")
    volume_value = NumericProperty(50)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 10
        self.spacing = 10
        
        self.devices = []
        self.current_device = None
        self.controller = None
        self.scanning = False
        
        # Build UI
        self.build_device_selection()
        self.build_tabs()
        
        # Auto-update
        Clock.schedule_interval(self.update_now_playing, 2)
        
        # Load saved devices
        self.load_saved_devices()
        
    def build_device_selection(self):
        """Build device selection area."""
        device_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=50, spacing=10)
        
        device_layout.add_widget(Label(text='Gerät:', size_hint_x=0.2))
        
        self.device_spinner = Spinner(
            text='Gerät auswählen...',
            values=[],
            size_hint_x=0.5
        )
        self.device_spinner.bind(text=self.on_device_selected)
        device_layout.add_widget(self.device_spinner)
        
        scan_btn = Button(
            text='Scan',
            size_hint_x=0.3,
            background_color=(0.3, 0.6, 0.3, 1)
        )
        scan_btn.bind(on_press=self.scan_devices)
        device_layout.add_widget(scan_btn)
        
        self.add_widget(device_layout)
        
        # Status label
        self.status_label = Label(
            text='Bereit',
            size_hint_y=None,
            height=30,
            color=(0.5, 0.5, 0.5, 1)
        )
        self.add_widget(self.status_label)
        
    def build_tabs(self):
        """Build tabbed interface."""
        tabs = TabbedPanel(do_default_tab=False)
        
        # Control tab
        control_tab = TabbedPanelItem(text='Steuerung')
        control_tab.add_widget(self.build_control_panel())
        tabs.add_widget(control_tab)
        
        # Groups tab
        groups_tab = TabbedPanelItem(text='Gruppen')
        groups_tab.add_widget(self.build_groups_panel())
        tabs.add_widget(groups_tab)
        
        # Info tab
        info_tab = TabbedPanelItem(text='Info')
        info_tab.add_widget(self.build_info_panel())
        tabs.add_widget(info_tab)
        
        self.add_widget(tabs)
        
    def build_control_panel(self):
        """Build main control panel."""
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        scroll = ScrollView()
        content = BoxLayout(orientation='vertical', size_hint_y=None, spacing=15)
        content.bind(minimum_height=content.setter('height'))
        
        # Now Playing section
        now_playing = BoxLayout(orientation='vertical', size_hint_y=None, height=150, spacing=5)
        now_playing.add_widget(Label(
            text='[b]Aktuelle Wiedergabe[/b]',
            markup=True,
            size_hint_y=None,
            height=30
        ))
        
        self.track_label = Label(text=self.current_track, size_hint_y=None, height=25)
        self.artist_label = Label(text=self.current_artist, size_hint_y=None, height=25)
        self.album_label = Label(text=self.current_album, size_hint_y=None, height=25)
        self.source_label = Label(text=self.current_source, size_hint_y=None, height=25)
        
        self.bind(current_track=self.track_label.setter('text'))
        self.bind(current_artist=self.artist_label.setter('text'))
        self.bind(current_album=self.album_label.setter('text'))
        self.bind(current_source=self.source_label.setter('text'))
        
        now_playing.add_widget(self.track_label)
        now_playing.add_widget(self.artist_label)
        now_playing.add_widget(self.album_label)
        now_playing.add_widget(self.source_label)
        content.add_widget(now_playing)
        
        # Playback controls
        playback = GridLayout(cols=4, size_hint_y=None, height=60, spacing=5)
        playback.add_widget(self.create_button('⏮', 'PREV_TRACK'))
        playback.add_widget(self.create_button('▶', 'PLAY'))
        playback.add_widget(self.create_button('⏸', 'PAUSE'))
        playback.add_widget(self.create_button('⏭', 'NEXT_TRACK'))
        content.add_widget(playback)
        
        # Volume control
        volume_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=50, spacing=10)
        volume_layout.add_widget(Label(text='Vol:', size_hint_x=0.15))
        
        self.volume_slider = Slider(
            min=0,
            max=100,
            value=self.volume_value,
            size_hint_x=0.7
        )
        self.volume_slider.bind(value=self.on_volume_changed)
        volume_layout.add_widget(self.volume_slider)
        
        self.volume_label = Label(text='50', size_hint_x=0.15)
        self.bind(volume_value=lambda _, v: setattr(self.volume_label, 'text', str(int(v))))
        volume_layout.add_widget(self.volume_label)
        
        content.add_widget(volume_layout)
        
        # Presets
        content.add_widget(Label(
            text='[b]Presets[/b]',
            markup=True,
            size_hint_y=None,
            height=30
        ))
        presets = GridLayout(cols=3, size_hint_y=None, height=120, spacing=5)
        for i in range(1, 7):
            presets.add_widget(self.create_button(f'P{i}', f'PRESET_{i}'))
        content.add_widget(presets)
        
        # Additional controls
        content.add_widget(Label(
            text='[b]Weitere Steuerung[/b]',
            markup=True,
            size_hint_y=None,
            height=30
        ))
        extra = GridLayout(cols=2, size_hint_y=None, height=120, spacing=5)
        extra.add_widget(self.create_button('Power', 'POWER'))
        extra.add_widget(self.create_button('Mute', 'MUTE'))
        extra.add_widget(self.create_button('Shuffle', 'SHUFFLE_ON'))
        extra.add_widget(self.create_button('Repeat', 'REPEAT_ALL'))
        content.add_widget(extra)
        
        scroll.add_widget(content)
        layout.add_widget(scroll)
        return layout
        
    def build_info_panel(self):
        """Build info display panel."""
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        scroll = ScrollView()
        self.info_label = Label(
            text='Wähle ein Gerät aus',
            markup=True,
            size_hint_y=None,
            valign='top',
            text_size=(Window.width - 40, None)
        )
        self.info_label.bind(texture_size=self.info_label.setter('size'))
        scroll.add_widget(self.info_label)
        
        layout.add_widget(scroll)
        
        refresh_btn = Button(
            text='Aktualisieren',
            size_hint_y=None,
            height=50,
            background_color=(0.3, 0.6, 0.3, 1)
        )
        refresh_btn.bind(on_press=lambda x: self.update_device_info())
        layout.add_widget(refresh_btn)
        
        return layout
        
    def build_groups_panel(self):
        """Build groups panel (simplified for Android)."""
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        layout.add_widget(Label(
            text='[b]Multi-Room Gruppen[/b]',
            markup=True,
            size_hint_y=None,
            height=40,
            font_size='18sp'
        ))
        
        layout.add_widget(Label(
            text='Wähle mehrere Geräte um sie zu synchronisieren:',
            size_hint_y=None,
            height=30,
            color=(0.6, 0.6, 0.6, 1)
        ))
        
        # Device checkboxes
        scroll = ScrollView()
        self.group_content = BoxLayout(orientation='vertical', size_hint_y=None, spacing=5)
        self.group_content.bind(minimum_height=self.group_content.setter('height'))
        scroll.add_widget(self.group_content)
        layout.add_widget(scroll)
        
        # Group actions
        actions = BoxLayout(orientation='horizontal', size_hint_y=None, height=60, spacing=10)
        
        create_group_btn = Button(
            text='Gruppe erstellen',
            background_color=(0.3, 0.6, 0.3, 1)
        )
        create_group_btn.bind(on_press=self.create_simple_group)
        actions.add_widget(create_group_btn)
        
        layout.add_widget(actions)
        
        # Update device list for groups
        self.update_group_devices()
        
        return layout
        
    def update_group_devices(self):
        """Update device list in groups panel."""
        if not hasattr(self, 'group_content'):
            return
            
        self.group_content.clear_widgets()
        
        from kivy.uix.checkbox import CheckBox
        
        for device in self.devices:
            row = BoxLayout(orientation='horizontal', size_hint_y=None, height=40)
            
            checkbox = CheckBox(size_hint_x=0.2)
            checkbox.device = device
            row.add_widget(checkbox)
            
            label = Label(
                text=f"{device['name']} ({device['ip']})",
                size_hint_x=0.8,
                halign='left',
                valign='middle'
            )
            label.bind(size=label.setter('text_size'))
            row.add_widget(label)
            
            self.group_content.add_widget(row)
            
    def create_simple_group(self, instance):
        """Create a simple group from selected devices."""
        from soundtouch_lib import SoundTouchGroupManager
        
        # Collect selected devices
        selected = []
        for child in self.group_content.children:
            if hasattr(child, 'children') and len(child.children) > 0:
                checkbox = child.children[1]  # First child (reversed order)
                if hasattr(checkbox, 'active') and checkbox.active and hasattr(checkbox, 'device'):
                    selected.append(checkbox.device)
        
        if len(selected) < 2:
            self.show_error("Bitte wähle mindestens 2 Geräte aus")
            return
            
        # First device is master
        master = selected[0]
        slaves = selected[1:]
        
        try:
            group_manager = SoundTouchGroupManager(self.devices)
            success = group_manager.create_group(master, slaves, f"Gruppe {len(selected)} Geräte")
            
            if success:
                popup = Popup(
                    title='Erfolg',
                    content=Label(text=f'Gruppe mit {len(selected)} Geräten erstellt!\nMaster: {master["name"]}'),
                    size_hint=(0.8, 0.4)
                )
                popup.open()
            else:
                self.show_error("Gruppe konnte nicht erstellt werden")
        except Exception as e:
            self.show_error(f"Fehler: {e}")
        
    def create_button(self, text, key):
        """Create a button that sends a key command."""
        btn = Button(
            text=text,
            background_color=(0.2, 0.5, 0.8, 1),
            font_size='16sp'
        )
        btn.bind(on_press=lambda x: self.send_key(key))
        return btn
        
    def scan_devices(self, instance):
        """Start device scanning in background thread."""
        if self.scanning:
            return
            
        self.scanning = True
        self.status_label.text = 'Scanne Netzwerk...'
        
        def scan_thread():
            try:
                discovery = SoundTouchDiscovery()
                devices = discovery.scan(max_threads=30)
                Clock.schedule_once(lambda dt: self.on_devices_found(devices))
            except Exception as e:
                Clock.schedule_once(lambda dt: self.show_error(f"Scan-Fehler: {e}"))
            finally:
                self.scanning = False
                
        threading.Thread(target=scan_thread, daemon=True).start()
        
    def on_devices_found(self, devices):
        """Handle found devices."""
        self.devices = devices
        
        device_names = []
        for device in devices:
            name = f"{device['name']} ({device['ip']})"
            device_names.append(name)
            
        self.device_spinner.values = device_names
        
        if devices:
            self.device_spinner.text = device_names[0]
            self.save_devices()
            self.status_label.text = f'{len(devices)} Gerät(e) gefunden'
            # Update group devices list
            self.update_group_devices()
        else:
            self.status_label.text = 'Keine Geräte gefunden'
            
    def on_device_selected(self, spinner, text):
        """Handle device selection."""
        if text == 'Gerät auswählen...' or not self.devices:
            return
            
        # Find device by display name
        for device in self.devices:
            if device['ip'] in text:
                self.current_device = device
                self.controller = SoundTouchController(device['ip'])
                self.status_label.text = f"Verbunden: {device['name']}"
                self.update_now_playing(0)
                self.update_device_info()
                break
                
    def send_key(self, key):
        """Send key command to device."""
        if not self.controller:
            self.show_error("Bitte wähle zuerst ein Gerät aus")
            return
            
        try:
            success = self.controller.send_key(key)
            if success:
                self.status_label.text = f"Befehl '{key}' gesendet"
                Clock.schedule_once(self.update_now_playing, 0.5)
            else:
                self.show_error(f"Fehler beim Senden von '{key}'")
        except Exception as e:
            self.show_error(f"Fehler: {e}")
            
    def on_volume_changed(self, instance, value):
        """Handle volume change."""
        self.volume_value = value
        if self.controller:
            try:
                self.controller.set_volume(int(value))
            except Exception as e:
                print(f"Volume error: {e}")
                
    def update_now_playing(self, dt):
        """Update now playing information."""
        if not self.controller:
            return
            
        try:
            info = self.controller.get_nowplaying()
            if info:
                self.current_track = f"Track: {info['track']}"
                self.current_artist = f"Artist: {info['artist']}"
                self.current_album = f"Album: {info['album']}"
                self.current_source = f"Source: {info['source']}"
                
            # Update volume
            volume = self.controller.get_volume()
            if volume is not None:
                self.volume_value = volume['actualvolume']
                self.volume_slider.value = volume['actualvolume']
        except Exception as e:
            pass
            
    def update_device_info(self):
        """Update device information display."""
        if not self.current_device:
            return
            
        info_text = f"""[b]{self.current_device['name']}[/b]

[b]Typ:[/b] {self.current_device['type']}
[b]IP:[/b] {self.current_device['ip']}
[b]MAC:[/b] {self.current_device['mac']}
[b]Device ID:[/b] {self.current_device['deviceID']}
[b]URL:[/b] {self.current_device['url']}

[b]Komponenten:[/b]
"""
        
        if 'components' in self.current_device:
            for comp in self.current_device['components']:
                info_text += f"\n• {comp['category']}\n  {comp.get('version', 'N/A')}\n"
                
        self.info_label.text = info_text
        self.info_label.text_size = (Window.width - 40, None)
        
    def load_saved_devices(self):
        """Load devices from saved file."""
        try:
            if os.path.exists('soundtouch_devices.json'):
                with open('soundtouch_devices.json', 'r') as f:
                    devices = json.load(f)
                    if devices:
                        self.on_devices_found(devices)
        except Exception as e:
            print(f"Error loading devices: {e}")
            
    def save_devices(self):
        """Save current devices to file."""
        try:
            with open('soundtouch_devices.json', 'w') as f:
                json.dump(self.devices, f, indent=2)
        except Exception as e:
            print(f"Error saving devices: {e}")
            
    def show_error(self, message):
        """Show error popup."""
        popup = Popup(
            title='Fehler',
            content=Label(text=message),
            size_hint=(0.8, 0.3)
        )
        popup.open()


class SoundTouchApp(App):
    """Main Kivy application."""
    
    def build(self):
        """Build the application."""
        self.title = 'SoundTouch Controller'
        Window.clearcolor = (0.95, 0.95, 0.95, 1)
        return SoundTouchGUI()


if __name__ == '__main__':
    SoundTouchApp().run()
