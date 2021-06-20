import os

os.system("pybabel extract --input-dirs=webhook_server.py -o locales/mybot.pot")
# os.system("pybabel init -i locales/mybot.pot -d locales -D mybot -l en")
os.system(" pybabel update -d locales -D mybot -i locales/mybot.pot")
os.system("pybabel compile -d locales -D mybot")
