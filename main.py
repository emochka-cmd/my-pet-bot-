import telebot
import os
from email_validator import validate_email, EmailNotValidError
""" Мои библеотеки: """
from database import DataBase
from hashing import Hashing

class TelegramBot:
    def __init__(self, token):
        self.bot = telebot.TeleBot(token)
        self._start()
        self.user_states = {} # Состояние пользователя
        self.user_temp_data = {} # Временное хранение данных пользователя

        #Теперь подключение к базе данных:
        self.db = DataBase(
            host=os.getenv('DATA_BASE_HOST'),
            user=os.getenv('DATA_BASE_LOGIN'),
            password=os.getenv('DATA_BASE_KEY'),
            database=os.getenv('DATA_BASE_NAME'),
        )

        # Обработка паролей:
        self.pas = Hashing()


    def _start(self):
        @self.bot.message_handler(commands=['start'])
        def welcome(message):
            chat_id = message.chat.id
            if self.db.is_user_registered(chat_id):
                self.user_states[chat_id] = 'login'
            else:
                self.user_states[chat_id] = None
                self.send_welcome(message)
                self.welcome_menu(message)


        @self.bot.callback_query_handler(func=lambda call: call.data == 'reg') # Регистрация
        def registration(call):
            self.start_registration(call.message)


        @self.bot.callback_query_handler(func=lambda call: call.data == 'log') # Вход
        def login(call):
            self.start_login(call.message)


        @self.bot.callback_query_handler(func=lambda call: call.data == 'status') # Оттображение статуса пользователя
        def get_status(call):
            self.status(call.message)


        @self.bot.callback_query_handler(func=lambda call: call.data == 'add_money') 
        def money(call):
            self.add_money(call.message)


        @self.bot.callback_query_handler(func=lambda call: call.data == 'shop_list') 
        def shop_list_handler(call):
            self.shoping(call.message)


        # Тут кнопки
        @self.bot.message_handler(func=lambda message: 'Мой статус' in message.text)
        def state(message):
            self.status(message)


        @self.bot.message_handler(func=lambda message: 'Пополнить баланс' in message.text)
        def balance(message):
            self.add_money(message)


        # Продолжить регистрацию
        @self.bot.message_handler(func=lambda message: message.text == '✏️ Продолжить регистрацию2')
        def continue_reg(message):
            chat_id = message.chat.id
            if chat_id in self.user_temp_data and chat_id in self.user_states:
                current_state = self.user_states[chat_id]
                steps = {
                    'awaiting_email': "Введите ваш email для продолжения регистрации:",
                    'awaiting_name': "Введите ваше имя для продолжения регистрации:",
                    'awaiting_surname': "Введите вашу фамилию для продолжения регистрации:",
                    'awaiting_password': "Введите пароль для продолжения регистрации:",
                    'awaiting_password_again': "Повторите пароль для продолжения регистрации:"
                }
                if current_state in steps:
                    self.bot.send_sticker(chat_id, 'CAACAgIAAxkBAAERWnZom0iUr_djTHyXQfLvNNftoCY-1QACDAEAAladvQqqb_XSQNziPTYE')
                    self.bot.send_message(chat_id, steps[current_state])
                else:
                    self.bot.send_message(chat_id, "Не удалось определить шаг регистрации. Начнем заново.")
                    self._reset_user_state(chat_id)
                    self.user_states[chat_id] = 'awaiting_email'
                    self.bot.send_message(chat_id, "Введите ваш email:")
            else:
                self.bot.send_message(chat_id, "Данные для продолжения регистрации не найдены. Начнем заново.")
                self._reset_user_state(chat_id)
                self.user_states[chat_id] = 'awaiting_email'
                self.bot.send_message(chat_id, "Введите ваш email:")


        @self.bot.message_handler(func=lambda message: message.text == '❌ Отменить')
        def cancel(message):
            chat_id = message.chat.id
    
            # Очищаем состояние и временные данные пользователя
            self._reset_user_state(chat_id)
                
            # Отправляем сообщение пользователю, что регистрация отменена
            self.bot.send_message(chat_id, "❌ Регистрация отменена. Если хотите начать заново, нажмите /start.")
                
            # Показываем главное меню (для незарегистрированных)
            self.welcome_menu(message)


        @self.bot.message_handler(func=lambda message: message.text == 'Выйти из аккаунта(')
        def out_login(message):
            chat_id = message.chat.id
            self._reset_user_state(chat_id)
            self.bot.send_message(chat_id, "🚪 Вы вышли из аккаунта. Чтобы войти снова — напишите /start.")


        @self.bot.message_handler(func=lambda message: True)# Ели пользователь присылает сообщение
        def handle_text(message):
            chat_id = message.chat.id

            # Проверяем регистрацию в базе
            if chat_id not in self.user_states:
                if self.db.is_user_registered(chat_id):
                    self.user_states[chat_id] = 'login'
                else:
                    self.user_states[chat_id] = None


            current_state = self.user_states.get(chat_id)
            match current_state:
                case 'awaiting_email':
                    self.input_email(message)
                case 'awaiting_name':
                    self.input_name(message)
                case 'awaiting_surname':
                    self.input_surname(message)
                case 'awaiting_password':
                    self.input_password(message)
                case 'awaiting_password_again':
                    self.input_password_again(message)
                case 'send_in_database_new_user':
                    self.send_in_database_new_user(message)
                case 'awaiting_reg_email':
                    self.login_email(message)
                case 'awaiting_log_password':
                    self.reg_password(message)
                case 'login':
                    self._unknown_message(message)
                case _:
                    if not self.db.is_user_registered(chat_id):
                        self.send_welcome(message)
                        self.welcome_menu(message)
                    else:
                        self._unknown_message(message)

                

    """ Тут начинается блок связаный с регистрацией """

    def start_registration(self, message):
        """telegram_id, email, name, surname, password_hash, salt - порядок сбора данных в бд"""
        chat_id = message.chat.id

        self.user_states[chat_id] = 'awaiting_email'
        self.user_temp_data[chat_id] = {}

        self.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message.message_id,
            text='✅ Положено начало регистрации! Введите ваш email:',
            reply_markup=None
        )


    def correct_email(self, message, email):
        """ Проверка email """
        try:
            validate_email(email)

        except EmailNotValidError as e:
            self.bot.reply_to(message, f'❌ Ваш email не корректен. Введите ваш email еще раз')
            return False
        
        """ Проерка на уникальность в базе данных: """
        chat_id = message.chat.id
        if not self.db.check_unique(email, chat_id):
            self.bot.reply_to(message, '❌ Ваш email или telegram уже зарегистрирован')
            return False
        return True


    def input_email(self, message):
        chat_id = message.chat.id
        email = message.text.strip() 
        if not self.correct_email(message, email):
            return

        self.user_temp_data[chat_id]['email'] = email
        self.user_states[chat_id] = 'awaiting_name'

        self._ask_for_input(chat_id, 'Ваше имя')

    
    def input_name(self, message):
        chat_id = message.chat.id
        self.user_temp_data[chat_id]['name'] = message.text.strip()
        self.user_states[chat_id] = 'awaiting_surname'
        self._ask_for_input(chat_id, 'Вашу фамилию')


    def input_surname(self, message):
        chat_id = message.chat.id
        self.user_temp_data[chat_id]['surname'] = message.text.strip()
        self.user_states[chat_id] = 'awaiting_password'
        self._ask_for_input(chat_id, 'пароль:')


    def input_password(self, message):
        chat_id = message.chat.id
        password = message.text.strip()
        self.user_temp_data[chat_id]['password'] = password

        # Проверка минимальной длины пароля
        if len(password) < 6:
            self.bot.reply_to(
                message, 
                "❌ Пароль должен содержать минимум 6 символов")
            return

        # Еще раз:
        self.user_states[chat_id] = 'awaiting_password_again'
        self.bot.send_message(chat_id, '✅ Отлично! Еще раз введите пароль: ')

    
    def input_password_again(self, message):
        chat_id = message.chat.id
        password = message.text.strip()
        
        if not self.user_temp_data[chat_id]['password'] == password:
            self.bot.reply_to(
            message, 
            '❌ Пароли  не совпадают')
            return

        # Хешируем:
        hashing = self.pas(password)
        password_hash = hashing.hash()
        salt = hashing.get_salt()

        # Сохранем:
        self.user_temp_data[chat_id]['password_hash'] = password_hash
        self.user_temp_data[chat_id]['salt'] = salt 
        
        # Изменяем состояние:
        self.send_in_database_new_user(message)


    def send_in_database_new_user(self, message):
        chat_id = message.chat.id

        required_fields = ['email', 'name', 'surname', 'password_hash', 'salt']
        if not all(field in self.user_temp_data.get(chat_id, {}) for field in required_fields):
            self.bot.send_message(
                chat_id, 
                "❌ Ошибка: не все данные собраны. Начните регистрацию заново.")
            self._reset_user_state(chat_id)
            return

        try:
            success = self.db.save_user(
                telegram_id=chat_id,
                email=self.user_temp_data[chat_id]['email'],
                name=self.user_temp_data[chat_id]['name'],
                surname=self.user_temp_data[chat_id]['surname'],
                password_hash=self.user_temp_data[chat_id]['password_hash'],
                salt=self.user_temp_data[chat_id]['salt']
            )

            if success:
                self.bot.send_message( 
                    chat_id=chat_id,
                    text='✅ Регистрация прошла успешно!'
                )
            else:
                self.bot.send_message(
                    chat_id=chat_id,
                    text='❌ Ошибка. Повторите регистрацию'
                )


        except Exception as e:
            self.bot.send_message(chat_id, f"❌ Произошла ошибка: {str(e)}")

        finally:
            #  Очищаем временные данные
            self._reset_user_state(chat_id)
            # Вызываем менюшку
            self.user_states[chat_id] = 'login'
            self.for_login_user(message)


    """ Тут заканчивается. Напишем логику для входа:"""
    def start_login(self, message):
        chat_id = message.chat.id
        self.user_states[chat_id] = 'awaiting_reg_email'
        
         # Инициализация, если еще не существует
        if chat_id not in self.user_temp_data:
            self.user_temp_data[chat_id] = {}

        self.bot.edit_message_text(chat_id=chat_id,
            message_id=message.message_id,
            text='🧐 Добро пожаловать! Введите адрес электронной почты: ',
            reply_markup=None)


    def login_email(self, message):
        chat_id = message.chat.id
        email = message.text.strip()

        """ Проверка email: """
        try:
            validate_email(email)
            if self.db.check_email_in_database(email) != None:
                self.user_states[chat_id] = 'awaiting_log_password'
                self.user_temp_data[chat_id]['log_email'] = email

                self.bot.send_message(
                    chat_id, 
                    '✅ Email подтвержден. Теперь введите ваш пароль:')
            else:
                self.bot.reply_to(message, '❌ Ваш email не зарегистрирован.')

        except EmailNotValidError as e:
            self.bot.reply_to(
                message, 
                f'❌ Ваш email не корректен: {str(e)}\nВведите ваш email еще раз')
            
    
    def reg_password(self, message):
        chat_id = message.chat.id
        try:
            password = message.text.strip()
            email = self.user_temp_data[chat_id].get('log_email')

            if not email:
                self.bot.send_message(chat_id, "❌ Ошибка: email не найден в сессии")
                return

            # Получаем соль (всегда строка)
            salt = self.db.get_login_salt(email)
            if not salt:
                self.bot.send_message(chat_id, "❌ Ошибка: пользователь не найден или нет соли")
                return

            # Хешируем введённый пароль
            password_hash = Hashing.hash_password(password, salt)

            # Проверяем пользователя
            if self.db.login_user(email, password_hash):
                self._reset_user_state(chat_id)
                self.user_states[chat_id] = 'login'
                self.bot.send_message(chat_id, '✅ Вы вошли в свой аккаунт!')
                self.for_login_user(message)
            else:
                self.bot.send_message(chat_id, "❌ Неверный пароль")
        except Exception as e:
            print(f"Error in reg_password: {e}")
            self.bot.send_message(chat_id, "❌ Произошла ошибка при обработке запроса")

        
    """ Конец логики для входа. Начало логики взаимодействия пользователя с ботом """
    def _unknown_message(self, message):
        """ Логика для неизвестных комманд """
        chat_id = message.chat.id

        if chat_id in self.user_states and self.user_states[chat_id] == 'login':
                user_state = 'login'
        else:
            user_state = 'registration'

        self.bot.send_sticker(chat_id, 'CAACAgIAAxkBAAERWONomykO0oVwY4pZeeqKF3yC5JvZawACAgEAAladvQpO4myBy0Dk_zYE')
        self.bot.send_message(message.chat.id, 'Я не понимаю ваше сообщение. Используйте команды', reply_markup=self._get_keyboard(state=user_state))


    def for_login_user(self, message):
        """ Тут я реализую меню для авторизираваного пользователя """
        chat_id = message.chat.id

        if self.user_states[chat_id] == 'login':
            # Создаем inline - клавитуру:
            key_menu = telebot.types.InlineKeyboardMarkup()

            first_level_first= telebot.types.InlineKeyboardButton('💲 Мой статус', callback_data='status')
            first_level_second = telebot.types.InlineKeyboardButton('✡️ Пополнить кошелек', callback_data='add_money')

            second_level_first = telebot.types.InlineKeyboardButton('🏪 Список доступных покупок', callback_data='shop_list')

            key_menu.add(first_level_first, first_level_second)
            key_menu.add(second_level_first)

            self.bot.send_message(
                chat_id,
                '🫂 Рады вас видеть!',
                reply_markup=key_menu)
        else:
            self.bot.send_message(chat_id, 'Вы не зарегистрировараны! Используйте /start', reply_markup=self._get_keyboard())

    
    def status(self, message):
        chat_id = message.chat.id

        if chat_id in self.user_states and self.user_states[chat_id] == 'login':
            status = self.db.get_status(chat_id=chat_id)
            if status:
                self.bot.send_message(chat_id,
                f"🔍 Имя: {status['name']}.🫡 Фамилия: {status['surname']}\n💰 Ваши сбережения: {status['user_money']}💲."
                )
        else:
            self.bot.send_message(chat_id, 'Сначала зарегистрируйтесь.', reply_markup=self._get_keyboard())


    def add_money(self, message):
        chat_id = message.chat.id
        self.bot.send_message(chat_id,
        f"К сожалению, у меня нет API для работы с вашими финансами🥹.\nПо этому за красивые глазки держите +100💲")
        self.db.money_operation(chat_id=chat_id, money=100)
        self.bot.send_sticker(chat_id, "CAACAgIAAxkBAAERTp9ombc13oFIa0FD__QQiewhzDYHgAACAwEAAladvQoC5dF4h-X6TzYE")


    def shoping(self, message):
        chat_id = message.chat.id


    """ Конец  действий с ботом. Дальше прописана логика replay клавиатуры """
    def _get_keyboard(self, state='registration'):
        """ Принимает состояние """
        keyboard = telebot.types.ReplyKeyboardMarkup(
            resize_keyboard=True,
            one_time_keyboard=False,
            selective=True
        )

        if state == 'login':
            keyboard.row('💲 Мой статус', '✡️ Пополнить баланс')
            keyboard.row('🏪 Магазин', '⚙️ Настройки')
            keyboard.row('🚪 Скрыть меню')
            keyboard.row('Выйти из аккаунта(')

        elif state == 'registration':
            keyboard.row('✏️ Продолжить регистрацию')
            keyboard.row('❌ Отменить')
            
        return keyboard


    
    """ Конец логики клавиатуры. Начало всего остального. """
    def _unknown_users(self, message):
        pass
    def _reset_user_state(self, chat_id):
        """ Функция для очистки информации о пользователе"""
        self.user_states.pop(chat_id, None)
        self.user_temp_data.pop(chat_id, None)


    def send_welcome(self, message):
        self.bot.send_sticker(
            message.chat.id, 
            'CAACAgIAAxkBAAERTqxombj0GO3zAAFj_8AHu7XfjbmkoeEAAgEBAAJWnb0KIr6fDrjC5jQ2BA')
        self.bot.send_message(
            message.chat.id, 
            'Я - Бот для отображения твоих ресурсов и регистрации :)')
    

    def welcome_menu(self, message):
        keyboard = telebot.types.InlineKeyboardMarkup() #фиксируем клавиатуру
        keyboard.add(
            telebot.types.InlineKeyboardButton(
            text="✍️Регистрация",
            callback_data='reg'
        ), 
        telebot.types.InlineKeyboardButton(
            text="👐Вход",
            callback_data='log'
        ))
        self.bot.send_message(
            message.chat.id, 
            'Список доступных сейчас действий:',
            reply_markup=keyboard
        )
    

    def _ask_for_input(self, chat_id, field_name):
        """ Фунция помощник для регистрации """
        self.bot.send_message(chat_id, f'✅ Отлично! Теперь введите {field_name}:')
    

    def run(self):
        """ Запуск Бота """
        print('Бот запущен!')
        try:
            self.bot.infinity_polling()  # Бесконечно берет инфу из телеги
        finally:
            self.db.close()


if __name__ == '__main__':
    TOKEN = os.getenv('API_KEY')  # Берем токен
    if not TOKEN:
        raise Exception("No token provided")

    bot = TelegramBot(TOKEN)
    bot.run()