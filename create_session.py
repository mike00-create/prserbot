import asyncio
import os
from telethon import TelegramClient
from config import Config

async def create_session():
    """Создание сессии для авторизации"""
    print("="*50)
    print("🔐 СОЗДАНИЕ СЕССИИ TELEGRAM")
    print("="*50)
    
    # Берем первый аккаунт
    config = Config()
    account = config.ACCOUNTS[0]
    
    print(f"📱 Аккаунт: {account['name']}")
    print(f"📞 Телефон: {account['phone']}")
    print(f"🔑 API_ID: {account['api_id']}")
    print("="*50)
    
    # Создаем папку для сессий
    os.makedirs("sessions", exist_ok=True)
    
    # Создаем клиент
    client = TelegramClient(
        f"sessions/{account['name']}",
        account['api_id'],
        account['api_hash']
    )
    
    try:
        # Запускаем авторизацию
        await client.start(phone=account['phone'])
        
        # Проверяем, что авторизация прошла
        me = await client.get_me()
        print(f"\n✅ УСПЕШНО! Аккаунт: {me.first_name} (@{me.username})")
        print(f"📁 Сессия сохранена в: sessions/{account['name']}.session")
        print("\n💡 Теперь загрузите папку sessions/ на Railway через Volume")
        
        await client.disconnect()
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        print("Пожалуйста, проверьте данные аккаунта")

if __name__ == "__main__":
    asyncio.run(create_session())
