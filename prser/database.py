import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import aiosqlite

class Database:
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных"""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            
            # Таблица чатов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    identifier TEXT UNIQUE NOT NULL,
                    name TEXT,
                    keywords TEXT,
                    limit_messages INTEGER DEFAULT 50,
                    enabled INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица найденных сообщений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER,
                    chat_id TEXT,
                    chat_name TEXT,
                    sender TEXT,
                    text TEXT,
                    keywords TEXT,
                    url TEXT,
                    account TEXT,
                    found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    forwarded INTEGER DEFAULT 0
                )
            ''')
            
            # Таблица настроек
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    async def add_chat(self, identifier: str, name: str = None, 
                       keywords: List[str] = None, limit: int = 50):
        """Добавление чата для парсинга"""
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute('''
                INSERT OR REPLACE INTO chats 
                (identifier, name, keywords, limit_messages)
                VALUES (?, ?, ?, ?)
            ''', (identifier, name, json.dumps(keywords or []), limit))
            await db.commit()
    
    async def get_chats(self, enabled_only: bool = True) -> List[Dict]:
        """Получение списка чатов"""
        async with aiosqlite.connect(self.db_file) as db:
            query = "SELECT * FROM chats"
            if enabled_only:
                query += " WHERE enabled = 1"
            
            cursor = await db.execute(query)
            rows = await cursor.fetchall()
            
            chats = []
            for row in rows:
                chats.append({
                    'id': row[0],
                    'identifier': row[1],
                    'name': row[2],
                    'keywords': json.loads(row[3]) if row[3] else [],
                    'limit': row[4],
                    'enabled': bool(row[5]),
                    'created_at': row[6]
                })
            return chats
    
    async def toggle_chat(self, chat_id: int, enabled: bool):
        """Включить/выключить чат"""
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute(
                "UPDATE chats SET enabled = ? WHERE id = ?",
                (1 if enabled else 0, chat_id)
            )
            await db.commit()
    
    async def delete_chat(self, chat_id: int):
        """Удалить чат"""
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
            await db.commit()
    
    async def save_message(self, message_data: Dict):
        """Сохранение найденного сообщения"""
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute('''
                INSERT INTO messages 
                (message_id, chat_id, chat_name, sender, text, keywords, url, account)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                message_data.get('message_id'),
                message_data.get('chat_id'),
                message_data.get('chat_name'),
                message_data.get('sender'),
                message_data.get('text'),
                json.dumps(message_data.get('keywords', [])),
                message_data.get('url'),
                message_data.get('account')
            ))
            await db.commit()
    
    async def get_messages(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Получение последних сообщений"""
        async with aiosqlite.connect(self.db_file) as db:
            cursor = await db.execute('''
                SELECT * FROM messages 
                ORDER BY found_at DESC 
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            rows = await cursor.fetchall()
            
            messages = []
            for row in rows:
                messages.append({
                    'id': row[0],
                    'message_id': row[1],
                    'chat_id': row[2],
                    'chat_name': row[3],
                    'sender': row[4],
                    'text': row[5],
                    'keywords': json.loads(row[6]) if row[6] else [],
                    'url': row[7],
                    'account': row[8],
                    'found_at': row[9],
                    'forwarded': bool(row[10])
                })
            return messages
    
    async def get_stats(self) -> Dict:
        """Получение статистики"""
        async with aiosqlite.connect(self.db_file) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM messages")
            total_messages = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(DISTINCT chat_id) FROM messages")
            total_chats = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM messages WHERE forwarded = 1")
            forwarded = (await cursor.fetchone())[0]
            
            return {
                'total_messages': total_messages,
                'total_chats': total_chats,
                'forwarded': forwarded
            }
    
    async def update_setting(self, key: str, value: str):
        """Обновление настройки"""
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute('''
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, value))
            await db.commit()
    
    async def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """Получение настройки"""
        async with aiosqlite.connect(self.db_file) as db:
            cursor = await db.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,)
            )
            row = await cursor.fetchone()
            return row[0] if row else default