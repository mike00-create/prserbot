import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Set

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.types import Message

from database import Database
from config import Config

logger = logging.getLogger(__name__)

class TelegramParser:
    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        self.processed_ids: Set[int] = set()
        self.load_processed_ids()
    
    def load_processed_ids(self):
        """Загрузка обработанных ID"""
        try:
            with open(self.config.PROCESSED_IDS_FILE, 'r') as f:
                self.processed_ids = set(json.load(f))
        except:
            self.processed_ids = set()
    
    def save_processed_ids(self):
        """Сохранение обработанных ID"""
        try:
            with open(self.config.PROCESSED_IDS_FILE, 'w') as f:
                json.dump(list(self.processed_ids), f)
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
    
    async def init_client(self, account: Dict) -> TelegramClient:
        """Инициализация клиента"""
        client = TelegramClient(
            f"sessions/{account['name']}",
            account['api_id'],
            account['api_hash']
        )
        
        try:
            await client.start(phone=account['phone'])
            return client
        except SessionPasswordNeededError:
            # Для бота нужно будет запросить пароль отдельно
            raise
        except Exception as e:
            logger.error(f"Ошибка авторизации {account['name']}: {e}")
            return None
    
    async def process_message(self, client: TelegramClient, message: Message,
                             chat_config: Dict, chat_name: str, account_name: str):
        """Обработка сообщения"""
        try:
            # Проверяем, не обработано ли уже
            if message.id in self.processed_ids:
                return
            
            if not message.text or len(message.text) < self.config.MIN_TEXT_LENGTH:
                return
            
            # Проверяем ключевые слова
            text_lower = message.text.lower()
            matched_keywords = [
                kw for kw in chat_config.get('keywords', [])
                if kw.lower() in text_lower
            ]
            
            if not matched_keywords:
                return
            
            # Проверяем дату
            if self.config.CHECK_INTERVAL_HOURS > 0:
                time_limit = datetime.now() - timedelta(hours=self.config.CHECK_INTERVAL_HOURS)
                if message.date.replace(tzinfo=None) < time_limit:
                    return
            
            # Получаем отправителя
            sender_name = 'Неизвестно'
            if message.sender:
                if hasattr(message.sender, 'first_name') and message.sender.first_name:
                    sender_name = message.sender.first_name
                    if hasattr(message.sender, 'last_name') and message.sender.last_name:
                        sender_name += f' {message.sender.last_name}'
                elif hasattr(message.sender, 'username') and message.sender.username:
                    sender_name = f'@{message.sender.username}'
            
            # Генерируем URL
            url = f"https://t.me/c/{str(message.chat_id)[4:]}/{message.id}" if str(message.chat_id).startswith('-100') else f"https://t.me/{chat_name}/{message.id}"
            
            # Сохраняем в базу
            message_data = {
                'message_id': message.id,
                'chat_id': str(message.chat_id),
                'chat_name': chat_name,
                'sender': sender_name,
                'text': message.text[:5000],
                'keywords': matched_keywords,
                'url': url,
                'account': account_name
            }
            
            await self.db.save_message(message_data)
            
            # Отмечаем как обработанное
            self.processed_ids.add(message.id)
            self.save_processed_ids()
            
            logger.info(f"✅ Найдено сообщение в {chat_name}: {message.text[:100]}...")
            
            return message_data
            
        except Exception as e:
            logger.error(f"Ошибка обработки: {e}")
            return None
    
    async def parse_chat(self, client: TelegramClient, account: Dict, chat_config: Dict):
        """Парсинг одного чата"""
        try:
            entity = await client.get_entity(chat_config['identifier'])
            chat_name = getattr(entity, 'title', chat_config['identifier'])
            
            logger.info(f"📥 Парсим {chat_name}")
            
            messages_found = []
            async for message in client.iter_messages(entity, limit=chat_config.get('limit', 50)):
                result = await self.process_message(
                    client, message, chat_config, chat_name, account['name']
                )
                if result:
                    messages_found.append(result)
                    
                    # Если достигнут лимит, останавливаемся
                    if len(messages_found) >= self.config.MAX_FORWARD_PER_RUN:
                        break
                
                await asyncio.sleep(0.5)
            
            return messages_found
            
        except FloodWaitError as e:
            logger.warning(f"Flood wait {e.seconds} секунд")
            await asyncio.sleep(e.seconds)
            return []
        except Exception as e:
            logger.error(f"Ошибка парсинга {chat_config['identifier']}: {e}")
            return []
    
    async def run_parser(self, accounts: List[Dict] = None, chat_ids: List[int] = None):
        """Запуск парсера"""
        if not accounts:
            accounts = self.config.ACCOUNTS
        
        # Получаем чаты из базы
        chats = await self.db.get_chats(enabled_only=True)
        if chat_ids:
            chats = [c for c in chats if c['id'] in chat_ids]
        
        if not chats:
            return {"status": "error", "message": "Нет активных чатов для парсинга"}
        
        total_found = 0
        for account in accounts:
            if not account.get('enabled', True):
                continue
            
            client = await self.init_client(account)
            if not client:
                continue
            
            for chat in chats:
                try:
                    found = await self.parse_chat(client, account, chat)
                    total_found += len(found)
                except Exception as e:
                    logger.error(f"Ошибка: {e}")
            
            await client.disconnect()
        
        return {
            "status": "success",
            "total_found": total_found,
            "message": f"Найдено {total_found} новых сообщений"
        }