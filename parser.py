import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Set, Optional

from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError, 
    FloodWaitError,
    PhoneNumberInvalidError,
    ApiIdInvalidError,
    AccessTokenInvalidError
)
from telethon.tl.types import Message
from telethon.tl.functions.messages import GetMessagesRequest

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
            with open(self.config.PROCESSED_IDS_FILE, 'r', encoding='utf-8') as f:
                self.processed_ids = set(json.load(f))
            logger.info(f"Загружено {len(self.processed_ids)} обработанных ID")
        except FileNotFoundError:
            logger.info("Файл processed_ids.json не найден, создаем новый")
            self.processed_ids = set()
        except json.JSONDecodeError:
            logger.warning("Ошибка чтения processed_ids.json, создаем новый")
            self.processed_ids = set()
        except Exception as e:
            logger.error(f"Ошибка загрузки processed_ids: {e}")
            self.processed_ids = set()
    
    def save_processed_ids(self):
        """Сохранение обработанных ID"""
        try:
            with open(self.config.PROCESSED_IDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(list(self.processed_ids), f)
        except Exception as e:
            logger.error(f"Ошибка сохранения processed_ids: {e}")
    
    async def init_client(self, account: Dict) -> Optional[TelegramClient]:
        """Инициализация клиента с обработкой ошибок"""
        try:
            client = TelegramClient(
                f"sessions/{account['name']}",
                account['api_id'],
                account['api_hash']
            )
            
            await client.start(phone=account['phone'])
            logger.info(f"✅ Аккаунт '{account['name']}' авторизован")
            return client
            
        except SessionPasswordNeededError:
            logger.error(f"❌ Для аккаунта '{account['name']}' требуется 2FA пароль")
            return None
            
        except PhoneNumberInvalidError:
            logger.error(f"❌ Неверный номер телефона для аккаунта '{account['name']}'")
            return None
            
        except ApiIdInvalidError:
            logger.error(f"❌ Неверный API_ID или API_HASH для аккаунта '{account['name']}'")
            return None
            
        except AccessTokenInvalidError:
            logger.error(f"❌ Неверный токен доступа для аккаунта '{account['name']}'")
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка авторизации {account['name']}: {e}")
            return None
    
    async def get_entity_with_retry(self, client: TelegramClient, identifier: str, max_retries: int = 3):
        """Получение чата с повторными попытками"""
        for attempt in range(max_retries):
            try:
                return await client.get_entity(identifier)
            except FloodWaitError as e:
                wait_time = e.seconds + 5
                logger.warning(f"Flood wait {wait_time} секунд, попытка {attempt + 1}/{max_retries}")
                await asyncio.sleep(wait_time)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Ошибка получения чата {identifier}, попытка {attempt + 1}: {e}")
                await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
        return None
    
    async def process_message(self, client: TelegramClient, message: Message,
                             chat_config: Dict, chat_name: str, account_name: str):
        """Обработка сообщения"""
        try:
            # Проверяем, не обработано ли уже
            if message.id in self.processed_ids:
                return None
            
            # Проверяем наличие текста
            if not message.text:
                return None
                
            # Обрезаем слишком длинные сообщения для проверки
            text_for_check = message.text[:1000].lower()
            if len(message.text) < self.config.MIN_TEXT_LENGTH:
                return None
            
            # Проверяем ключевые слова
            matched_keywords = [
                kw for kw in chat_config.get('keywords', [])
                if kw.lower() in text_for_check
            ]
            
            if not matched_keywords:
                return None
            
            # Проверяем дату (используем время сообщения)
            if self.config.CHECK_INTERVAL_HOURS > 0:
                time_limit = datetime.now().astimezone() - timedelta(hours=self.config.CHECK_INTERVAL_HOURS)
                if message.date < time_limit:
                    return None
            
            # Получаем отправителя
            sender_name = 'Неизвестно'
            if message.sender:
                if hasattr(message.sender, 'first_name') and message.sender.first_name:
                    sender_name = message.sender.first_name
                    if hasattr(message.sender, 'last_name') and message.sender.last_name:
                        sender_name += f' {message.sender.last_name}'
                elif hasattr(message.sender, 'username') and message.sender.username:
                    sender_name = f'@{message.sender.username}'
                elif hasattr(message.sender, 'title'):
                    sender_name = message.sender.title
            
            # Генерируем URL
            try:
                entity = await client.get_entity(message.chat_id)
                if entity.username:
                    url = f"https://t.me/{entity.username}/{message.id}"
                else:
                    chat_id = str(message.chat_id)
                    if chat_id.startswith('-100'):
                        chat_id = chat_id[4:]
                    url = f"https://t.me/c/{chat_id}/{message.id}"
            except:
                url = "Недоступно"
            
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
            
            # Сохраняем каждые 10 сообщений
            if len(self.processed_ids) % 10 == 0:
                self.save_processed_ids()
            
            logger.info(f"✅ Найдено в {chat_name}: {message.text[:100].replace(chr(10), ' ')}...")
            
            return message_data
            
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения {message.id}: {e}")
            return None
    
    async def parse_chat(self, client: TelegramClient, account: Dict, chat_config: Dict):
        """Парсинг одного чата"""
        try:
            # Получаем чат с повторными попытками
            entity = await self.get_entity_with_retry(client, chat_config['identifier'])
            if not entity:
                logger.error(f"Не удалось получить чат {chat_config['identifier']}")
                return []
            
            chat_name = getattr(entity, 'title', chat_config['identifier'])
            logger.info(f"📥 Парсим {chat_name} (лимит: {chat_config.get('limit', 50)})")
            
            messages_found = []
            count = 0
            
            async for message in client.iter_messages(
                entity, 
                limit=chat_config.get('limit', 50),
                reverse=False  # Новые сообщения сначала
            ):
                count += 1
                if count % 20 == 0:
                    logger.info(f"   Обработано {count} сообщений в {chat_name}")
                
                result = await self.process_message(
                    client, message, chat_config, chat_name, account['name']
                )
                if result:
                    messages_found.append(result)
                    
                    # Если достигнут лимит, останавливаемся
                    if len(messages_found) >= self.config.MAX_FORWARD_PER_RUN:
                        logger.info(f"   Достигнут лимит ({self.config.MAX_FORWARD_PER_RUN})")
                        break
                
                # Небольшая пауза между сообщениями
                await asyncio.sleep(0.3)
            
            logger.info(f"📊 В {chat_name} найдено {len(messages_found)} сообщений")
            return messages_found
            
        except FloodWaitError as e:
            wait_time = e.seconds + 10
            logger.warning(f"⚠️ Flood wait {wait_time} секунд для {chat_config['identifier']}")
            await asyncio.sleep(wait_time)
            return []
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга {chat_config['identifier']}: {e}")
            return []
    
    async def run_parser(self, accounts: List[Dict] = None, chat_ids: List[int] = None):
        """Запуск парсера"""
        if not accounts:
            accounts = self.config.get_enabled_accounts()
        
        if not accounts:
            return {
                "status": "error", 
                "message": "Нет активных аккаунтов для парсинга"
            }
        
        # Получаем чаты из базы
        try:
            chats = await self.db.get_chats(enabled_only=True)
            if chat_ids:
                chats = [c for c in chats if c['id'] in chat_ids]
        except Exception as e:
            logger.error(f"Ошибка получения чатов из БД: {e}")
            return {
                "status": "error",
                "message": f"Ошибка базы данных: {e}"
            }
        
        if not chats:
            return {
                "status": "error", 
                "message": "Нет активных чатов для парсинга. Добавьте чаты через бота."
            }
        
        logger.info(f"🚀 Запуск парсинга: {len(accounts)} аккаунтов, {len(chats)} чатов")
        
        total_found = 0
        errors = []
        
        for account in accounts:
            if not account.get('enabled', True):
                continue
            
            logger.info(f"📱 Аккаунт: {account['name']}")
            client = await self.init_client(account)
            if not client:
                errors.append(f"Не удалось авторизовать {account['name']}")
                continue
            
            try:
                for chat in chats:
                    try:
                        found = await self.parse_chat(client, account, chat)
                        total_found += len(found)
                        
                        # Сохраняем ID после каждого чата
                        self.save_processed_ids()
                        
                    except Exception as e:
                        error_msg = f"Ошибка в чате {chat['identifier']}: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                
                await client.disconnect()
                
            except Exception as e:
                logger.error(f"Критическая ошибка для {account['name']}: {e}")
                errors.append(f"{account['name']}: {e}")
                try:
                    await client.disconnect()
                except:
                    pass
        
        # Финальное сохранение
        self.save_processed_ids()
        
        # Логируем результат
        logger.info(f"✅ Парсинг завершен. Найдено: {total_found}")
        if errors:
            logger.warning(f"⚠️ Ошибки: {len(errors)}")
        
        return {
            "status": "success" if total_found > 0 else "empty",
            "total_found": total_found,
            "errors": errors,
            "message": f"Найдено {total_found} новых сообщений" + 
                      (f" (ошибок: {len(errors)})" if errors else "")
        }
