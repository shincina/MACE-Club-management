class Config:
    SECRET_KEY = 'mace_secret_2024'
    MYSQL_HOST = 'localhost'
    MYSQL_USER = 'sanusha'
    MYSQL_PASSWORD = 'password'
    MYSQL_DB = 'mace_activity_db'
    MYSQL_CURSORCLASS = 'DictCursor'
    UPLOAD_FOLDER = 'uploads/certificates'
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}