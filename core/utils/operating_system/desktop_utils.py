import winreg
import ctypes

class DesktopUtils:
    _original_settings = None

    @staticmethod
    def _set_reg_value(key, subkey_path, name, value_type, value):
        try:
            # Ensure the subkey path exists or create it if necessary (though OpenKey won't create it)
            # For simplicity, we assume Control Panel\Desktop and Control Panel\Colors exist.
            reg_key = winreg.OpenKey(key, subkey_path, 0, winreg.KEY_WRITE)
            winreg.SetValueEx(reg_key, name, 0, value_type, value)
            winreg.CloseKey(reg_key)
            return True
        except FileNotFoundError:
            print(f"[ERROR][DesktopUtils] Registry path not found: {subkey_path}")
            return False
        except Exception as e:
            print(f"[ERROR][DesktopUtils] Failed to set registry value {name} at {subkey_path}: {e}")
            return False

    @staticmethod
    def _get_reg_value(key, subkey_path, name):
        try:
            reg_key = winreg.OpenKey(key, subkey_path, 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(reg_key, name)
            winreg.CloseKey(reg_key)
            return value
        except FileNotFoundError:
            # This is not an error if a wallpaper was never set (solid color by default)
            # print(f"[INFO][DesktopUtils] Registry value {name} not found at {subkey_path}, returning None.")
            return None
        except Exception as e:
            print(f"[ERROR][DesktopUtils] Failed to get registry value {name} from {subkey_path}: {e}")
            return None

    @staticmethod
    def get_desktop_background_settings():
        if DesktopUtils._original_settings is not None:
            # Already have settings, possibly from a previous call in the same session that wasn't restored
            print("[INFO][DesktopUtils] Using already stored original desktop settings.")
            return DesktopUtils._original_settings

        settings = {}
        control_panel_desktop = r"Control Panel\Desktop"
        colors_path = r"Control Panel\Colors"
        try:
            settings['Wallpaper'] = DesktopUtils._get_reg_value(winreg.HKEY_CURRENT_USER, control_panel_desktop, "Wallpaper")
            settings['WallpaperStyle'] = DesktopUtils._get_reg_value(winreg.HKEY_CURRENT_USER, control_panel_desktop, "WallpaperStyle")
            settings['TileWallpaper'] = DesktopUtils._get_reg_value(winreg.HKEY_CURRENT_USER, control_panel_desktop, "TileWallpaper")
            settings['Background'] = DesktopUtils._get_reg_value(winreg.HKEY_CURRENT_USER, colors_path, "Background")
            
            DesktopUtils._original_settings = settings.copy()
            print(f"[INFO][DesktopUtils] Stored original desktop settings: Wallpaper='{settings.get('Wallpaper', 'N/A')}', Style='{settings.get('WallpaperStyle', 'N/A')}', Tile='{settings.get('TileWallpaper', 'N/A')}', Color='{settings.get('Background', 'N/A')}'")
            return settings
        except Exception as e:
            print(f"[ERROR][DesktopUtils] Failed to get original desktop settings: {e}")
            DesktopUtils._original_settings = None 
            return None

    @staticmethod
    def set_desktop_background_solid_color(r=0, g=0, b=0):
        if DesktopUtils._original_settings is None:
            DesktopUtils.get_desktop_background_settings() # Ensure original settings are stored if not already

        color_str = f"{r} {g} {b}"
        control_panel_desktop = r"Control Panel\Desktop"
        colors_path = r"Control Panel\Colors"

        print(f"[INFO][DesktopUtils] Setting desktop background to solid color: RGB({color_str})")
        DesktopUtils._set_reg_value(winreg.HKEY_CURRENT_USER, control_panel_desktop, "Wallpaper", winreg.REG_SZ, "")
        DesktopUtils._set_reg_value(winreg.HKEY_CURRENT_USER, control_panel_desktop, "WallpaperStyle", winreg.REG_SZ, "2") # 2 for Stretch/Fill
        DesktopUtils._set_reg_value(winreg.HKEY_CURRENT_USER, control_panel_desktop, "TileWallpaper", winreg.REG_SZ, "0") # 0 for not tiled
        DesktopUtils._set_reg_value(winreg.HKEY_CURRENT_USER, colors_path, "Background", winreg.REG_SZ, color_str)

        # Constants for SystemParametersInfoW
        SPI_SETDESKWALLPAPER = 0x0014 # 20
        SPIF_UPDATEINIFILE = 0x0001
        SPIF_SENDWININICHANGE = 0x0002 # Same as SPIF_SENDCHANGE

        # Call SystemParametersInfoW to apply changes
        # For solid color, path should be empty string or None.
        # The documentation is a bit unclear if "" or None is better. Let's try None.
        # ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, None, SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE)
        # Using an empty string for the path is often more reliable for clearing wallpaper:
        ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, "", SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE)
        print(f"[INFO][DesktopUtils] Desktop background set command issued.")

    @staticmethod
    def restore_desktop_background_settings():
        if DesktopUtils._original_settings is None:
            print("[WARNING][DesktopUtils] No original desktop settings found to restore.")
            return

        settings = DesktopUtils._original_settings
        control_panel_desktop = r"Control Panel\Desktop"
        colors_path = r"Control Panel\Colors"
        
        wallpaper_path = settings.get('Wallpaper', "") # Default to empty if None
        
        print(f"[INFO][DesktopUtils] Restoring desktop settings: Wallpaper='{wallpaper_path}', Style='{settings.get('WallpaperStyle')}', Tile='{settings.get('TileWallpaper')}', Color='{settings.get('Background')}'")

        if settings.get('Wallpaper') is not None: # If there was a wallpaper
            DesktopUtils._set_reg_value(winreg.HKEY_CURRENT_USER, control_panel_desktop, "Wallpaper", winreg.REG_SZ, wallpaper_path)
        else: # If original was solid color, ensure wallpaper path is empty
            DesktopUtils._set_reg_value(winreg.HKEY_CURRENT_USER, control_panel_desktop, "Wallpaper", winreg.REG_SZ, "")

        if settings.get('WallpaperStyle') is not None:
            DesktopUtils._set_reg_value(winreg.HKEY_CURRENT_USER, control_panel_desktop, "WallpaperStyle", winreg.REG_SZ, settings['WallpaperStyle'])
        if settings.get('TileWallpaper') is not None:
            DesktopUtils._set_reg_value(winreg.HKEY_CURRENT_USER, control_panel_desktop, "TileWallpaper", winreg.REG_SZ, settings['TileWallpaper'])
        
        # Restore original background color only if it was set
        if settings.get('Background') is not None:
            DesktopUtils._set_reg_value(winreg.HKEY_CURRENT_USER, colors_path, "Background", winreg.REG_SZ, settings['Background'])

        SPI_SETDESKWALLPAPER = 0x0014
        SPIF_UPDATEINIFILE = 0x0001
        SPIF_SENDWININICHANGE = 0x0002
        
        # Crucially, SystemParametersInfoW needs the path to the wallpaper file to restore it.
        # If the original was a solid color, wallpaper_path might be "" or None.
        # If wallpaper_path is empty, it should revert to the color specified by HKEY_CURRENT_USER\Control Panel\Colors\Background
        ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, wallpaper_path if wallpaper_path else None, SPIF_UPDATEINIFILE | SPIF_SENDWININICHANGE)
        
        print("[INFO][DesktopUtils] Desktop background settings restoration command issued.")
        DesktopUtils._original_settings = None # Clear after restoring to allow fresh fetch next time
