import threading
import time
import psutil
import datetime
from interfaces import AikoCommand
from utils.matcher import CommandMatcher
from utils.logger import logger
from utils.config_manager import aiko_cfg

class SystemStatusCommand(AikoCommand):
    def __init__(self):
        self.trigger = "диагностика системы"
        self.start_time = time.time()
        logger.info("SystemStatusCommand: Инициализирован.")

    def get_report(self, ctx):
        process = psutil.Process()
        mem_bytes = process.memory_info().rss
        mem_mb = mem_bytes / (1024 * 1024)
        process_cpu = process.cpu_percent(interval=0.1)
        uptime_diff = int(time.time() - self.start_time)
        uptime = str(datetime.timedelta(seconds=uptime_diff))
        total_ram = psutil.virtual_memory().percent
        vol = int(aiko_cfg.get("audio.master_volume", 0) * 100)
        mic_id = aiko_cfg.get("audio.device_index", "N/A")

        # Добавим форматирование для Telegram (моноширинный шрифт через `...`)
        report = (
            f"🛠 **ДИАГНОСТИКА AIKO**\n"
            f"`--------------------------` \n"
            f"👤 Имя: {aiko_cfg.get('bot.name')} | ⏱ Uptime: {uptime}\n"
            f"🔊 Vol: {vol}% | 🎤 Mic: {mic_id}\n"
            f"💾 RAM: {mem_mb:.1f} MB (Sys: {total_ram}%)\n"
            f"⚡ CPU: {process_cpu}% | 🧵 Threads: {threading.active_count()}\n"
            f"🧩 Plugins: {len(ctx.commands)} | 📄 State: {ctx.state.upper()}\n"
            f"`--------------------------`"
        )
        return report

    def execute(self, text: str, ctx) -> bool:
        match, score = CommandMatcher.extract(text, [self.trigger], threshold=70, partial=True)

        if match:
            full_report = self.get_report(ctx)
            # УМНЫЙ ОТВЕТ: Айко сама поймет, куда слать — в консоль, в HUD или в Телеге ответить.
            # Если хочешь, чтобы диагностика ВСЕГДА дублировалась в телегу (даже при голосовом вызове),
            # поставь to_all=True
            ctx.reply(full_report, to_all=False)
            return True

        return False