import config

from bot import EmailBotService

if __name__ == "__main__":
    email_bot = EmailBotService(access_token=config.BOT_ACCESS_TOKEN)
    email_bot.run_bot()
