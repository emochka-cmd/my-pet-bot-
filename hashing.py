import hashlib
import secrets


class Hashing:
    def __init__(self, password=None, salt=None):
        self.password = password
        self.salt = salt if salt is not None else self._generate_salt()


    def __call__(self,password=None, salt=None):
        if password is not None:
            self.password = password
        if salt is not None:
            self.salt = salt
        return self


    def _generate_salt(self, lenght=16):
        """ Генерирует случайную соль """
        return secrets.token_hex(lenght)
        

    def hash(self) -> str:
        """ Возвращает захешированый пароль """
        return hashlib.sha256((self.password + self.salt).encode()).hexdigest()


    @staticmethod
    def hash_password(password: str, salt: str) -> str:
        """Статический метод для хеширования пароля с солью"""
        return hashlib.sha256((password + salt).encode()).hexdigest()


    def get_salt(self):
        return self.salt
