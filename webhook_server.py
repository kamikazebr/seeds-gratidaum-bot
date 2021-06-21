import traceback
from datetime import datetime
import logging
from pathlib import Path
from typing import Optional

import aiogram.utils.markdown as md
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.webhook import DEFAULT_ROUTE_NAME
from aiogram.utils.deep_linking import get_start_link

from aiogram import Bot, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import ParseMode, MessageEntityType, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, \
    MessageEntity
from aiogram.utils.executor import set_webhook
import os

from aiohttp import web
from playhouse.shortcuts import model_to_dict

from api import api_get
from db import db, User
from helpers import strip_html
from i18n_user_middleware import I18nUserMiddleware
from migrate import start_migration

logging.basicConfig(level=logging.INFO)

APP_VERSION = 0.5

API_TOKEN = os.getenv("API_TOKEN")
CHAT_ID_FATHER = os.getenv("CHAT_ID_FATHER", None)

if not CHAT_ID_FATHER:
    logging.warning(f"Chat ID FATHER is not present, check your CHAT_ID_FATHER env variables")

# webhook settings
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST") if os.getenv("WEBHOOK_HOST") else 'https://c2da1c477408.ngrok.io'
WEBHOOK_PATH = '/api/bot/webhook'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# webserver settings
WEBAPP_HOST = os.getenv("WEBAPP_HOST") if os.getenv("WEBAPP_HOST") else '0.0.0.0'  # or ip
WEBAPP_PORT = os.getenv("PORT", 3001)

logging.info(f"Port to listen: {WEBAPP_PORT}")

# Start migration
start_migration()

bot = Bot(token=API_TOKEN)

# For example use simple MemoryStorage for Dispatcher.
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

I18N_DOMAIN = 'mybot'

BASE_DIR = Path(__file__).parent
LOCALES_DIR = BASE_DIR / 'locales'

# Setup i18n middleware
i18n = I18nUserMiddleware(I18N_DOMAIN, LOCALES_DIR)
dp.middleware.setup(i18n)

# Alias for gettext method
_ = i18n.gettext


# States
class Form(StatesGroup):
    name = State()  # Will be represented in storage as 'Form:name'
    username = State()  # Will be represented in storage as 'Form:username'
    # language = State()  # Will be represented in storage as 'Form:language'


# Helper funcs
async def send_msg_father(msg):
    if CHAT_ID_FATHER:
        await bot.send_message(chat_id=CHAT_ID_FATHER, text=msg)
    else:
        logging.info("CHAT_ID_FATHER env not defined in send_msg_father(). Do nothihg")


def build_qr_msg(json_eosio, to_who=None):
    link_wallet = f'https://eosio.to/{json_eosio["esr"][6:]}'
    link_confirm_transaction = md.hlink(_("Confirme o envio da Gratidaum"), link_wallet)
    qr_code = md.hide_link(json_eosio['qr'])
    to = to_who if to_who else _('a pessoa')
    return _("🥳 Sua Gratidaum está quase chegando para {to} 🎉\n\n"
             "Você precisa confirmar a transação.\n"
             "Você tem 2 opções:\n\n"
             'Clique no link abaixo para assinar com Seeds Wallet/Anchor\n'
             '{link_confirm_transaction}\n\n'
             'Ou\n\n'
             "Escaneie o QR Code para confirmar a transação"
             "{qr_code}\n"
             'Em casos de dúvidas digite /ajuda').format(
        to=to,
        qr_code=qr_code,
        link_confirm_transaction=link_confirm_transaction)


async def start_redirect_help(message: types.Message):
    logging.warning(f"Msg in group or channel. Calling Help {message}")
    await help_handler(message)


def get_user_id(message):
    msg_entity = None
    for msgEntity in message.entities:
        if msgEntity.type == MessageEntityType.TEXT_MENTION and msgEntity.user:
            msg_entity = msgEntity
            break
    return msg_entity


def db_close():
    db.close()


