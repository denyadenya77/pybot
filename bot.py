#Email Bot Service
from __future__ import print_function
import json
import pickle
import os.path
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from google.auth.transport.requests import Request
import base64
import sqlalchemy as db
import time


# SCOPES = [
#     "https://www.googleapis.com/auth/gmail.modify",
#     "https://www.googleapis.com/auth/gmail.metadata"
# ]
SCOPES = [
    # 'https://www.googleapis.com/auth/gmail.metadata',
    # 'https://www.googleapis.com/auth/userinfo.email',
    # 'openid',
    # 'https://www.googleapis.com/auth/gmail.modify',
    # 'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/gmail.readonly'
]


class EmailBotService:
    """Service for communicate with bot and gmail."""
    def __init__(self, access_token: str):
        """Initialize bot work."""
        self.updater = Updater(token=access_token, use_context=True)
        self.track_message = None

        self.chat_id = self.updater.bot

        start_handler = CommandHandler(command="start",
                                       callback=self.start_command)
        # cancel_handler = CommandHandler(command="cancel",
        #                                 callback=self.cancel_command)
        get_message_handler = CommandHandler(command="getmessage",
                                             callback=self.getmessage)
        register_manager_handler = CommandHandler(command='register_manager',
                                                  callback=self.register_manager)
        self.updater.dispatcher.add_handler(start_handler)
        self.updater.dispatcher.add_handler(get_message_handler)
        self.updater.dispatcher.add_handler(register_manager_handler)

    def run_bot(self):
        """Running bot."""
        self.updater.start_polling()

    # def cancel_command(self, bot, update):
    #     """Bot cancel command"""
    #     text_message = "If you want start again please enter /start."
    #     print(text_message)
    #     bot.send_message(chat_id=update.message.chat_id, text=text_message)

    def get_chat_id(self, update):
        chat_id = update['message']['chat']['id']
        return chat_id

    def register_manager(self, update, context):
        new_manager_chat_id = update['message']['chat']['id']
        new_manager_name = update['message']['chat']['first_name']

        with open('managers.json') as obj:
            managers = json.load(obj)

        managers[new_manager_name] = new_manager_chat_id

        with open('managers.json', 'w') as obj:
            json.dump(managers, obj)

        context.bot.send_message(chat_id=update.message.chat_id, text=f'{new_manager_name} - {new_manager_chat_id}')


    def getmessage(self, update, context):
        redirect_uri = "https://thawing-ridge-47246.herokuapp.com"  # используем ссылку на хероку
        # настройка соединения
        flow = Flow.from_client_secrets_file(
            'credentials.json',
            scopes=SCOPES,
            redirect_uri=redirect_uri)

        # engine = db.create_engine('sqlite:////home/denis/PycharmProjects/email_bot/helloworld/db.sqlite3')
        # engine = db.create_engine('postgresql+psycopg2://tdlmpahyaeqjii:84ecbd8bb4f36d2ac3d4c82ee1434d37bcf0b3ba49da73e1aa3b2819cc723b29@ec2-107-21-209-1.compute-1.amazonaws.com/dfv8rpsfcop1eb')

        # подключаемся к базе данных хероку, чтобы вытащить крайний ключ-код
        engine = db.create_engine('postgresql+psycopg2://vxttrrwzkdeaol:367054ad01122101b1b5d9ee099e03253d212ec914e330378952dec6c67e5174@ec2-79-125-126-205.eu-west-1.compute.amazonaws.com/d82qavso2hgauu')

        connection = engine.connect()  # устанавливаем соединение
        metadata = db.MetaData()
        hola_bottable = db.Table('hola_bottable', metadata, autoload=True, autoload_with=engine)  # из всех существующих таблиц выбираем нужную: 'hola_bottable'

        # Equivalent to 'SELECT * FROM census'
        query = db.select([hola_bottable])
        ResultProxy = connection.execute(query)
        ResultSet = ResultProxy.fetchall()  # возвращает список из tuple формата [(id:..., code:...)]

        code = ResultSet[-1][1]  # из списка строк выбираем последнюю

        flow.fetch_token(code=code, code_verifier="111")  # устанавливаем соединение с гуглом

        # You can use flow.credentials, or you can just get a requests session
        # using flow.authorized_session.
        # credentials = flow.credentials()
        session = flow.authorized_session()  # создаем сессию
        response = session.get('https://www.googleapis.com/gmail/v1/users/me/messages').json()  # формируем запрос и получаем ответ сервера

        messages = response["messages"]
        count_of_secret_messages = 0

        # у каждого из сообщений достаем id
        for message in messages[0:10]:
            mid = message['id']

            # получаем сообщение по id
            message_message = session.get(f'https://www.googleapis.com/gmail/v1/users/me/messages/{mid}').json()

            # информация об отправителе, получателе и теме сообщения хранится в ключе 'payload' --> 'headers'
            headers = message_message['payload']['headers']

            from_who = None
            to_whom = None
            subject = None

            for item in headers:

                if item['name'] == 'From':
                    from_who = item['value']
                elif item['name'] == 'To':
                    to_whom = item['value']
                elif item['name'] == 'Subject':
                    subject = item['value']

            # ищем текст сообщения
            # достаем из сообщения его части
            message_payload_parts = message_message['payload']['parts']
            zero_part = message_payload_parts[0]
            if zero_part['mimeType'] == 'text/plain':
                self.message_without_attachments(update, context, message_payload_parts, from_who, to_whom, subject)
            elif zero_part['mimeType'] == 'multipart/alternative':
                self.message_with_attachments(self, context, zero_part, message_payload_parts,
                                              from_who, to_whom, subject)









    def message_without_attachments(self, update, context, message_payload_parts, from_who, to_whom, subject):
        body_of_part = None
        # достаем из нужной части (текст сообщения хранится под нулевым индексом) текст сообщения закодированный в
        # формате "utf-8" и "base64"
        for part in message_payload_parts:
            if part['partId'] == '0':
                body_of_part = part['body']
        # декодируем
        encoded_text = body_of_part['data']
        decodedBytes = base64.urlsafe_b64decode(encoded_text)
        # текст сообщения сохраняем в переменную
        decoded_text = str(decodedBytes, "utf-8")

        secret_key = 'секрет'

        if secret_key in subject or secret_key in decoded_text:

            telebot_message_text = f'Sender: {from_who}.\n' \
                                   f'Receiver: {to_whom}.\n' \
                                   f'Subject: {subject}.\n' \
                                   f'Text of message: {decoded_text}'

            with open('managers.json') as obj:
                managers = json.load(obj)

            for m_chat_id in managers.values():
                context.bot.send_message(chat_id=m_chat_id, text=telebot_message_text)  # отправка сообщения в бот



    def message_with_attachments(self, update, context, zero_part, message_payload_parts, from_who, to_whom, subject):
        zero_part_parts = zero_part['parts']
        sub_zero_part = zero_part_parts[0]
        body_of_part = sub_zero_part['body']

        # декодируем
        encoded_text = body_of_part['data']
        decodedBytes = base64.urlsafe_b64decode(encoded_text)
        # текст сообщения сохраняем в переменную
        decoded_text = str(decodedBytes, "utf-8")

        secret_key = 'секрет'

        if secret_key in subject or secret_key in decoded_text:

            telebot_message_text = f'Sender: {from_who}.\n' \
                                   f'Receiver: {to_whom}.\n' \
                                   f'Subject: {subject}.\n' \
                                   f'Text of message: {decoded_text}'

            with open('managers.json') as obj:
                managers = json.load(obj)

            for m_chat_id in managers.values():
                context.bot.send_message(chat_id=m_chat_id, text=telebot_message_text)  # отправка сообщения в бот









    def start_command(self, update, context):
        """Bot start command"""
        creds = None
        redirect_uri = "https://thawing-ridge-47246.herokuapp.com"
        flow = Flow.from_client_secrets_file(
            'credentials.json',
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        flow.code_verifier = "111"


        # Tell the user to go to the authorization URL.
        auth_url, _ = flow.authorization_url(prompt='consent',  access_type='offline', include_granted_scopes='true')

        telebot_message_text = 'Please go to this URL: {}'.format(auth_url)
        context.bot.send_message(chat_id=update.message.chat_id, text=telebot_message_text)







