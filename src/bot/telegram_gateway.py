# src/bot/telegram_gateway.py
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
import os

# Заглушки: подключи свою БД/оркестратор
TASKS = {}
NEXT_ID = 1

def kb(task_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="✅ Approve", callback_data=f"a:{task_id}")
    b.button(text="🔁 Rework", callback_data=f"r:{task_id}")
    b.button(text="❓ Clarify", callback_data=f"c:{task_id}")
    b.button(text="📄 Full report", callback_data=f"f:{task_id}")
    b.adjust(2,2)
    return b.as_markup()

async def run_bot():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing")
    bot = Bot(token=token)
    dp = Dispatcher()

    @dp.message(F.text.startswith("# TASK"))
    async def ingest(message: Message):
        global NEXT_ID
        task_id = NEXT_ID
        NEXT_ID += 1
        TASKS[task_id] = {"owner_text": message.text, "status": "NEW", "report": "Draft v1 (stub)"}
        await message.answer(f"Принято. Task #{task_id} в работе. Итог пришлю с кнопками.")

        # Stub: имитация результата
        TASKS[task_id]["status"] = "WAIT_OWNER"
        await message.answer(
            f"✅ Task #{task_id}: черновой результат готов (stub). Нужен апрув для EXECUTE.",
            reply_markup=kb(task_id),
        )

    @dp.callback_query(F.data.startswith(("a:","r:","c:","f:")))
    async def decision(cb: CallbackQuery):
        code, tid = cb.data.split(":")
        task_id = int(tid)
        if code == "f":
            await cb.message.answer(f"📄 Full report for Task #{task_id}:
{TASKS.get(task_id, {}).get('report','(нет)')}")
        else:
            TASKS.get(task_id, {})["decision"] = code
            await cb.message.answer(f"Решение по Task #{task_id}: {code}")
        await cb.answer()

    await dp.start_polling(bot)
