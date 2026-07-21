import os
import sys

print("=" * 60)
print("🔍 ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ")
print("=" * 60)

# Проверяем все переменные, которые нужны для авторизации
env_vars = [
    'ACCOUNT_1_NAME',
    'ACCOUNT_1_API_ID', 
    'ACCOUNT_1_API_HASH',
    'ACCOUNT_1_PHONE',
    'BOT_TOKEN',
    'ALLOWED_USERS',
    'DATA_DIR'
]

for var in env_vars:
    value = os.getenv(var)
    if value:
        # Маскируем чувствительные данные
        if 'HASH' in var or 'TOKEN' in var:
            print(f"✅ {var} = {value[:10]}... (установлена)")
        else:
            print(f"✅ {var} = {value}")
    else:
        print(f"❌ {var} = НЕ УСТАНОВЛЕНА!")

print("=" * 60)

# Проверяем, какие переменные вообще есть
print("\n📋 ВСЕ ПЕРЕМЕННЫЕ (первые 10):")
for key, value in list(os.environ.items())[:10]:
    if 'HASH' in key or 'TOKEN' in key:
        print(f"  {key} = {value[:10]}...")
    else:
        print(f"  {key} = {value}")