async def i18n_HELP(full_name, locale=None):
    start_link_setup = await get_start_link('setup')
    msg_footer = _('<b>OBS:</b> Nunca compartilhe sua senha com ninguém, e a guarde em lugar seguro.')
    return _('Precisa de ajuda, <b>{full_name}</b>?\n'
             'Segue uma lista de comandos que você pode usar:\n\n'
             '🥰 /gratz @nomedapessoa Mensagem de gratidaum\n'
             '       📜 Envia gratidaum para a pessoa selecionada.\n'
             '🤔 /ajuda\n'
             '       📜 Esse menu de ajuda\n\n' +
             '<a href="{start_link_setup}" >🤖 Inicie a configuração CLICANDO AQUI 🤖</a>\n\n'
             '{msg_footer}',
             locale=locale).format(full_name=full_name, start_link_setup=start_link_setup, msg_footer=msg_footer)


# END - Helper funcs

# Query Callbacks

# Use multiple registrators. Handler will execute when one of the filters is OK
@dp.callback_query_handler(state='*')
# @dp.callback_query_handler(text='pt')
async def query_language_callback_handler(query: CallbackQuery):
    locale = query.data
    # always answer callback queries, even if you have nothing to say
    try:
        i18n.ctx_locale.set(locale)
        logging.info(f"query_language_callback_handler: {query.data}")
        await query.answer(_('Idioma Português selecionado.'))
    except Exception as e:
        logging.error(traceback.format_exc())
        logging.error(e)

    user_id = query.from_user.id
    logging.info(f"User id: {query.from_user.id}")
    if user_id:
        has_user = User.get_or_none(user_id=query.from_user.id)
        if not has_user:
            logging.info(f"Creating from user id: {query.from_user.id}")
            has_user = User.create(
                user_id=query.from_user.id,
                name=f"{query.from_user.full_name}",
                username=f"{query.from_user.username}",
                created_date=datetime.now(),
                updated_date=datetime.now(),
            )
            logging.info(f"has_user in except: {has_user}")

        if has_user:
            logging.info(f"Changed Locale to: {i18n.ctx_locale.get()}")
            has_user.locale = locale
            has_user.save()
            # logging.info(f"Changed Locale to")
            text = await i18n_HELP(query.from_user.full_name, locale)
            try:
                await bot.edit_message_text(chat_id=query.message.chat.id,
                                            message_id=query.message.message_id,
                                            text=text,
                                            reply_markup=build_language_keyboard(),
                                            parse_mode=ParseMode.HTML)
            except Exception as e:
                logging.error(traceback.format_exc())
                logging.error(e)
            # await start(query.message)
        else:
            logging.info(f"User not found: {query.from_user.id}")
    else:
        logging.info("user_id no present in query")

    # await bot.answer_callback_query(query.id,text,True)
    #


@dp.message_handler(commands=['help', 'ajuda'])
async def help_handler(message: types.Message):
    try:
        locale = i18n.ctx_locale.get()
        logging.warning(f"Help locale:{locale}")
        text_help = await i18n_HELP(full_name=message.from_user.full_name, locale=locale)

        keyboard_markup = build_language_keyboard()

        await bot.send_message(
            message.chat.id,
            md.text(text_help, sep='\n'),
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard_markup
        )

    except Exception as e:
        db_close()
        logging.error(traceback.format_exc())
        logging.error(e)


@dp.my_chat_member_handler()
async def some_handler(my_chat_member: types.ChatMemberUpdated):
    logging.info(f"Chat member update: {my_chat_member}")

    user = my_chat_member.new_chat_member.user
    status = my_chat_member.new_chat_member.status
    if user.is_bot:
        if status == "member":
            msg = f"'{my_chat_member.from_user.full_name}' adicionou o Bot no grupo '{my_chat_member.chat.title}'"
            logging.info(msg)
            await send_msg_father(msg)
            # logging.info(f"Não me é permitido ficar aqui. Saindo do grupo")
            # await my_chat_member.chat.leave()
        elif status == "left":
            msg = f"'{my_chat_member.from_user.full_name}' removeu o Bot do grupo '{my_chat_member.chat.title}'"
            logging.info(msg)
            await send_msg_father(msg)


@dp.message_handler(commands=['admin'])
async def admin(message: types.Message):
    try:
        logging.info(f"admin: {message}")
    except Exception as e:
        logging.error(traceback.format_exc())
        logging.error(f"error: {e}")


