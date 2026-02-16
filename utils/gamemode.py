import psutil
import ctypes
import time
import os
import shutil
import subprocess


class GameMode:
    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.whitelist = [
            'explorer.exe', 'python.exe', 'py.exe',
            'conhost.exe',
        ]

    def _get_free_ram(self):
        return psutil.virtual_memory().available / (1024 * 1024)

    def _is_window_visible(self, pid):
        hwnds = []

        def callback(hwnd, extra):
            if self.user32.IsWindowVisible(hwnd):
                lp_pid = ctypes.c_ulong()
                self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lp_pid))
                if lp_pid.value == pid:
                    hwnds.append(hwnd)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        self.user32.EnumWindows(WNDENUMPROC(callback), 0)
        return len(hwnds) > 0

    def _clean_temp_files(self):
        temp_paths = [os.environ.get('TEMP'), r'C:\Windows\Temp']
        for path in temp_paths:
            if not path or not os.path.exists(path): continue
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                except:
                    continue

    def _toggle_services(self, stop=True):
        services = ["SysMain", "WSearch", "wuauserv"]
        action = "stop" if stop else "start"
        for service in services:
            try:
                subprocess.run(["sc", action, service], capture_output=True, check=False)
            except:
                continue

    def activate(self):
        """
        Запускает оптимизацию и возвращает словарь с результатами.
        """
        ram_before = self._get_free_ram()
        killed_list = []

        for proc in psutil.process_iter(['pid', 'name']):
            try:
                name = proc.info['name'].lower()
                pid = proc.info['pid']
                if name in self.whitelist:
                    continue
                if self._is_window_visible(pid):
                    proc.terminate()
                    killed_list.append(name)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        self._clean_temp_files()

        self._toggle_services(stop=True)

        time.sleep(2)
        ram_after = self._get_free_ram()

        result = {
            "status": "success",
            "ram_before": round(ram_before, 2),
            "ram_after": round(ram_after, 2),
            "freed_ram": round(max(0, ram_after - ram_before), 2),
            "killed_apps_count": len(killed_list),
            "killed_apps_names": killed_list,
            "services_stopped": True
        }
        return result


if __name__ == "__main__":
    gamemode = GameMode()
    stats = gamemode.activate()

    print(f"Освобождено: {stats['freed_ram']} MB")
    print(f"Закрыто программ: {stats['killed_apps_count']}")