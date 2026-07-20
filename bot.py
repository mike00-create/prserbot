import asyncio
import logging
from datetime import datetime
from typing import Dict, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

from config import Config
from database import Database
from parser import TelegramParser

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class ParserBot:
    def __init__(self):
        self.config = Config()
        self.db = Database(self.config.DATABASE_FILE)
        self.parser = TelegramParser(self.config, self.db)
        self.user_sessions = {}  # Временные данные пользователей
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user_id = update.effective_user.id
        
        # Проверка доступа
        if user_id not in self.config.ALLOWED_USERS:
            await update.message.reply_text(
                "⛔ У вас нет доступа к этому боту.\n"
                "Пожалуйста, свяжитесь с администратором."
            )
            return
        
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("📋 Мои чаты", callback_data="list_chats")],
            [InlineKeyboardButton("➕ Добавить чат", callback_data="add_chat")],
            [InlineKeyboardButton("▶️ Запустить парсинг", callback_data="run_parser")],
            [InlineKeyboardButton("📥 Последние сообщения", callback_data="last_messages")],
            [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🤖 **Бот для управления парсером Telegram**\n\n"
            "Я помогу вам отслеживать сообщения в чатах и каналах.\n"
            "Выберите действие из меню ниже:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопок"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        if user_id not in self.config.ALLOWED_USERS:
            await query.edit_message_text("⛔ Доступ запрещен")
            return
        
        data = query.data
        
        if data == "stats":
            await self.show_stats(query)
        elif data == "list_chats":
            await self.list_chats(query)
        elif data == "add_chat":
            await self.add_chat_prompt(query)
        elif data == "run_parser":
            await self.run_parser(query)
        elif data == "last_messages":
            await self.show_last_messages(query)
        elif data == "settings":
            await self.show_settings(query)
        elif data.startswith("toggle_chat_"):
            chat_id = int(data.split("_")[2])
            await self.toggle_chat(query, chat_id)
        elif data.startswith("delete_chat_"):
            chat_id = int(data.split("_")[2])
            await self.delete_chat(query, chat_id)
        elif data.startswith("set_keywords_"):
            chat_id = int(data.split("_")[2])
            self.user_sessions[user_id] = {'action': 'set_keywords', 'chat_id': chat_id}
            await query.edit_message_text(
                f"📝 Введите ключевые слова через запятую для чата (ID: {chat_id}):\n"
                f"Пример: срочно, важно, скидка"
            )
    
    async def show_stats(self, query):
        """Показать статистику"""
        stats = await self.db.get_stats()
        chats = await self.db.get_chats(enabled_only=False)
        
        active_chats = len([c for c in chats if c['enabled']])
        total_chats = len(chats)
        
        text = (
            "📊 **Статистика парсера**\n\n"
            f"📝 Всего сообщений: {stats['total_messages']}\n"
            f"📤 Переслано: {stats['forwarded']}\n"
            f"💬 Чатов всего: {total_chats}\n"
            f"🟢 Активных чатов: {active_chats}\n"
            f"⏱ Обновлено: {datetime.now().strftime('%H:%M:%S')}"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def list_chats(self, query):
        """Список чатов"""
        chats = await self.db.get_chats(enabled_only=False)
        
        if not chats:
            await query.edit_message_text(
                "📭 У вас пока нет добавленных чатов.\n"
                "Добавьте чат через кнопку 'Добавить чат'"
            )
            return
        
        text = "📋 **Ваши чаты для парсинга**\n\n"
        keyboard = []
        
        for chat in chats:
            status = "🟢" if chat['enabled'] else "🔴"
            keywords = ', '.join(chat['keywords']) if chat['keywords'] else 'нет'
            text += (
                f"{status} **{chat['name'] or chat['identifier']}**\n"
                f"  ID: {chat['id']}\n"
                f"  Ключевые слова: {keywords}\n"
                f"  Лимит: {chat['limit']}\n\n"
            )
            
            # Кнопки управления для каждого чата
            keyboard.append([
                InlineKeyboardButton(
                    f"{'⏸' if chat['enabled'] else '▶️'} {chat['name'] or chat['identifier']}",
                    callback_data=f"toggle_chat_{chat['id']}"
                ),
                InlineKeyboardButton(
                    "🗑 Удалить",
                    callback_data=f"delete_chat_{chat['id']}"
                ),
                InlineKeyboardButton(
                    "✏️ Ключевые слова",
                    callback_data=f"set_keywords_{chat['id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def add_chat_prompt(self, query):
        """Запрос данных для добавления чата"""
        user_id = query.from_user.id
        self.user_sessions[user_id] = {'action': 'add_chat'}
        
        await query.edit_message_text(
            "📝 **Добавление нового чата**\n\n"
            "Отправьте ссылку или username чата:\n"
            "• Ссылка: https://t.me/chat_name\n"
            "• Username: @chat_name\n"
            "• ID: -1001234567890\n\n"
            "Пример: @durov"
        )
    
    async def toggle_chat(self, query, chat_id: int):
        """Включить/выключить чат"""
        chats = await self.db.get_chats(enabled_only=False)
        chat = next((c for c in chats if c['id'] == chat_id), None)
        
        if chat:
            new_state = not chat['enabled']
            await self.db.toggle_chat(chat_id, new_state)
            status = "включен" if new_state else "отключен"
            await query.answer(f"Чат {status}")
            await self.list_chats(query)
    
    async def delete_chat(self, query, chat_id: int):
        """Удалить чат"""
        await self.db.delete_chat(chat_id)
        await query.answer("Чат удален")
        await self.list_chats(query)
    
    async def run_parser(self, query):
        """Запуск парсинга"""
        await query.edit_message_text("🔄 Запускаю парсинг... Подождите...")
        
        try:
            result = await self.parser.run_parser()
            
            if result['status'] == 'success' or result['status'] == 'empty':
                text = (
                    "✅ **Парсинг завершен!**\n\n"
                    f"🔍 Найдено новых сообщений: {result['total_found']}\n"
                    f"⏱ Время: {datetime.now().strftime('%H:%M:%S')}\n\n"
                    "Используйте кнопку 'Последние сообщения' для просмотра"
                )
                if result.get('errors'):
                    text += f"\n\n⚠️ Ошибок: {len(result['errors'])}"
            else:
                text = f"❌ Ошибка: {result.get('message', 'Неизвестная ошибка')}"
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Ошибка при запуске парсинга: {e}")
            await query.edit_message_text(f"❌ Ошибка: {str(e)}")
    
    async def show_last_messages(self, query):
        """Показать последние сообщения"""
        messages = await self.db.get_messages(limit=10)
        
        if not messages:
            await query.edit_message_text(
                "📭 Пока нет найденных сообщений.\n"
                "Запустите парсинг для поиска."
            )
            return
        
        text = "📥 **Последние найденные сообщения**\n\n"
        
        for i, msg in enumerate(messages[:5], 1):
            text += (
                f"{i}. **{msg['chat_name']}**\n"
                f"   👤 {msg['sender']}\n"
                f"   🔑 {', '.join(msg['keywords'])}\n"
                f"   📝 {msg['text'][:100]}...\n"
                f"   🔗 [Ссылка]({msg['url']})\n\n"
            )
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def show_settings(self, query):
        """Показать настройки"""
        settings = {
            'Лимит сообщений': self.config.DEFAULT_LIMIT,
            'Максимум пересылок': self.config.MAX_FORWARD_PER_RUN,
            'Период проверки (часов)': self.config.CHECK_INTERVAL_HOURS,
            'Минимальная длина текста': self.config.MIN_TEXT_LENGTH
        }
        
        text = "⚙️ **Текущие настройки**\n\n"
        for key, value in settings.items():
            text += f"• {key}: {value}\n"
        
        text += "\n✏️ Настройки можно изменить в файле .env"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        user_id = update.effective_user.id
        
        if user_id not in self.config.ALLOWED_USERS:
            await update.message.reply_text("⛔ Доступ запрещен")
            return
        
        text = update.message.text
        session = self.user_sessions.get(user_id)
        
        if not session:
            await update.message.reply_text(
                "Используйте кнопки для управления ботом"
            )
            return
        
        if session['action'] == 'add_chat':
            # Добавление чата
            try:
                # Проверяем чат через временный клиент
                parser = TelegramParser(self.config, self.db)
                
                # Берем первый активный аккаунт
                accounts = self.config.get_enabled_accounts()
                if not accounts:
                    await update.message.reply_text(
                        "❌ Нет активных аккаунтов для парсинга.\n"
                        "Проверьте настройки ACCOUNT_* в переменных окружения."
                    )
                    del self.user_sessions[user_id]
                    return
                
                # Инициализируем клиент
                client = await parser.init_client(accounts[0])
                if not client:
                    await update.message.reply_text(
                        "❌ Не удалось подключиться к Telegram API.\n"
                        "Проверьте API_ID, API_HASH и номер телефона."
                    )
                    del self.user_sessions[user_id]
                    return
                
                # Пробуем получить чат
                try:
                    entity = await client.get_entity(text)
                    chat_name = getattr(entity, 'title', text)
                    
                    # Сохраняем в базу
                    await self.db.add_chat(
                        identifier=text,
                        name=chat_name,
                        keywords=['срочно', 'важно'],  # По умолчанию
                        limit=50
                    )
                    
                    await update.message.reply_text(
                        f"✅ Чат '{chat_name}' успешно добавлен!\n"
                        f"📝 Ключевые слова по умолчанию: срочно, важно\n"
                        f"✏️ Используйте кнопку 'Мои чаты' для настройки\n"
                        f"▶️ Нажмите 'Запустить парсинг' для поиска сообщений"
                    )
                    
                except ValueError as e:
                    await update.message.reply_text(
                        f"❌ Чат не найден: {str(e)}\n"
                        "Проверьте правильность ссылки или username.\n"
                        "Примеры:\n"
                        "• @durov\n"
                        "• https://t.me/durov\n"
                        "• -1001234567890"
                    )
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ Ошибка: {str(e)}\n"
                        "Проверьте правильность ссылки или username."
                    )
                finally:
                    # Закрываем клиент
                    await client.disconnect()
                    
            except Exception as e:
                logger.error(f"Ошибка при добавлении чата: {e}")
                await update.message.reply_text(
                    f"❌ Критическая ошибка: {str(e)}\n"
                    "Пожалуйста, проверьте логи Railway."
                )
            
            # Удаляем сессию пользователя
            del self.user_sessions[user_id]
            
        elif session['action'] == 'set_keywords':
            # Установка ключевых слов
            chat_id = session['chat_id']
            keywords = [kw.strip() for kw in text.split(',') if kw.strip()]
            
            if not keywords:
                await update.message.reply_text("❌ Введите хотя бы одно ключевое слово")
                return
            
            # Обновляем чат
            chats = await self.db.get_chats(enabled_only=False)
            chat = next((c for c in chats if c['id'] == chat_id), None)
            
            if chat:
                await self.db.add_chat(
                    identifier=chat['identifier'],
                    name=chat['name'],
                    keywords=keywords,
                    limit=chat['limit']
                )
                
                await update.message.reply_text(
                    f"✅ Ключевые слова обновлены:\n"
                    f"📝 {', '.join(keywords)}\n\n"
                    f"▶️ Нажмите 'Запустить парсинг' для поиска новых сообщений"
                )
            else:
                await update.message.reply_text("❌ Чат не найден")
            
            del self.user_sessions[user_id]
    
    async def back_handler(self, query):
        """Кнопка 'Назад'"""
        # Создаем фейковый update для вызова start
        class FakeUpdate:
            def __init__(self, query):
                self.effective_user = query.from_user
                self.message = type('obj', (object,), {
                    'reply_text': query.edit_message_text
                })()
        
        fake_update = FakeUpdate(query)
        await self.start(fake_update, None)
    
    def run(self):
        """Запуск бота"""
        # Создаем приложение
        application = Application.builder().token(self.config.BOT_TOKEN).build()
        
        # Регистрируем обработчики
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CallbackQueryHandler(self.button_handler))
        application.add_handler(CallbackQueryHandler(self.back_handler, pattern="^back$"))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Запускаем бота
        logger.info("🚀 Бот запущен...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    bot = ParserBot()
    bot.run()
