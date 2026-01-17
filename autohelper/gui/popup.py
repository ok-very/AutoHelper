import os
import threading
import sys
from typing import Optional

# Set Kivy environment variables to prevent early window creation/console logging
os.environ['KIVY_NO_CONSOLELOG'] = '1'
os.environ['KIVY_NO_ARGS'] = '1'

# Lazy loaded modules
App = None
BoxLayout = None
Label = None
TextInput = None
Button = None
Window = None
Config = None

def _ensure_kivy_imported():
    """Import Kivy modules on demand."""
    global App, BoxLayout, Label, TextInput, Button, Window, Config
    if App is not None:
        return True
        
    try:
        from kivy.app import App
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.textinput import TextInput
        from kivy.uix.button import Button
        from kivy.core.window import Window
        from kivy.config import Config
        return True
    except ImportError:
        print("Warning: Kivy not installed. GUI features unavailable.")
        return False

class ConfigLayout(object): # Placeholder until instantiated
    pass

def get_config_layout_class():
    if not _ensure_kivy_imported():
        return None

    class InternalConfigLayout(BoxLayout):
        def __init__(self, app_instance, **kwargs):
            super().__init__(**kwargs)
            self.app = app_instance
            self.orientation = 'vertical'
            self.padding = 15
            self.spacing = 10

            # Font settings
            label_font = 'Carlito' if self._is_font_available('Carlito') else 'Roboto'
            input_font = 'Consolas' if self._is_font_available('Consolas') else 'RobotoMono'
            
            # Title
            self.add_widget(Label(
                text="Index Configuration", 
                font_name=label_font,
                font_size='20sp', 
                size_hint_y=None, 
                height=40, 
                bold=True
            ))

            # Root Path
            self.add_widget(Label(text="Root Directory:", font_name=label_font, size_hint_y=None, height=25, halign='left', text_size=(320, None)))
            self.root_input = TextInput(
                text=os.getcwd(), 
                multiline=False, 
                size_hint_y=None, 
                height=35,
                font_name=input_font,
                font_size='14sp'
            )
            self.add_widget(self.root_input)

            # Excluded Extensions
            self.add_widget(Label(text="Excluded Extensions:", font_name=label_font, size_hint_y=None, height=25, halign='left', text_size=(320, None)))
            self.exclude_input = TextInput(
                text="pyc, __pycache__, git", 
                multiline=False, 
                size_hint_y=None, 
                height=35,
                font_name=input_font,
                font_size='14sp'
            )
            self.add_widget(self.exclude_input)

            # Index Status
            self.add_widget(Label(
                text="Index Status: Idle", 
                font_name=input_font,
                size_hint_y=None, 
                height=25, 
                color=(0.7, 0.7, 0.7, 1)
            ))

            # Actions
            action_layout = BoxLayout(size_hint_y=None, height=40, spacing=10)
            rebuild_btn = Button(text="Rebuild", font_name=label_font, background_color=(0.2, 0.6, 0.8, 1))
            rescan_btn = Button(text="Rescan", font_name=label_font, background_color=(0.2, 0.8, 0.4, 1))
            action_layout.add_widget(rebuild_btn)
            action_layout.add_widget(rescan_btn)
            self.add_widget(action_layout)

            # Spacer
            self.add_widget(Label())

            # Bottom Buttons
            btn_layout = BoxLayout(size_hint_y=None, height=40, spacing=10)
            save_btn = Button(text="Save", font_name=label_font)
            save_btn.bind(on_press=self.save_config)
            cancel_btn = Button(text="Cancel", font_name=label_font)
            cancel_btn.bind(on_press=self.cancel)
            
            btn_layout.add_widget(save_btn)
            btn_layout.add_widget(cancel_btn)
            self.add_widget(btn_layout)

        def _is_font_available(self, font_name):
            # Very basic check, Kivy usually falls back gracefully
            return True 

        def save_config(self, instance):
            print(f"Saving config: Root={self.root_input.text}")
            self.app.stop()

        def cancel(self, instance):
            self.app.stop()
            
    return InternalConfigLayout

def launch_config_popup():
    """Launch the configuration popup."""
    if not _ensure_kivy_imported():
        return

    ConfigLayoutClass = get_config_layout_class()

    class ConfigApp(App):
        def build(self):
            self.title = "AutoHelper Settings"
            
            # Configure Window
            Window.size = (350, 450) # Narrower
            Window.borderless = True
            
            # Position at bottom right
            try:
                import ctypes
                user32 = ctypes.windll.user32
                screen_width = user32.GetSystemMetrics(0)
                screen_height = user32.GetSystemMetrics(1)
                taskbar_height = 50 
                
                Window.left = screen_width - 350 - 20
                Window.top = screen_height - 450 - taskbar_height
            except Exception:
                pass
                
            return ConfigLayoutClass(self)
        
        def on_start(self):
            # Ensure position is enforced after window creation
            pass

    try:
        ConfigApp().run()
    except Exception as e:
        print(f"Error launching popup: {e}")
