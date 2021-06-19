import traceback
from datetime import datetime
import logging

import aiogram.utils.markdown as md
import peewee
from aiogram.dispatcher.filters import ChatTypeFilter
from aiogram.dispatcher.webhook import DEFAULT_ROUTE_NAME
from aiogram.utils.deep_linking import get_start_link

from aiogram import Bot, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import ParseMode, ChatType
from aiogram.utils.executor import set_webhook
import os

from aiohttp import web

from db import db, User

logging.basicConfig(level=logging.INFO)

APP_VERSION = 0.3

API_TOKEN = os.getenv("API_TOKEN")

# logging.info(PORT)
# webhook settings
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST") if os.getenv("WEBHOOK_HOST") else 'https://e4972c9dbaa0.ngrok.io'
WEBHOOK_PATH = '/api/bot/webhook'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# webserver settings
WEBAPP_HOST = os.getenv("WEBAPP_HOST") if os.getenv("WEBAPP_HOST") else '0.0.0.0'  # or ip
WEBAPP_PORT = os.getenv("PORT", 3001)

logging.info(f"Port to listen: {WEBAPP_PORT}")

bot = Bot(token=API_TOKEN)
# For example use simple MemoryStorage for Dispatcher.
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())


# Instance flask server to return frontend and check health
# app = Flask(__name__)


# @app.route('/')
# def hello_world():
#     return f'Eu sou o Seeds Gratidaum Bot e tenho {APP_VERSION} anos de idade.'


# States
class Form(StatesGroup):
    name = State()  # Will be represented in storage as 'Form:name'
    username = State()  # Will be represented in storage as 'Form:age'


