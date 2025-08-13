import pymysql
from pymysql.cursors import DictCursor # Будет возвращать словари

class DataBase:
    def __init__(self, host, user, password, database):
        self.connection = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            cursorclass=DictCursor
        )
    

    def check_unique(self, email, telegram_id):
        try:
            with self.connection.cursor() as cursor:
                check_email = "SELECT COUNT(*) AS count FROM users WHERE email = %s;"
                check_telegram_id = "SELECT COUNT(*) AS count FROM users WHERE id_telegram = %s;"

                cursor.execute(check_email, (email,))
                res_email = cursor.fetchone()

                cursor.execute(check_telegram_id, (telegram_id, ))
                res_telegram_id = cursor.fetchone()

                if res_email['count'] > 0 or res_telegram_id['count'] > 0: # Проверка на уникальность
                    return False
                return True
        
        except Exception as e:
            return False


    def save_user(self, telegram_id, email, name, surname, password_hash, salt):
        try:
            with self.connection.cursor() as cursor: # У нас используеться обьект. Cursor позволяет обращаться к бд
                # Храниться в varchar:
                telegram_id_str = str(telegram_id)
                
               # Если по ошибке передали bytes — декодируем
                if salt and isinstance(salt, bytes):
                    salt = salt.decode('utf-8')
                

                # Запрос на добавление данных при регистрации
                new_user_sql = """
                INSERT INTO users (id_telegram, email, password_hash, salt, name, surname)
                VALUES (%s, %s, %s, %s, %s, %s)
                """

                # Добавление новых данных, но еще не записываем
                cursor.execute(new_user_sql, 
                    (telegram_id_str, 
                    email, 
                    password_hash, 
                    salt, 
                    name, 
                    surname))

            # Записываем изменения в БД
            self.connection.commit()
            # Добавим потом сообщение польщователю что все хорошо
            return True

        except pymysql.err.IntegrityError as e:
            return False            

        except Exception:
            self.connection.rollback() # Откат изменений в случае ошибок
            return False


    def is_user_registered(self, telegram_id):
        """ Проверка, зарегистрирован ли пользователь """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM users WHERE id_telegram = %s LIMIT 1", (telegram_id,))
                return cursor.fetchone() is not None

        except Exception as e:
            print(f"Ошибка в is_user_registered: {e}")
            return False    

    def check_email_in_database(self, email):
        """ Проверяет есть ли email в базе данных """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM users WHERE email = %s LIMIT 1", (email,))
                return cursor.fetchone() is not None

        except Exception as e:
            print(f"Ошибка: {str(e)}")
            return False


    def get_login_salt(self, email):
        """ Возвращаем соль """
        try:
            with self.connection.cursor() as cursor:
                query = "SELECT salt FROM users WHERE email=%s"
                cursor.execute(query, (email,))
                row = cursor.fetchone()
                if row:
                    return row['salt']  # возвращаем просто строку соли
                return None

        except Exception as e:
            print(f"Ошибка в get_login_salt: {e}")
            return None


    def login_user(self, email, hash_password):
        """ Метод для входа в систему. Подразумевается, что пароль уже захеширован"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM users WHERE email = %s AND password_hash = %s ",
                    (email, hash_password, )
                )
                res = cursor.fetchone()
                return res is not None

        except Exception as e:
            print (f'Ошибка: {str(e)}')
            return False


    def get_status(self, chat_id):
        """ Эта фунция будет возвращать информацию о пользователе
            name, surname, money. Возвращает словарь """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT name, surname, user_money FROM users WHERE id_telegram = %s", (chat_id, ))
                return cursor.fetchone() # Принимается кортеж, но в моем случае словарь, так как dictcursor


        except Exception as e:
            print(f"Ошибка: {str(e)}") 
        
    
    def money_operation(self, chat_id, money):
        """ Добавление в базу данных новых поступлений или отчислений пользователя """
        try:
            with self.connection.cursor() as cursor:
                # Получаем текущий баланс пользователя
                cursor.execute("SELECT user_money FROM users WHERE id_telegram = %s", (chat_id,))
                row = cursor.fetchone()
                if row is None:
                    print(f"Пользователь {chat_id} не найден")
                    return False

                current_money = row['user_money'] or 0
                # Проверяем, хватит ли денег после операции
                if current_money + money < 0:
                    print(f"Недостаточно денег у пользователя {chat_id}")
                    return False

                # Обновляем баланс
                cursor.execute(
                    "UPDATE users SET user_money = user_money + %s WHERE id_telegram = %s",
                    (money, chat_id)
                )
                self.connection.commit()
                return True

        except Exception as e:
            self.connection.rollback()
            print(f"Ошибка при обновлении баланса: {e} у пользователя {chat_id}")
            return False


    def close(self):
        """ Закрываем соединение """
        if self.connection:
            self.connection.close()


  