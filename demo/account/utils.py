import re

PASSWORD_MAX_LENGTH = 20
PASSWORD_MIN_LENGTH = 6
PASSWORD_PATTERN = r'[0-9a-zA-Z]+'
password_regex = re.compile(PASSWORD_PATTERN)


def is_valid_password(password):
    length_of_pwd = len(password)
    if length_of_pwd < PASSWORD_MIN_LENGTH or length_of_pwd > PASSWORD_MAX_LENGTH:
        return False
    
    return password_regex.fullmatch(password)

    