def build_language_keyboard():
    keyboard_markup = InlineKeyboardMarkup(row_width=3)
    # default row_width is 3, so here we can omit it actually
    # kept for clearness

    text_and_data = (
        ('🇧🇷 Português 🇧🇷', 'pt'),
        ('🇺🇸 English 🇺🇸', 'en'),
    )
    # in real life for the callback_data the callback data factory should be used
    # here the raw string is used for the simplicity
    row_btns = (InlineKeyboardButton(text, callback_data=data) for text, data in text_and_data)
    # CallbackData("lang","locale","action")
    keyboard_markup.row(*row_btns)
    # keyboard_markup.add(
    #     # url buttons have no callback data
    #     types.InlineKeyboardButton('aiogram source', url='https://github.com/aiogram/aiogram'),
    # )
    return keyboard_markup
    # await message.reply("Hi!\nDo you love aiogram?", )


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
        # await Form.language.set()
        try:
            if message.from_user.username:
                user = User.get(User.name == message.from_user.username)
            else:
                user = User.get(User.name == message.from_user.full_name)
        except Exception as e:
            logging.info(f"UserDoesNotExist just ignore")
            logging.error(traceback.format_exc())
            logging.error(e)

        msg_footer = _('<b>OBS:</b> Nunca compartilhe sua senha com ninguém, e a guarde em lugar seguro.')

        if user is None:
            await bot.send_message(
                message.chat.id,
                md.text(
                    _('Olá Prazer em te conhecer,<b>{full_name}</b>\n\n'
                      'Eu sou um <b>robô</b> que está aqui pra te ajudar a configurar sua conta\n\n'
                      'Eu preciso saber o <b>username</b> da sua conta SEEDS para que você possa receber <b>Gratidaum</b>.\n\n'
                      'Envie "cancel" (sem aspas) a qualquer momento para cancelar\n\n'
                      '{msg_footer}')
                        .format(full_name=message.from_user.full_name, msg_footer=msg_footer),
                    sep='\n',
                ),
                parse_mode=ParseMode.HTML,
            )
            await message.reply(_("Qual seu username do SEEDS?"))
        else:
            username = user.username

            await bot.send_message(
                message.chat.id,
                md.text(
                    _('Olá novamente,<b>{full_name}</b>\n\n'
                      'Você já tem uma conta do SEEDS cadastrado com o username: {username}.\n\n'
                      'Envie "cancel" (sem aspas) a qualquer momento para cancelar\n\n'
                      '{msg_footer}')
                        .format(full_name=message.from_user.full_name,
                                username=username, msg_footer=msg_footer),
                    sep='\n',
                ),
                parse_mode=ParseMode.HTML,
            )
            await message.reply(_("Qual o novo username do SEEDS?"))

    except Exception as e:
        db_close()
        logging.error(traceback.format_exc())
        logging.error(e)


# You can use state '*' if you need to handle all states
@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals='cancel', ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    """
    Allow user to cancel any action
    """
    current_state = await state.get_state()
    if current_state is None:
        return

    logging.info('Cancelling state %r', current_state)
    # Cancel state and inform user about it
    await state.finish()
    # And remove keyboard (just in case)
    await message.reply(_('Cancelado.'), reply_markup=types.ReplyKeyboardRemove())


# Check username.
@dp.message_handler(lambda message: not message.text.isalnum(), state=Form.username)
async def process_username_invalid(message: types.Message):
    """
    If username is invalid
    """

    return await message.reply(
        _("Oh Não! Isso não é um username válido. Vamos tentar novamente.\n"
          "Qual seu username do SEEDS? (Ex: felipenseeds)"))


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
                    has_user = User.get_or_none(user_id=message.from_user.id)
                    if has_user:
                        has_user.username = message.text
                        # has_user.user_id = message.from_user.id
                        has_user.updated_date = datetime.now()
                        has_user.save()
                        logging.info(f" user updated by user_id {has_user}")
                    else:
                        has_user = User.get_or_none(name=name)
                        if has_user:
                            has_user.username = message.text
                            has_user.user_id = message.from_user.id
                            has_user.updated_date = datetime.now()
                            has_user.save()
                            logging.info(f" user updated by name {model_to_dict(has_user)}")
                        else:
                            user_id = (User.insert(
                                name=name,
                                username=message.text,
                                user_id=message.from_user.id,
                                created_date=datetime.now(),
                                updated_date=datetime.now())
                                       .execute())
                            logging.info(f"UserID upserted: {user_id}")

                # And send message
                await bot.send_message(
                    message.chat.id,
                    md.text(
                        _('Muito bem <b>{full_name}</b>!\n'
                          'Seu username do SEEDS: <b>{username}</b>\n'
                          'Agora você já pode enviar e receber Gratidaum!')
                            .format(full_name=message.from_user.full_name, username=data['username']),
                        sep='\n',
                    ),
                    reply_markup=types.ReplyKeyboardRemove(),
                    parse_mode=ParseMode.HTML,
                )
            except ValueError:
                db_close()
                logging.info(f"Deu ruim no upsert")
                await bot.send_message(
                    message.chat.id,
                    md.text(
                        _('Ops. Algo deu errado'),
                        sep='\n',
                    ),
                    reply_markup=types.ReplyKeyboardRemove(),
                    parse_mode=ParseMode.HTML,
                )

        # Finish conversation
        await state.finish()

    except Exception as e:
        db_close()
        logging.error(e)
        logging.error(traceback.format_exc())