@dp.message_handler(commands=['help', 'ajuda'])
async def help_handler(message: types.Message):
    try:
        logging.warning("Help")

        start_link_setup = await get_start_link('setup')

        await bot.send_message(
            message.chat.id,
            md.text(
                md.text('Precisa de ajuda,', md.bold(message.from_user.full_name), '?'),
                md.text('\n'),
                md.text('Segue uma lista de comandos que você pode usar:'),
                md.text('\n'),
                md.text('🥰 /ack @nomedapessoa Mensagem de gratidaum'),
                md.text('       📜 Envia gratidaum para a pessoa selecionada.'),
                md.text('🤔 /help ou /ajuda'),
                md.text('       📜 Esse menu de ajuda'),
                md.text('\n'),
                md.link('🤖 Inicie a configuração CLICANDO AQUI 🤖', start_link_setup),
                md.text('\n'),
                md.text(md.bold('OBS:'), 'Nunca compartilhe sua senha com ninguém, e a guarde em lugar seguro.'),
                sep='\n',
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        db_close()
        logging.error(traceback.format_exc())
        logging.error(e)


# @dp.message_handler(ChatTypeFilter(ChatType.CHANNEL))
# @dp.message_handler(ChatTypeFilter(ChatType.GROUP))

# @dp.message_handler(commands=['start', 'borala', 'bora', 'começar'])
async def start_redirect_help(message: types.Message):
    logging.warning(f"Msg in group or channel. Calling Help {message}")
    await help_handler(message)


@dp.message_handler(commands=['start', 'borala', 'bora', 'começar'])
async def start(message: types.Message):
    try:
        if message.chat.type != 'private':
            await start_redirect_help(message)
            return
        logging.info(f"{message.chat.type}")
        logging.warning("Start")
        user = None
        # await Form.name.set()
        await Form.username.set()
        try:
            if message.from_user.username:
                user = User.get(User.name == message.from_user.username)
            else:
                user = User.get(User.name == message.from_user.full_name)
        except peewee.DoesNotExist:
            logging.info(f"DoesNotExist")
            pass

        if user is None:
            await bot.send_message(
                message.chat.id,
                md.text(
                    md.text('Oie! Prazer em te conhecer,', md.bold(message.from_user.full_name)),
                    md.text('\n'),
                    md.text('Eu sou um', md.underline('robô'), 'que está aqui pra te ajudar a configurar sua conta'),
                    md.text('\n'),
                    md.text('Eu preciso saber o', md.bold('username'), 'da sua conta SEEDS para que você possa receber',
                            md.bold('Gratidaum'), '.'),
                    md.text('\n'),
                    md.text(md.bold('OBS:'), 'Nunca compartilhe sua senha com ninguém, e a guarde em lugar seguro.'),
                    sep='\n',
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
            await message.reply("Qual seu username do SEEDS?")
        else:
            username = user.username
            await bot.send_message(
                message.chat.id,
                md.text(
                    md.text('Olá novamente,', md.bold(message.from_user.full_name)),
                    md.text('\n'),
                    md.text('Você já tem uma conta do SEEDS cadastrado com o username: ', md.bold(username), '.'),
                    md.text('\n'),
                    md.text(md.bold('OBS:'), 'Nunca compartilhe sua senha com ninguém, e a guarde em lugar seguro.'),
                    sep='\n',
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
            await message.reply("Qual o novo username do SEEDS?")

        # Regular request
        # await bot.send_message(message.chat.id, f"Bem vinde: [{message.from_user.id}].")

        # or reply INTO webhook
        # return SendMessage(message.chat.id, message.text)
    except Exception as e:
        db_close()
        logging.error(traceback.format_exc())
        logging.error(e)




# Check username.
@dp.message_handler(lambda message: not message.text.isalnum(), state=Form.username)
async def process_username_invalid(message: types.Message):
    """
    If username is invalid
    """

    return await message.reply(
        "Oh Não! Isso não é um username válido. Vamos tentar novamente.\n"
        "Qual seu username do SEEDS? (Ex: felipenseeds)")


@dp.message_handler(lambda message: message.text.isalnum(), state=Form.username)
async def process_username(message: types.Message, state: FSMContext):
    try:
        # Update state and data
        async with state.proxy() as data:
            data['username'] = message.text
            data['name'] = message.from_user.full_name

            name = message.from_user.full_name if not message.from_user.username else message.from_user.username
            try:
                with db.transaction():
                    has_user = User.get_or_none(name=name)
                    if has_user:
                        logging.info(f" user updated {has_user}")

                        has_user.username = message.text
                        has_user.updated_date = datetime.now()
                        has_user.save()
                    else:
                        user_id = (User.insert(
                            name=name,
                            username=message.text,
                            created_date=datetime.now(),
                            updated_date=datetime.now())
                                   .execute())
                        logging.info(f"UserID upserted: {user_id}")

                # And send message
                await bot.send_message(
                    message.chat.id,
                    md.text(
                        md.text('Muito bem', md.bold(message.from_user.full_name), "!"),
                        md.text('Seu username do SEEDS:', md.bold(data['username'])),
                        md.text('Agora você já pode enviar e receber Gratidaum!'),
                        sep='\n',
                    ),
                    reply_markup=types.ReplyKeyboardRemove(),
                    parse_mode=ParseMode.MARKDOWN,
                )
            except ValueError:
                db_close()
                logging.info(f"Deu ruim no upsert")
                await bot.send_message(
                    message.chat.id,
                    md.text(
                        md.text('Ops. Algo deu errado'),
                        sep='\n',
                    ),
                    reply_markup=types.ReplyKeyboardRemove(),
                    parse_mode=ParseMode.MARKDOWN,
                )

        # Finish conversation
        await state.finish()

    except Exception as e:
        db_close()
        logging.error(e)
        logging.error(traceback.format_exc())


# await message.reply("Tudo certo!!\nAgora você já pode enviar Gratidaum!")


@dp.message_handler(commands='ack')
async def ack(message: types.Message):
    try:
        # check if user is bot message.from_user.is_bot
        if message.from_user.is_bot:
            logging.info("Bot talking...ignore")
            pass
        # extract params
        first = message.get_args()

        if first:
            args = first.split(" ", 1)
            who = args[0] if len(args) > 0 else None
            memo = args[1] if len(args) > 1 else None

            if who is None:
                await bot.send_message(message.chat.id, f"Use /ack @nome Escreva seu Agradecimento")
            else:
                who = who.split('@')
                who = who[len(who) - 1]
            has_user = User.get_or_none(name=who)

            if has_user:
                msg = f"{message.from_user.get_mention()} envia Gratidaum para {who} - {memo}"
                # Reply to chat origin the Gratidaum sent
                await bot.send_message(message.chat.id, msg, parse_mode=ParseMode.MARKDOWN)
                # TODO CallAPI Hypha and create QRCODE and Link to sign transaction
                await bot.send_message(message.from_user.id, msg, parse_mode=ParseMode.MARKDOWN)
                logging.info(msg)
            else:
                start_link_setup = await get_start_link('setup')

                await bot.send_message(message.chat.id, md.text(
                    md.text("Não encontramos essa pessoa de nome", md.bold(who),
                            " talvez seja necessário essa pessoa se registrar."),
                    md.text('\n'),
                    md.link('🤖 Peça que a pessoa inicie a configuração CLICANDO AQUI 🤖', start_link_setup),
                    sep='\n',
                ), parse_mode=ParseMode.MARKDOWN)
                logging.info(f"Esse usuario não foi encontrado no DB {who}")
        else:
            await bot.send_message(message.chat.id, f"Use /ack @nome agradecimento")

        # or reply INTO webhook
        # return SendMessage(message.chat.id, message.text)
    except Exception as e:
        db_close()
        logging.error(e)
        logging.error(traceback.format_exc())


def db_close():
    db.close()


@dp.message_handler()
async def not_founded(message: types.Message):
    logging.warning("not founded")
    # Regular request
    await bot.send_message(message.chat.id, f"Ops! Eu não conheço esse comando: [{message.text}].")

    # or reply INTO webhook
    # return SendMessage(message.chat.id, message.text)


async def on_startup_handler(_dpp):
    logging.warning('Startup..')
    await bot.set_webhook(WEBHOOK_URL)
    # insert code here to run it after start


async def on_shutdown_handler(_dpp):
    logging.warning('Shutting down..')

    # insert code here to run it before shutdown

    # Remove webhook (not acceptable in some cases)
    await bot.delete_webhook()

    # Close DB connection (if used)
    await dp.storage.close()
    await dp.storage.wait_closed()

    logging.warning('Bye!')


async def root_path_handler(_request):
    # name = request.match_info.get('name', "Anonymous")
    return web.Response(text=f'Eu sou o Seeds Gratidaum Bot e tenho {APP_VERSION} anos de idade.')


def start_webhook(dispatcher, webhook_path, *, loop=None, skip_updates=None,
                  on_startup=None, on_shutdown=None, check_ip=False, retry_after=None, route_name=DEFAULT_ROUTE_NAME,
                  **kwargs):
    """
    Start bot in webhook mode

    :param retry_after:
    :param dispatcher:
    :param webhook_path:
    :param loop:
    :param skip_updates:
    :param on_startup:
    :param on_shutdown:
    :param check_ip:
    :param route_name:
    :param kwargs:
    :return:
    """
    executor = set_webhook(dispatcher=dispatcher,
                           webhook_path=webhook_path,
                           loop=loop,
                           skip_updates=skip_updates,
                           on_startup=on_startup,
                           on_shutdown=on_shutdown,
                           check_ip=check_ip,
                           retry_after=retry_after,
                           route_name=route_name)

    # executor.web_app.router.add_route(method="GET",
    #                                   path="/",
    #                                   handler=root_path_handler,
    #                                   name="root_handler")

    executor.web_app.add_routes([web.get("/", root_path_handler)])

    executor.run_app(**kwargs)


if __name__ == '__main__':
    # app.run(host="0.0.0.0", port=PORT)

    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup_handler,
        on_shutdown=on_shutdown_handler,
        skip_updates=True,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )
