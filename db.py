import logging
import os

from peewee import *
import datetime

db = None

DATABASE_URL = os.getenv('DATABASE_URL', None)
try:
    # logging.error(f"DATABASE_URL: {DATABASE_URL}")
    if DATABASE_URL:
        full = DATABASE_URL.split("//")[1]
        [part1, part2] = full.split("@")
        [USER, PASSWORD] = part1.split(":")
        [part3, DBNAME] = part2.split("/")
        [HOST, PORT] = part3.split(":")

    HOST = os.getenv('PG_HOST', None) if not HOST else HOST
    USER = os.getenv('PG_USER', None) if not USER else USER
    DBNAME = os.getenv('PG_DBNAME', None) if not DBNAME else DBNAME
    PORT = os.getenv('PG_PORT', 5432) if not PORT else PORT
    PASSWORD = os.getenv('PG_PASSWORD', None) if not PASSWORD else PASSWORD

    if not HOST or not USER or not DBNAME or not PASSWORD:
        raise Exception(f"Must define PG_HOST PG_USER PG_DBNAME PG_PASSWORD [PG_PORT]")
    else:
        db = PostgresqlDatabase(DBNAME, host=HOST, user=USER, password=PASSWORD)
except Exception as e:
    logging.error(f"Some error with env database: {e}")


class BaseModel(Model):
    class Meta:
        database = db


class DBVersion(BaseModel):
    number = AutoField()
    created_date = DateTimeField(default=datetime.datetime.now())


class User(BaseModel):
    pk_id = AutoField()
    user_id = CharField(primary_key=False, null=True)
    name = CharField(primary_key=False, unique=False)
    username = CharField()
    locale = CharField(null=True)
    created_date = DateTimeField()
    updated_date = DateTimeField()


db.connect()

# db.drop_tables([User])

db.create_tables([User, DBVersion])
