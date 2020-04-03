import string
import logging
import argparse
import time
from collections import Counter
import sys
from telegram.client import Telegram
import csv
from datetime import datetime
import numpy as np
"""

'MIIBCgKCAQEAwVACPi9w23mF3tBkdZz+zwrzKOaaQdr01vAbU4E1pvkfj4sqDsm6
lyDONS789sVoD/xCS9Y0hkkC3gtL1tSfTlgCMOOul9lcixlEKzwKENj1Yz/s7daS
an9tqw3bfUV/nqgbhGX81v/+7RFAEd+RwFnK7a+XYl9sluzHRyVVaTTveB2GazTw
Efzk2DWgkBluml8OREmvfraX3bkHZJTKX4EQSjBbbdJ2ZXIsRrYOXfaA+xayEGB+
8hdlLmAjbCVfaigxX0CDqWeR1yFL9kwd9P0NsZRPsmoqVwMbMu7mStFai6aIhc3n
Slv8kg9qv1m6XHVQY3PnEw+QQtqSIXklHwIDAQAB'

python script.py 


"""

def timestamp_to_date(ts: int) -> str:
    return datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

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

    tg = Telegram(
        api_id=123456789,
        api_hash='hash',
        phone='phone',
        library_path='lib_path',
        database_encryption_key='changeMe'
    )
    # you must call login method before others
    tg.login()

    def get_all_chat_ids():
        offset_order = 9223372036854775807
        offset_chat_id = 0
        chat_ids = list()
        old_len = -1
        # Optional: Only get chats with type Supergroup
        while True:
            # get chat_ids from current offset_order, offset_chat_id
            res = tg.get_chats(offset_order=offset_order, offset_chat_id=offset_chat_id, limit=100)
            res.wait()
            chat_ids += res.update['chat_ids']
            # remove duplicates from chat_ids
            chat_ids = list(dict.fromkeys(chat_ids))
            # get id, order from last chat
            res = tg.get_chat(chat_ids[-1])
            res.wait()
            last_chat = res.update
            # update offset_order, offset_chat_id
            offset_chat_id = last_chat['id']
            offset_order = last_chat['order']
            new_len = len(chat_ids)
            print(f'old_len = {old_len}, new_len = {new_len}')
            if old_len == new_len:
                print(f'Fetched {len(chat_ids)} chats.')
                break
            old_len = new_len
        return chat_ids
    # blacklist = [("Gil's Gang", -1001458106605), ("Hilfestellung", -1001166164071), ("Umzug bitches", -1001376933463)]
    # assumes the supgergroups of interest are archived
    def extract_crypto_chats(chat_ids):
        """ chat keys
            dict_keys(
            ['@type', 'id', 'type', 'chat_list', 'title', 'photo', 'permissions', 'last_message', 'order',
            'is_pinned', 'is_marked_as_unread', 'is_sponsored', 'has_scheduled_messages',
            'can_be_deleted_only_for_self', 'can_be_deleted_for_all_users', 'can_be_reported',
            'default_disable_notification', 'unread_count', 'last_read_inbox_message_id',
            'last_read_outbox_message_id', 'unread_mention_count', 'notification_settings',
            'pinned_message_id', 'reply_markup_message_id', 'client_data', '@extra'])
        """
        crypto_chat_candidates = list()
        i = 0
        for id in chat_ids:
            res = tg.get_chat(id)
            res.wait()
            chat = res.update
            if i == 0:
                pass
                # print(chat.keys())
                # print(chat['chat_list'])
            # print(f'chat["type"] = {chat["type"]}')
            if chat['type']['@type'] == 'chatTypeSupergroup':
                crypto_chat_candidates.append(chat)
            i += 1
        # remove supergroups that are not cryptochannels, if any
        return crypto_chat_candidates

    def get_chat_history(chat_obj):
        """ supergroup keys
            dict_keys(
            ['@type', 'description', 'member_count', 'administrator_count', 'restricted_count', 'banned_count',
             'linked_chat_id', 'slow_mode_delay', 'slow_mode_delay_expires_in', 'can_get_members',
             'can_set_username', 'can_set_sticker_set', 'can_set_location', 'can_view_statistics',
             'is_all_history_available', 'sticker_set_id', 'invite_link', 'upgraded_from_basic_group_id',
             'upgraded_from_max_message_id', '@extra'])
        """
        def _get_history(id):
            from_message_id = 0
            offset = 0
            messages = list()
            completed = False
            old_ids = []
            # loop
            while not completed:
                res = tg.get_chat_history(id, limit=100, from_message_id=from_message_id, offset=0)
                res.wait()
                msgs = res.update['messages']
                first = msgs[0]
                last = msgs[-1]
                from_message_id = last['id']
                print(f'number of messages in buffer = {len(msgs)}')
                print(f'date 1st: {timestamp_to_date(first["date"])} -- date last = {timestamp_to_date(last["date"])}')
                ids = np.array([msg['id'] for msg in msgs])
                have_duplicates = bool(int(np.sum(ids == old_ids)))
                assert not have_duplicates
                old_ids = ids
                if len(msgs) < 1:
                    completed = True
                messages += msgs
                print(f'total number of messages fetched = {len(messages)}')
                time.sleep(.5)
            return messages

        # get supergroup id from chat_obj
        supergroup_id = chat_obj['type']['supergroup_id']
        is_channel = chat_obj['type']['is_channel']

        # get supergroup info by supergroup id
        res = tg.get_supergroup_full_info(supergroup_id)
        res.wait()
        group = res.update
        hist = None
        if group['is_all_history_available'] and group['member_count'] >= 500 and not is_channel:
            # get chat_history
            hist = _get_history(chat_obj['id'])

        return hist

    chat_ids = get_all_chat_ids()
    crypto_chats = extract_crypto_chats(chat_ids)
    histories = list()
    hist = get_chat_history(crypto_chats[0])
    keys = hist[0].keys()
    # todo rename file according to chat id
    with open('example.csv', 'wb') as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(hist)
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




