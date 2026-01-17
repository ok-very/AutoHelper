import os
import threading
import sys
from typing import Optional, Any

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
ScrollView = None
GridLayout = None

def _ensure_kivy_imported():
    """Import Kivy modules on demand."""
    global App, BoxLayout, Label, TextInput, Button, Window, Config, ScrollView, GridLayout
    if App is not None:
        return True
        
    try:
        from kivy.app import App
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.gridlayout import GridLayout
        from kivy.uix.scrollview import ScrollView
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
            self.padding = 20
            self.spacing = 15
            
            # Imports inside method to avoid early dependency issues if they use global state
            from autohelper.config.store import ConfigStore
            self.config_store = ConfigStore()
            self.current_config = self.config_store.load()

            # Font selection helper
            def get_system_font(preferences, fallback=None):
                """Find first available system font from preferences, downloading if needed."""
                import os
                import urllib.request
                
                font_dirs = [os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')]
                
                # Check for cached fonts in ./data/fonts
                cache_dir = os.path.join(os.getcwd(), 'data', 'fonts')
                if os.path.exists(cache_dir):
                    font_dirs.insert(0, cache_dir)
                
                # Map common names to probable filenames AND remote URLs
                font_map = {
                    'calibri': {'files': ['calibri.ttf', 'calibriz.ttf']}, 
                    'carlito': {
                        'files': ['carlito.ttf', 'Carlito-Regular.ttf'],
                        'url': 'https://github.com/google/fonts/raw/main/ofl/carlito/Carlito-Regular.ttf'
                    },
                    'arial': {'files': ['arial.ttf']},
                    'consolas': {'files': ['consola.ttf']},
                    'courier new': {'files': ['cour.ttf']},
                }

                for font_name in preferences:
                    font_name_lower = font_name.lower()
                    info = font_map.get(font_name_lower)
                    
                    if not info:
                         filenames = [f"{font_name}.ttf"]
                         url = None
                    else:
                        filenames = info['files']
                        url = info.get('url')
                    
                    # 1. Check local existence
                    for fname in filenames:
                        for fdir in font_dirs:
                            fpath = os.path.join(fdir, fname)
                            if os.path.exists(fpath):
                                return fpath
                    
                    # 2. Try download if URL exists (only for Carlito in this request)
                    if url:
                        try:
                            if not os.path.exists(cache_dir):
                                os.makedirs(cache_dir, exist_ok=True)
                            
                            # Use the first filename as target
                            target_name = filenames[0] 
                            target_path = os.path.join(cache_dir, target_name)
                            
                            # Double check if it exists in cache now (race condition or simple check)
                            if os.path.exists(target_path):
                                return target_path

                            print(f"Downloading font {font_name} from {url}...")
                            # Simple synchronous download - fine for startup of this popup
                            urllib.request.urlretrieve(url, target_path)
                            
                            if os.path.exists(target_path):
                                return target_path
                        except Exception as e:
                            print(f"Failed to download font {font_name}: {e}")
                
                return fallback

            # User Preferences: Calibri (> Carlito w/ download) > Arial
            self.label_font = get_system_font(['calibri', 'carlito', 'arial'], fallback='Arial') 
            
            # Input preference: Consolas > Courier New
            self.input_font = get_system_font(['consolas', 'courier new'], fallback='Consolas') 
            
            # Use found fonts
            label_font = self.label_font
            input_font = self.input_font
            
            # --- Header ---
            header = BoxLayout(size_hint_y=None, height=40)
            title = Label(
                text="AutoHelper Settings", 
                font_name=label_font,
                font_size='22sp', 
                bold=True,
                halign='left',
                valign='middle',
                text_size=(250, None) # Constraints for alignment
            )
            close_btn = Button(text="X", size_hint_x=None, width=40, background_color=(0.8, 0.2, 0.2, 1))
            close_btn.bind(on_press=self.cancel)
            
            header.add_widget(title)
            header.add_widget(close_btn)
            self.add_widget(header)

            # --- Scrollable Content ---
            scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
            content = BoxLayout(orientation='vertical', size_hint_y=None, spacing=15)
            content.bind(minimum_height=content.setter('height'))

            # Root Directories
            content.add_widget(Label(
                text="Allowed Roots (one per line):", 
                font_name=label_font, 
                size_hint_y=None, height=25, 
                halign='left', text_size=(310, None)
            ))
            
            roots_text = "\n".join(self.current_config.get("allowed_roots", []))
            self.roots_input = TextInput(
                text=roots_text, 
                multiline=True, 
                size_hint_y=None, 
                height=100,
                font_name=input_font,
                font_size='13sp',
                background_color=(0.95, 0.95, 0.95, 1)
            )
            content.add_widget(self.roots_input)

            # Excluded Extensions
            content.add_widget(Label(
                text="Excluded Extensions (csv):", 
                font_name=label_font, 
                size_hint_y=None, height=25, 
                halign='left', text_size=(310, None)
            ))
            
            excludes_text = ", ".join(self.current_config.get("excludes", []))
            self.exclude_input = TextInput(
                text=excludes_text, 
                multiline=False, 
                size_hint_y=None, 
                height=35,
                font_name=input_font,
                font_size='13sp'
            )
            content.add_widget(self.exclude_input)

            # Status Section
            self.status_label = Label(
                text="Status: Ready", 
                font_name=input_font,
                size_hint_y=None, 
                height=30, 
                color=(0.6, 0.6, 0.6, 1)
            )
            content.add_widget(self.status_label)
            
            scroll.add_widget(content)
            self.add_widget(scroll)

            # --- Actions ---
            # Index Management
            action_label = Label(text="Index Operations:", font_name=label_font, size_hint_y=None, height=25, halign='left', text_size=(310, None))
            self.add_widget(action_label)
            
            idx_actions = BoxLayout(size_hint_y=None, height=45, spacing=10)
            scan_btn = Button(text="Quick Scan", font_name=label_font, background_color=(0.2, 0.7, 0.4, 1))
            scan_btn.bind(on_press=self.on_scan)
            
            rebuild_btn = Button(text="Full Rebuild", font_name=label_font, background_color=(0.2, 0.5, 0.8, 1))
            rebuild_btn.bind(on_press=self.on_rebuild)
            
            idx_actions.add_widget(scan_btn)
            idx_actions.add_widget(rebuild_btn)
            self.add_widget(idx_actions)

            # --- Footer ---
            footer = BoxLayout(size_hint_y=None, height=50, spacing=10, padding=(0, 10, 0, 0))
            save_btn = Button(
                text="Save Settings", 
                font_name=label_font, 
                bold=True,
                background_color=(0.3, 0.3, 0.8, 1)
            )
            save_btn.bind(on_press=self.save_config)
            
            footer.add_widget(save_btn)
            self.add_widget(footer)

        def _is_font_available(self, font_name):
            # Kivy Core Label handles font finding, but simpler to rely on defaults 
            # unless we strictly know the font exists.
            # Returning False forces fallback to 'Roboto'/'RobotoMono' which Kivy provides.
            return False 

        def save_config(self, instance):
            """Validate and save configuration."""
            raw_roots = self.roots_input.text.strip().split('\n')
            valid_roots = []
            
            # Basic Validation
            for r in raw_roots:
                r = r.strip()
                if not r: 
                    continue
                if os.path.exists(r) and os.path.isdir(r):
                    valid_roots.append(r)
                else:
                    self.status_label.text = f"Error: Invalid Path '{r}'"
                    self.status_label.color = (1, 0, 0, 1)
                    return

            raw_excludes = self.exclude_input.text.split(',')
            valid_excludes = [e.strip() for e in raw_excludes if e.strip()]

            new_config = {
                "allowed_roots": valid_roots,
                "excludes": valid_excludes
            }
            
            try:
                self.config_store.save(new_config)
                self.status_label.text = "Settings Saved."
                self.status_label.color = (0, 1, 0, 1)
                
                # Optionally trigger reload here
                from autohelper.config.settings import reset_settings
                reset_settings()
                
            except Exception as e:
                self.status_label.text = f"Save Failed: {str(e)}"
                self.status_label.color = (1, 0, 0, 1)

        def on_rebuild(self, instance):
            self._run_async_action(self._do_rebuild, "Rebuild Started...")

        def on_scan(self, instance):
            self._run_async_action(self._do_scan, "Scanning...")

        def _run_async_action(self, func, start_msg):
            self.status_label.text = start_msg
            self.status_label.color = (1, 1, 0, 1)
            threading.Thread(target=func, daemon=True).start()

        def _do_rebuild(self):
            try:
                from autohelper.modules.index.service import IndexService
                svc = IndexService()
                svc.rebuild_index()
                self._update_status("Rebuild Complete", (0, 1, 0, 1))
            except Exception as e:
                self._update_status(f"Error: {str(e)}", (1, 0, 0, 1))

        def _do_scan(self):
            try:
                # For M0/M1, rescan is alias to rebuild or lighter scan
                from autohelper.modules.index.service import IndexService
                svc = IndexService()
                svc.rescan()
                self._update_status("Scan Complete", (0, 1, 0, 1))
            except Exception as e:
                self._update_status(f"Error: {str(e)}", (1, 0, 0, 1))

        def _update_status(self, text, color):
            # Kivy runs on main thread, this might need clock schedule if strict
            # But for simple property updates it often works or use Clock.schedule_once
            from kivy.clock import Clock
            def update(dt):
                self.status_label.text = text
                self.status_label.color = color
            Clock.schedule_once(update)

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
            # Hardcoded dark theme background
            Window.clearcolor = (0.1, 0.1, 0.1, 1)
            
            # Update size to be a bit taller for more content
            Window.size = (350, 500) 
            Window.borderless = True
            
            self._position_window()
            return ConfigLayoutClass(self)
        
        def _position_window(self):
            try:
                import ctypes
                user32 = ctypes.windll.user32
                screen_width = user32.GetSystemMetrics(0)
                screen_height = user32.GetSystemMetrics(1)
                # Taskbar assumption: ~40-50px at bottom
                taskbar_height = 48 
                
                win_w, win_h = Window.size
                
                # Bottom right, with margin
                target_x = screen_width - win_w - 10
                target_y = taskbar_height + 10 
                # Note: Kivy Window.top/left coordinate system can vary
                # Kivy usually uses top-left from top-left screen (SDL2)
                # But let's try setting via Window.left/top
                
                Window.left = target_x
                # Kivy top is distance from top of screen? 
                Window.top = screen_height - win_h - target_y
                
            except Exception:
                pass

    try:
        ConfigApp().run()
    except Exception as e:
        print(f"Error launching popup: {e}")

