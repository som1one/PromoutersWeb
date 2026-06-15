import logging
import os

from _vk import VKBot


def _mask(value: str | None) -> str:
    if not value:
        return "<empty>"
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:4]}...{value[-2:]}"


def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("VK_BOT_TOKEN: %s", _mask(os.getenv("VK_BOT_TOKEN")))
    logging.info("VK_GROUP_ID: %s", os.getenv("VK_GROUP_ID"))
    bot = VKBot()
    bot.run()


if __name__ == "__main__":
    main()
