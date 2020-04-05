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
import os


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


if __name__ == '__main__':
    setup_logging(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument('api_id', help='API id', type=int)  # https://my.telegram.org/apps
    parser.add_argument('api_hash', help='API hash')
    parser.add_argument('phone', help='Phone')
    parser.add_argument('--lib_path', help='path to libtdjson.so.1.6.0', type=str,
                        default='/home/hellovertex/Documents/github.com/tdlib/td/tdlib/lib/libtdjson.so.1.6.0')
    args = parser.parse_args()

    print(f'api_id = {args.api_id}, type={type(args.api_id)}')
    print(f'api_hash = {args.api_hash}, type={type(args.api_hash)}')
    print(f'phone = {args.phone}, type={type(args.phone)}')
    tg = Telegram(
        api_id=args.api_id,
        api_hash=args.api_hash,
        phone=args.phone,
        library_path=args.lib_path,
        database_encryption_key='hanabi',
    )
    # you must call login method before others
    tg.login()


    def get_all_chat_ids():
        offset_order = 9223372036854775807
        offset_chat_id = 0
        chat_ids = list()
        old_len = -1
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


    def extract_supergroup_chats(chat_ids):
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
        for id in chat_ids:
            res = tg.get_chat(id)
            res.wait()
            chat = res.update
            if chat['type']['@type'] == 'chatTypeSupergroup':
                if not chat['type']['is_channel']:
                    crypto_chat_candidates.append(chat)
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
                if not msgs:
                    break
                first = msgs[0]
                last = msgs[-1]
                from_message_id = last['id']
                print(f'number of messages in buffer = {len(msgs)}')
                print(f'date 1st: {timestamp_to_date(first["date"])} -- date last = {timestamp_to_date(last["date"])}')
                ids = np.array([msg['id'] for msg in msgs])
                have_duplicates = bool(int(np.sum(ids == old_ids)))
                assert not have_duplicates
                old_ids = ids
                # todo consider writing directly to file instead
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
        else:
            skip_reason = f'group member count is too low: {group["member_count"]}' if group[
                'is_all_history_available'] else f'history is not available or group is channel'
            print('...Skipping chat because ' + skip_reason)

        return hist


    chat_ids = get_all_chat_ids()
    crypto_chats = extract_supergroup_chats(chat_ids)
    for chat in crypto_chats:
        # If no csv file for current history exists yet
        if not os.path.isfile(f'{chat["title"]}.csv'):
            print(f'getting history for chat: {chat["title"]}...')
            hist = get_chat_history(chat)
            if hist:
                hist[0]['forward_info'] = ''
                hist[0]['reply_markup'] = ''
                keys = hist[0].keys()
                # Create csv file for chat history
                with open(f'{chat["title"]}.csv', 'w') as output_file:
                    print(f'Writing history of {chat["title"]} to .csv file...')
                    dict_writer = csv.DictWriter(output_file, keys)
                    dict_writer.writeheader()
                    dict_writer.writerows(hist)
            else:
                print(f'...History for chat {chat["title"]} is None')
        else:
            print(f'Skipping group {chat["title"]} because .csv file exists already')
