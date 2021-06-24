import logging

from aiogram.contrib.middlewares.i18n import I18nMiddleware
from aiogram.types import Message

from db import User

# logging.basicConfig(level=logging.INFO)

log = logging.getLogger("i18n_user")


class I18nUserMiddleware(I18nMiddleware):

    async def trigger(self, action, args):
        """
        Event trigger

        :param action: event name
        :param args: event arguments
        :return:
        """
        if 'update' not in action \
                and 'error' not in action \
                and action.startswith('pre_process'):
            message: Message = args[0]
            user_id = message['from']['id']

            has_user = User.get_or_none(user_id=user_id)
            locale = None
            if has_user:
                locale = has_user.locale if has_user.locale else None
            log.info(f"data: {message.from_user.id}, locale:{locale}")
            # locale = await self.get_user_locale(action, args)
            self.ctx_locale.set(locale)
            return True
