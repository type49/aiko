import re
import pythoncom
from interfaces import AikoCommand
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume


class VolumePlugin(AikoCommand):
    def __init__(self):
        self.words_map = {
            "ноль": 0, "десять": 10, "двадцать": 20, "тридцать": 30,
            "сорок": 40, "пятьдесят": 50, "шестьдесят": 60,
            "семьдесят": 70, "восемьдесят": 80, "девяносто": 90, "сто": 100
        }

    def _get_volume_control(self):
        try:
            pythoncom.CoInitialize()
            # Используем GetDeviceEnumerator напрямую через AudioUtilities
            enumerator = AudioUtilities.GetDeviceEnumerator()
            # 0: eRender (динамики), 0: eMultimedia (роль устройства)
            devices = enumerator.GetDefaultAudioEndpoint(0, 0)
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return cast(interface, POINTER(IAudioEndpointVolume))
        except Exception as e:
            print(f"[VOLUME ERROR]: {e}")
            return None

    def execute(self, text, ctx):
        text = text.lower()
        # Проверяем, относится ли фраза к громкости
        if not any(word in text for word in ["громкость", "тише", "громче", "звук"]):
            return False

        volume_ctrl = self._get_volume_control()
        if not volume_ctrl:
            return False

        try:
            level = None
            digit_match = re.search(r'(\d+)', text)

            if digit_match:
                level = int(digit_match.group(1))
            else:
                for word, val in self.words_map.items():
                    if word in text:
                        level = val
                        break

            # Установка громкости (Громкость 50)
            if level is not None and "громкость" in text:
                level = max(0, min(100, level))
                volume_ctrl.SetMasterVolumeLevelScalar(level / 100.0, None)
                self._notify(ctx, f"Громкость: {level}%")
                return True

            # Относительное изменение
            current = volume_ctrl.GetMasterVolumeLevelScalar()
            if "тише" in text:
                new_level = max(0.0, current - 0.1)
                volume_ctrl.SetMasterVolumeLevelScalar(new_level, None)
                self._notify(ctx, f"Громкость: {int(new_level * 100)}%")
                return True

            if "громче" in text:
                new_level = min(1.0, current + 0.1)
                volume_ctrl.SetMasterVolumeLevelScalar(new_level, None)
                self._notify(ctx, f"Громкость: {int(new_level * 100)}%")
                return True

        except Exception as e:
            print(f"[VOLUME EXEC ERROR]: {e}")
        finally:
            pythoncom.CoUninitialize()

        return False

    def _notify(self, ctx, msg):
        if hasattr(ctx, 'ui_callback'):
            ctx.ui_callback(msg)