@dp.message_handler(commands=['ack', 'gratz'])
async def ack(message: types.Message):
    try:
        # check if user is bot message.from_user.is_bot
        if message.from_user.is_bot:
            logging.info("Bot talking...ignore")
            return

            # extract params
        first = message.get_args()

        if first:
            # args = first.split(" ", 1)
            # who = args[0] if len(args) > 0 else None
            # memo = args[1] if len(args) > 1 else None
            who = None
            memo = None

            msg_entity: Optional[MessageEntity] = get_user_id(message)
            user_id = msg_entity.user.id
            if message.text:
                who = message.text[msg_entity.offset: msg_entity.offset + msg_entity.length]
                memo = message.text[msg_entity.offset + msg_entity.length:]

            logging.debug(f"Memo before strip_html: {memo}")
            memo = strip_html(memo)
            logging.debug(f"Memo after strip_html: {memo}")

            if who is None:
                await bot.send_message(message.chat.id, _("Use /ack @nome Escreva seu Agradecimento"))
            else:
                who = who.split('@')
                who = who[len(who) - 1]

            has_user = None
            if user_id:
                has_user = User.get_or_none(user_id=user_id)

            if not has_user:
                has_user = User.get_or_none(name=who)

            if has_user:
                # msg = f"{user_mention} envia Gratidaum para {who}{f' - {memo}' if memo else ''}"

                msg = _("{user_mention} envia Gratidaum para {who} {memo}").format(
                    user_mention=message.from_user.get_mention(as_html=True),
                    who=who,
                    memo=memo)
                # Reply to chat origin the Gratidaum sent
                await bot.send_message(message.chat.id, msg, parse_mode=ParseMode.HTML)
                logging.info(msg)
                # CallAPI Hypha and create QRCODE and Link to sign transaction
                json_eosio = await api_get(account=f"{has_user.username}", memo=memo)
                logging.info(json_eosio)
                res = build_qr_msg(json_eosio, who)
                logging.info(res)
                await bot.send_message(message.from_user.id, res, parse_mode=ParseMode.HTML,
                                       disable_web_page_preview=False)

            else:
                start_link_setup = await get_start_link('setup')
                link_setup_html = md.hlink(_('🤖 Peça que a pessoa inicie a configuração CLICANDO AQUI 🤖'),
                                           start_link_setup)
                await bot.send_message(message.chat.id, md.text(
                    _("Não encontramos essa pessoa de nome <b>{who}</b> "
                      "talvez seja necessário essa pessoa se registrar.\n\n"
                      "{link_setup_html}").format(who=who, link_setup_html=link_setup_html),
                    sep='\n',
                ), parse_mode=ParseMode.HTML)
                logging.info(f"Esse usuario não foi encontrado no DB {who}")
        else:
            await bot.send_message(message.chat.id, _("Use /ack @nome agradecimento"))

    except Exception as e:
        db_close()
        logging.error(e)
        logging.error(traceback.format_exc())


@dp.message_handler()
async def not_found(message: types.Message):
    logging.warning("Not found")
    # Regular request
    await bot.send_message(message.chat.id, _("Ops! Eu não conheço esse comando: [{command}].")
                           .format(command=message.text))


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
    start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup_handler,
        on_shutdown=on_shutdown_handler,
        skip_updates=True,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
    )
