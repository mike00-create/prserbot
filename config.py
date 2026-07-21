import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env только в локальной среде
if os.path.exists('.env'):
    load_dotenv()

class Config:
    # ============ Telegram Bot ============
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    if not BOT_TOKEN:
        raise ValueError("❌ BOT_TOKEN не найден в переменных окружения!")
    
    ALLOWED_USERS = [int(x.strip()) for x in os.getenv('ALLOWED_USERS', '').split(',') if x.strip()]
    if not ALLOWED_USERS:
        raise ValueError("❌ ALLOWED_USERS не найден в переменных окружения!")
    
    # ============ Аккаунты для парсинга ============
    ACCOUNTS = []
    
    # Загружаем аккаунты из переменных окружения
    i = 1
    while True:
        name = os.getenv(f'ACCOUNT_{i}_NAME')
        if not name:
            break
            
        # Проверяем наличие обязательных полей
        api_id = os.getenv(f'ACCOUNT_{i}_API_ID')
        api_hash = os.getenv(f'ACCOUNT_{i}_API_HASH')
        phone = os.getenv(f'ACCOUNT_{i}_PHONE')
        
        if not all([api_id, api_hash, phone]):
            print(f"⚠️ Аккаунт {i} пропущен: не хватает данных")
            i += 1
            continue
            
        ACCOUNTS.append({
            'name': name,
            'api_id': int(api_id),
            'api_hash': api_hash,
            'phone': phone,
            'enabled': os.getenv(f'ACCOUNT_{i}_ENABLED', 'true').lower() == 'true'
        })
        i += 1
    
    if not ACCOUNTS:
        raise ValueError("❌ Не загружено ни одного аккаунта для парсинга!")
    
    # ============ Настройки парсинга ============
    DEFAULT_LIMIT = int(os.getenv('DEFAULT_LIMIT', 50))
    MAX_FORWARD_PER_RUN = int(os.getenv('MAX_FORWARD_PER_RUN', 30))
    CHECK_INTERVAL_HOURS = int(os.getenv('CHECK_INTERVAL_HOURS', 24))
    MIN_TEXT_LENGTH = int(os.getenv('MIN_TEXT_LENGTH', 5))
    
    # ============ Пути к файлам (с поддержкой Railway Volumes) ============
    # Определяем базовую директорию для данных
    DATA_DIR = os.getenv('DATA_DIR', 'data')
    
    # ✅ СОЗДАЕМ ПАПКУ ГАРАНТИРОВАННО
    try:
        Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
        print(f"✅ Папка данных: {DATA_DIR}")
    except Exception as e:
        print(f"⚠️ Ошибка создания папки {DATA_DIR}: {e}")
        # Запасной вариант - используем текущую папку
        DATA_DIR = '.'
    
    # Пути к файлам в директории данных
    PROCESSED_IDS_FILE = os.path.join(DATA_DIR, os.getenv('PROCESSED_IDS_FILE', 'processed_ids.json'))
    CSV_FILE = os.path.join(DATA_DIR, os.getenv('CSV_FILE', 'parsed_messages.csv'))
    LOG_FILE = os.path.join(DATA_DIR, os.getenv('LOG_FILE', 'parser.log'))
    
    # ============ База данных ============
    DATABASE_FILE = os.path.join(DATA_DIR, os.getenv('DATABASE_FILE', 'parser_data.db'))
    
    # Если используется PostgreSQL (на Railway), берем DATABASE_URL
    DATABASE_URL = os.getenv('DATABASE_URL')
    USE_POSTGRES = bool(DATABASE_URL)
    
    if USE_POSTGRES:
        print(f"✅ Используется PostgreSQL: {DATABASE_URL[:30]}...")
    else:
        print(f"✅ Используется SQLite: {DATABASE_FILE}")
    
    # ============ Дополнительные настройки ============
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
    
    # Прокси (если нужно)
    PROXY = os.getenv('PROXY')
    if PROXY:
        PROXY = {
            'scheme': os.getenv('PROXY_SCHEME', 'socks5'),
            'hostname': PROXY,
            'port': int(os.getenv('PROXY_PORT', 1080))
        }
    
    # ============ Методы для удобства ============
    @classmethod
    def get_account(cls, name: str):
        """Получить аккаунт по имени"""
        for account in cls.ACCOUNTS:
            if account['name'] == name:
                return account
        return None
    
    @classmethod
    def get_enabled_accounts(cls):
        """Получить список включенных аккаунтов"""
        return [acc for acc in cls.ACCOUNTS if acc.get('enabled', True)]
    
    @classmethod
    def is_railway_env(cls) -> bool:
        """Проверить, запущено ли на Railway"""
        return bool(os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('RAILWAY_SERVICE_ID'))
    
    @classmethod
    def validate_accounts(cls):
        """Проверка корректности данных аккаунтов"""
        if not cls.ACCOUNTS:
            print("❌ Нет загруженных аккаунтов!")
            return False
        
        for i, acc in enumerate(cls.ACCOUNTS, 1):
            issues = []
            
            if not acc.get('name'):
                issues.append("отсутствует имя")
            if not acc.get('api_id'):
                issues.append("отсутствует API_ID")
            if not acc.get('api_hash'):
                issues.append("отсутствует API_HASH")
            if not acc.get('phone'):
                issues.append("отсутствует номер телефона")
                
            if issues:
                print(f"❌ Аккаунт {i} имеет проблемы: {', '.join(issues)}")
                return False
            else:
                print(f"✅ Аккаунт {i} ({acc['name']}): данные заполнены")
        
        return True

# ✅ При импорте выводим информацию
print("="*50)
print("🔧 КОНФИГУРАЦИЯ ПАРСЕРА")
print("="*50)
print(f"🤖 BOT_TOKEN: {'✅ Установлен' if Config.BOT_TOKEN else '❌ ОТСУТСТВУЕТ'}")
print(f"👤 ALLOWED_USERS: {Config.ALLOWED_USERS}")
print(f"📱 Аккаунтов: {len(Config.ACCOUNTS)}")
for acc in Config.ACCOUNTS:
    status = "🟢" if acc['enabled'] else "🔴"
    print(f"   {status} {acc['name']} ({acc['phone']})")
print(f"📂 DATA_DIR: {Config.DATA_DIR}")
print(f"📊 БД: {'PostgreSQL' if Config.USE_POSTGRES else 'SQLite'}")
print(f"📝 Лог: {Config.LOG_FILE}")
print(f"📁 Файл БД: {Config.DATABASE_FILE}")
print("="*50)
