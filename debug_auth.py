import asyncio
import os
import sys
from telethon import TelegramClient
from telethon.errors import (
    PhoneNumberInvalidError,
    ApiIdInvalidError,
    SessionPasswordNeededError,
    FloodWaitError
)

async def debug_auth():
    """Диагностика авторизации с подробным выводом"""
    
    print("=" * 60)
    print("🔍 ДИАГНОСТИКА АВТОРИЗАЦИИ TELEGRAM")
    print("=" * 60)
    
    # Проверяем переменные окружения
    print("\n📋 ПРОВЕРКА ПЕРЕМЕННЫХ:")
    
    # Проверяем BOT_TOKEN
    bot_token = os.getenv('BOT_TOKEN')
    print(f"  BOT_TOKEN: {'✅ Установлен' if bot_token else '❌ ОТСУТСТВУЕТ'}")
    
    # Проверяем аккаунты
    i = 1
    accounts = []
    while True:
        name = os.getenv(f'ACCOUNT_{i}_NAME')
        if not name:
            break
        
        api_id = os.getenv(f'ACCOUNT_{i}_API_ID')
        api_hash = os.getenv(f'ACCOUNT_{i}_API_HASH')
        phone = os.getenv(f'ACCOUNT_{i}_PHONE')
        
        accounts.append({
            'name': name,
            'api_id': api_id,
            'api_hash': api_hash,
            'phone': phone
        })
        i += 1
    
    if not accounts:
        print("  ❌ Нет аккаунтов!")
        return
    
    print(f"  Найдено аккаунтов: {len(accounts)}")
    
    for idx, acc in enumerate(accounts, 1):
        print(f"\n📱 АККАУНТ {idx}: {acc['name']}")
        print(f"  API_ID: {acc['api_id']}")
        print(f"  API_HASH: {acc['api_hash'][:10]}... (обрезано)")
        print(f"  PHONE: {acc['phone']}")
        
        # Проверяем корректность данных
        issues = []
        if not acc['api_id'] or acc['api_id'] == 'None':
            issues.append("API_ID не установлен")
        if not acc['api_hash'] or acc['api_hash'] == 'None':
            issues.append("API_HASH не установлен")
        if not acc['phone'] or acc['phone'] == 'None':
            issues.append("PHONE не установлен")
        
        if issues:
            print(f"  ❌ ПРОБЛЕМЫ: {', '.join(issues)}")
            continue
        
        # Пробуем авторизоваться
        print(f"\n  🔄 Пытаюсь авторизоваться...")
        
        try:
            # Создаем папку для сессий
            os.makedirs("sessions", exist_ok=True)
            
            # Пробуем разные варианты номера
            phones_to_try = [acc['phone']]
            
            # Если номер начинается с +, пробуем без +
            if acc['phone'].startswith('+'):
                phones_to_try.append(acc['phone'][1:])
            else:
                phones_to_try.append(f'+{acc['phone']}')
            
            for phone in phones_to_try:
                try:
                    print(f"    📞 Пробую номер: {phone}")
                    
                    client = TelegramClient(
                        f"sessions/debug_{acc['name']}",
                        int(acc['api_id']),
                        acc['api_hash']
                    )
                    
                    try:
                        await client.start(phone=phone)
                        me = await client.get_me()
                        print(f"  ✅ УСПЕШНО! Аккаунт: {me.first_name} (@{me.username})")
                        await client.disconnect()
                        break
                    except PhoneNumberInvalidError:
                        print(f"    ❌ Неверный номер: {phone}")
                        continue
                    except ApiIdInvalidError:
                        print(f"    ❌ Неверный API_ID или API_HASH")
                        break
                    except SessionPasswordNeededError:
                        print(f"    ❌ Требуется 2FA пароль")
                        print(f"    💡 Добавьте переменную ACCOUNT_PASSWORD в Railway")
                        break
                    except FloodWaitError as e:
                        print(f"    ❌ Слишком много попыток! Подождите {e.seconds} секунд")
                        break
                    except Exception as e:
                        print(f"    ❌ Ошибка: {type(e).__name__}: {str(e)[:100]}")
                        continue
                    finally:
                        try:
                            await client.disconnect()
                        except:
                            pass
                except Exception as e:
                    print(f"    ❌ Ошибка при создании клиента: {e}")
                    continue
                    
        except Exception as e:
            print(f"  ❌ Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_auth())
