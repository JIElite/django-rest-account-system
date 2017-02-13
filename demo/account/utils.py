import re

PASSWORD_PATTERN = r'[0-9a-zA-Z]+'
password_regex = re.compile(PASSWORD_PATTERN)

def is_valid_password(password):
    length_of_pwd = len(password)
    
    if length_of_pwd < 6 or length_of_pwd > 20:
        return False
    
    return password_regex.fullmatch(password)

    

