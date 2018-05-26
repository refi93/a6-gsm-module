#!/usr/bin/env python3

import serial
from datetime import datetime

import config
import db
from models import MessageToSend, ReceivedMessage

port = serial.Serial(config.serial_port,  9600, timeout=4)
if (not port.isOpen()):
    port.open()


def send_at_command(command, append_eol=True):
    command = command + "\r\n" if append_eol else command
    port.write(command.encode())
    return list(map(lambda elem: elem.decode("utf-8"), port.readlines()))


def init(pin=None):
    while True:
        result = send_at_command("ATI")
        if len(result) > 0 and result[-1] == "OK\r\n":
            break

    if (not enter_pin(pin)):
        raise Error("PIN authentification has failed!")

    # switch to text mode so commands look nicer
    send_at_command("AT+CMGF=1")

    # store received sms on sim card
    # i.e. disable cnmi notifications and set storage
    # of newly arrived messages to gsm module memory
    send_at_command("AT+CNMI=0,0,0,0,0")
    send_at_command("AT+CPMS=\"ME\",\"ME\",\"ME\"")

    print("GSM module initialized!")


def enter_pin(pin=None):
    pin_status = send_at_command("AT+CPIN?")[2]

    if pin_status == "+CPIN:READY\r\n":
        return True
    elif pin_status == "+CPIN:SIM PIN\r\n":
        auth_result = send_at_command("AT+CPIN=\"" + pin + "\"")
        return auth_result[2] == "OK\r\n"
    else:
        return False


def send_sms_message(phone_number, text):
    assert phone_number.startswith("+421")

    command_sequence = [
        "AT+CMGF=1",
        "AT+CMGS=" + phone_number,
        text
    ]

    for command in command_sequence:
        send_at_command(command)

    result = send_at_command(chr(26), False)
    print(result)


def get_sms_messages(category="ALL"):
    assert category in [
        "ALL", "REC READ", "REC UNREAD", "STO UNSENT", "STO SENT"
    ]

    result = []
    response_raw = send_at_command("AT+CMGL=" + category)

    print(response_raw)

    sms_list_raw = response_raw[2:-2]
    # the odd elements are sms metadata, the even ones are sms texts
    sms_pairs = zip(sms_list_raw[0::2], sms_list_raw[1::2])

    for sms_meta, sms_text in sms_pairs:
        result.append(parse_sms(sms_meta, sms_text))

    print(result)

    return result


def delete_all_sms_messages():
    sms_messages_to_delete = get_sms_messages("ALL")

    for sms_message in sms_messages_to_delete:
        delete_sms_message(sms_message["index"])


def delete_sms_message(index):
    return send_at_command("AT+CMGD=" + str(index))


def parse_sms(sms_meta, sms_text):
    sms_meta = sms_meta.split(',')

    return {
        'index': int(sms_meta[0].split(': ')[1]),
        'category': sms_meta[1].split("\"")[1],
        'sender': sms_meta[2].split("\"")[1],
        'date': sms_meta[4].split("\"")[1],
        'text': sms_text
    }

