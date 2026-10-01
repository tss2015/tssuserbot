from cryptography.fernet import Fernet


class SessionManager:
    def __init__(self, key: str):
        self.fernet = Fernet(key.encode())

    def encrypt(self, session: str) -> str:
        return self.fernet.encrypt(session.encode()).decode()

    def decrypt(self, value: str) -> str:
        return self.fernet.decrypt(value.encode()).decode()
