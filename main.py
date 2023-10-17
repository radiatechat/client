import os
import sys
if sys.__stdout__ is None or sys.__stderr__ is None:
    os.environ['KIVY_NO_CONSOLELOG'] = '1'

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.utils import escape_markup
from websockets.sync.client import connect
from threading import Thread
from json import loads

with open('config.txt') as _config:
    config = _config.read().splitlines()
    config = dict([tuple(i.split(': ',1)) for i in config])
    websocket = connect(config['server'])

def close():
    websocket.close()
    websocket.close_socket()

try:
    class Formatter: #purely using this to distinguish format strings and regular strings
        def __init__(self,string):
            self.string = string
        def __repr__(self):
            return self.string

    class ChatHandler:
        def __init__(self, chat):
            self.chat = chat
            self.chatlog = chat.ids.chatlog
            self.chatbox = chat.ids.chatbox
            self.chatscroll = chat.ids.chatscroll
            self.username = False #has the user entered a username yet

        def subformatting(self, texts, trigger, opening, closing):
            out = []
            for text in texts:
                if isinstance(text, str):
                    outs = []
                    count = 0
                    idx = 0
                    i = 0
                    while idx < len(text):
                        i = text[idx]
                        if i == trigger[0]:
                            if count+1 != text.count(trigger) or count%2==1: #you dont want *a** to become [b]a[/b][b]
                                if text[idx:].startswith(trigger): #is the trigger there
                                    outs.append((Formatter(opening),Formatter(closing))[count%2])
                                    count += 1
                                    idx += len(trigger)
                                    continue
                        if len(outs) == 0 or isinstance(outs[-1], Formatter):
                            outs.append(i)
                        else:
                            outs[-1] += i
                        idx += 1
                    out += outs
                else:
                    out.append(text)
            return out

        def colorformatting(self, texts, trigger, formatter):
            out = []
            colorstack = 0
            for text in texts:
                if isinstance(text, str):
                    outs = []
                    idx = 0
                    while idx < len(text):
                        i = text[idx]
                        if text[idx:].startswith(trigger):
                            outs.append(Formatter(formatter))
                            colorstack += 1
                            idx += len(trigger)
                            continue
                        if len(outs) == 0 or isinstance(outs[-1], Formatter):
                            outs.append(i)
                        else:
                            outs[-1] += i
                        idx += 1
                    out += outs
                else:
                    out.append(text)
            return out+[Formatter('[/color]')]*colorstack

        def formatting(self, text):
            out = ""
            txts = [text]
            txts = self.colorformatting(txts, '{r}', '[color=#D02020]')
            txts = self.colorformatting(txts, '{g}', '[color=#20D020]')
            txts = self.colorformatting(txts, '{b}', '[color=#2020D0]')
            txts = self.colorformatting(txts, '{y}', '[color=#D0D020]')
            txts = self.colorformatting(txts, '{d}', '[color=#808080]')
            txts = self.colorformatting(txts, '{/}', '[/color]')
            txts = self.subformatting(txts, '***', '[b][i]', '[/i][/b]')
            txts = self.subformatting(txts, '**', '[b]', '[/b]')
            txts = self.subformatting(txts, '*', '[i]', '[/i]')
            txts = self.subformatting(txts, '~~', '[s]', '[/s]')
            txts = self.subformatting(txts, '__', '[u]', '[/u]')
            txts = self.subformatting(txts, '_', '[u]', '[/u]')
            txts = self.subformatting(txts, '^^', '[sub]', '[/sub]')
            txts = self.subformatting(txts, '^', '[sup]', '[/sup]')
            txts = self.subformatting(txts, '`', '[font=resources/mono.ttf]', '[/font]')
            print(txts)
            for i in txts:
                if isinstance(i, Formatter):
                    out += i.string
                else:
                    out += escape_markup(i)
            return out

        def format(self, text, user=None):
            formatted = self.formatting(text)
            if user is not None:
                return f"\n{user}: {formatted}"
            else:
                return f"\n{formatted}"

        def jump_to_bottom(self, dt):
            if self.chatscroll.vbar[1] != 1:
                self.chatscroll.scroll_y = 0
        def push_text(self, text):
            self.chatlog.text += text
            if self.chatscroll.scroll_y == 0 or self.chatscroll.vbar[1] == 1:
                Clock.schedule_once(self.jump_to_bottom)

        def on_receive(self, value):
            message = loads(value)
            match message['id']:
                case "response_chat_message":
                    self.push_text(self.format(message['data'], message['user']))
                case "response_system_message":
                    self.push_text(self.format(message['data']))

        def on_enter(self, value):
            self.chatbox.text = ''
            if not self.username:
                websocket.send(value)
                self.username = True
                self.chatlog.text = ''
            else:
                websocket.send('{{"id":"send_chat_message","data":"{}"}}'.format(value))
            Clock.schedule_once(self.focus)

        def focus(self, dt): #the superior focus()
            self.chatbox.focus = True

    class Chat(Widget):
        def __init__(self):
            super().__init__()
            Window.bind(on_key_down=self.focus)
        def focus(self, window, key, *args):
            chatbox = self.ids.chatbox
            if not chatbox.focus and 31 < key < 127:
                self.ids.chatbox.focus = True


    class ChatApp(App):
        def __init__(self):
            super().__init__()
            self.chathandler = None

        def build(self):
            chat = Chat()
            self.chathandler = ChatHandler(chat)
            return chat

    def wait():
        while True:
            message = websocket.recv()
            if app.chathandler is not None:
                app.chathandler.on_receive(message)
            else:
                print(f"pre-initialization request: {message}")

    app = ChatApp()
    waiter = Thread(target=wait)
    waiter.start()
    app.run()
    close()
except Exception as e:
    close()
    raise e