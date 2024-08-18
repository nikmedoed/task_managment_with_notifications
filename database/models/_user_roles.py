import enum


class UserRole(str, enum.Enum):
    SUPPLIER = "Постановщик"
    EXECUTOR = "Исполнитель"
    SUPERVISOR = "Руководитель"
    GUEST = 'Гость'

    def __str__(self):
        return self.value
