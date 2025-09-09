import os

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'root'),
    'database': os.getenv('DB_NAME','qr_scanner'),
    'charset': 'utf8mb4',
    'autocommit': True
}


MAIL_USERNAME=os.getenv('MAIL_USERNAME')
MAIL_PASSWORD=os.getenv('MAIL_PASSWORD')
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USE_SSL = False




# Database table schema
# DATABASE_SCHEMA = """
# CREATE DATABASE IF NOT EXISTS qr_scanner_db;
# USE qr_scanner_db;

# CREATE TABLE IF NOT EXISTS users (
#     id VARCHAR(50) PRIMARY KEY,
#     name VARCHAR(100) NOT NULL,
#     email VARCHAR(100) NOT NULL,
#     flag BOOLEAN DEFAULT FALSE,
#     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
# );

# -- Sample data for testing
# INSERT INTO users (id, name, email, flag) VALUES 
# ('x0x0x0', 'Test User 1', 'test1@example.com', TRUE),
# ('abc123', 'Test User 2', 'test2@example.com', TRUE),
# ('def456', 'Test User 3', 'test3@example.com', FALSE),
# ('ghi789', 'Test User 4', 'test4@example.com', TRUE)
# ON DUPLICATE KEY UPDATE name=VALUES(name), email=VALUES(email), flag=VALUES(flag);
# """



