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

        # 2. Считаем потребление (RSS - физическая память)
        # memory_info().rss возвращает байты, переводим в Мегабайты
        mem_bytes = process.memory_info().rss
        mem_mb = mem_bytes / (1024 * 1024)

        # 3. Нагрузка на CPU именно этим процессом
        # ВАЖНО: при первом вызове может вернуть 0.0, это нормально
        process_cpu = process.cpu_percent(interval=0.1)

        # 4. Данные из конфига и системы
        uptime_diff = int(time.time() - self.start_time)
        uptime = str(datetime.timedelta(seconds=uptime_diff))

        # Для сравнения оставим общую память системы
        total_ram = psutil.virtual_memory().percent

        vol = int(aiko_cfg.get("audio.master_volume", 0) * 100)
        mic_id = aiko_cfg.get("audio.device_index", "N/A")

        report = (
            f"=== 🛠 ДИАГНОСТИКА AIKO ===\n"
            f"👤 Имя: {aiko_cfg.get('bot.name')} | ⏱ Uptime: {uptime}\n | 🔊 Vol: {vol}% | 🎤 Mic: {mic_id}\n"
            f"💾 AiKo RAM: {mem_mb:.1f} MB (Система: {total_ram}%)\n"
            f"⚡ AiKo CPU: {process_cpu}% | 🧵 Threads: {threading.active_count()}\n"
            f"📥 Queue: {ctx.audio.audio_q.qsize() if hasattr(ctx, 'audio') else 'N/A'}\n"
            f"🧩 Plugins: {len(ctx.commands)} | 📄 State: {ctx.state.upper()}\n"
            f"=========================="
        )
        return report


    def execute(self, text: str, ctx) -> bool:
        # Сохраняем последнюю фразу в контекст для истории (опционально)
        ctx.last_phrase = text

        match, score = CommandMatcher.extract(text, [self.trigger], threshold=70, partial=True)

        if match:
            full_report = self.get_report(ctx)
            logger.info(f"\n{full_report}")
            ctx.ui_log(full_report, "info")
            return True

        return False