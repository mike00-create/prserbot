import asyncio
import os
from telethon import TelegramClient
from config import Config

async def test_auth():
    """Тест авторизации для всех аккаунтов"""
    config = Config()
    
    print("="*50)
    print("🔍 ТЕСТ АВТОРИЗАЦИИ")
    print("="*50)
    
    for i, account in enumerate(config.ACCOUNTS, 1):
        print(f"\n📱 Тестируем аккаунт {i}: {account['name']}")
        print(f"   Телефон: {account['phone']}")
        print(f"   API_ID: {account['api_id']}")
        
        # Создаем папку для сессий
        os.makedirs("sessions", exist_ok=True)
        
        client = TelegramClient(
            f"sessions/test_{account['name']}",
            account['api_id'],
            account['api_hash']
        )
        
        try:
            await client.start(phone=account['phone'])
            me = await client.get_me()
            print(f"   ✅ УСПЕШНО! Аккаунт: {me.first_name} (@{me.username})")
            await client.disconnect()
        except Exception as e:
            print(f"   ❌ ОШИБКА: {type(e).__name__}: {e}")
            
            # Детали ошибки
            if "PhoneNumberInvalidError" in str(e):
                print(f"      📱 Неверный номер. Проверьте формат: +79123456789")
            elif "ApiIdInvalidError" in str(e):
                print(f"      🔑 Неверный API_ID или API_HASH. Проверьте my.telegram.org")
            elif "SessionPasswordNeededError" in str(e):
                print(f"      🔐 Включена 2FA. Используйте аккаунт без 2FA или добавьте поддержку")
            elif "FloodWaitError" in str(e):
                print(f"      ⏳ Слишком много попыток. Подождите 5-10 минут")
            else:
                print(f"      💡 Проверьте: интернет, правильность данных, нет ли блокировки")

if __name__ == "__main__":
    asyncio.run(test_auth())
