import string
import logging
import argparse
from collections import Counter
import sys
from telegram.client import Telegram


"""

'MIIBCgKCAQEAwVACPi9w23mF3tBkdZz+zwrzKOaaQdr01vAbU4E1pvkfj4sqDsm6
lyDONS789sVoD/xCS9Y0hkkC3gtL1tSfTlgCMOOul9lcixlEKzwKENj1Yz/s7daS
an9tqw3bfUV/nqgbhGX81v/+7RFAEd+RwFnK7a+XYl9sluzHRyVVaTTveB2GazTw
Efzk2DWgkBluml8OREmvfraX3bkHZJTKX4EQSjBbbdJ2ZXIsRrYOXfaA+xayEGB+
8hdlLmAjbCVfaigxX0CDqWeR1yFL9kwd9P0NsZRPsmoqVwMbMu7mStFai6aIhc3n
Slv8kg9qv1m6XHVQY3PnEw+QQtqSIXklHwIDAQAB'

"""
def setup_logging(level=logging.INFO):
    root = logging.getLogger()
    root.setLevel(level)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)

def retreive_messages(telegram, chat_id, receive_limit):
    receive = True
    from_message_id = 0
    stats_data = {}

    while receive:
        response = telegram.get_chat_history(
            chat_id=chat_id,
            limit=1000,
            from_message_id=from_message_id,
        )
        print(str(response))
        response.wait()
        print(str(response))
        for message in response.update['messages']:
            if message['content']['@type'] == 'messageText':
                stats_data[message['id']] = message['content']['text']['text']
            from_message_id = message['id']

        total_messages = len(stats_data)
        if total_messages > receive_limit or not response.update['total_count']:
            receive = False

        print(f'[{total_messages}/{receive_limit}] received')

    return stats_data


def print_stats(stats_data, most_common_count):
    words = Counter()
    translator = str.maketrans('', '', string.punctuation)
    for _, message in stats_data.items():
        for word in message.split(' '):
            word = word.translate(translator).lower()
            if len(word) > 3:
                words[word] += 1

    for word, count in words.most_common(most_common_count):
        print(f'{word}: {count}')


if __name__ == '__main__':
    setup_logging(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument('api_id', help='API id')  # https://my.telegram.org/apps
    parser.add_argument('api_hash', help='API hash')
    parser.add_argument('phone', help='Phone')
    parser.add_argument('chat_id', help='Chat ID')
    parser.add_argument('--limit', help='Messages to retrieve', type=int, default=1000)
    parser.add_argument('--most-common', help='Most common count', type=int, default=30)
    args = parser.parse_args()

    tg = Telegram(
        api_id=args.api_id,
        api_hash=args.api_hash,
        phone=args.phone,
        database_encryption_key='changeme1234',
    )

    # you must call login method before others
    tg.login()
    res = tg.get_chats()
    # todo get_chats is no longer supported by td_lib since chatListMain and chatListArchive
    # todo use https://github.com/tdlib/td/blob/master/example/python/tdjson_example.py
    # todo and https://core.telegram.org/tdlib/getting-started
    # todo to create your own Telegram pip package

    print(res.update)
    res.wait()
    print(res.update)
    # stats_data = retreive_messages(
    #     telegram=tg,
    #     #chat_id=args.chat_id,
    #     chat_id=1,
    #     #receive_limit=args.limit,
    #     receive_limit=1000,
    # )
    #
    # print_stats(
    #     stats_data=stats_data,
    #     # most_common_count=args.most_common,
    #     most_common_count=30,
    # )




