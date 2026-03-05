import pymysql as sql
from cnf import config

def init_db():
    initdbconn = sql.connections.Connection(user=config['username'], password=config['password'], host=config['host'])
    with initdbconn.cursor() as cursor:
        cursor.execute(f'CREATE DATABASE IF NOT EXISTS {config["username"]}__match_and_split;')
        cursor.execute(f'USE {config["username"]}__match_and_split;')
        cursor.execute('''CREATE TABLE IF NOT EXISTS `jobs` (
            `id` INT NOT NULL AUTO_INCREMENT,
            `type` VARCHAR(255) NOT NULL,
            `lang` VARCHAR(255) NOT NULL,
            `title` VARCHAR(255) NOT NULL,
            `username` VARCHAR(255) NOT NULL,
            `logfile` VARCHAR(255),
            `status` VARCHAR(255) NOT NULL,
            PRIMARY KEY (`id`)
        )''')
    initdbconn.close()
    
def get_conn():
    init_db()
    dbconn = sql.connections.Connection(user=config['username'], password=config['password'], host=config['host'], database=f'{config["username"]}__match_and_split')
    return dbconn
