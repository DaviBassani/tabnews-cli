import requests
import json
import os
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.table import Table
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.styles import Style
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
import asyncio
from typing import List, Dict, Any

console = Console()
BASE_URL = "https://www.tabnews.com.br/api/v1"

class TabNewsAPI:
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        load_dotenv()
        self.token = os.getenv("TABNEWS_TOKEN")

    def get_contents(self, page: int = 1, per_page: int = 10, strategy: str = "relevant"):
        url = f"{BASE_URL}/contents"
        params = {
            "page": page,
            "per_page": per_page,
            "strategy": strategy
        }
        response = self.session.get(url, params=params)
        return response.json()

    def get_user_contents(self, username: str, page: int = 1, per_page: int = 10, strategy: str = "relevant"):
        url = f"{BASE_URL}/contents/{username}"
        params = {
            "page": page,
            "per_page": per_page,
            "strategy": strategy
        }
        response = self.session.get(url, params=params)
        return response.json()

    def get_content(self, username: str, slug: str):
        url = f"{BASE_URL}/contents/{username}/{slug}"
        response = self.session.get(url)
        return response.json()

    def get_comments(self, username: str, slug: str):
        url = f"{BASE_URL}/contents/{username}/{slug}/children"
        response = self.session.get(url)
        return response.json()

    def login(self, email: str, password: str):
        url = f"{BASE_URL}/sessions"
        data = {
            "email": email,
            "password": password
        }
        response = self.session.post(url, json=data)
        if response.status_code == 200:
            self.token = response.json().get("token")
            return True
        return False

class TabNewsUI:
    def __init__(self):
        self.api = TabNewsAPI()
        self.current_page = 1
        self.current_strategy = "relevant"
        self.selected_index = 0
        self.contents = []
        self.current_content = None
        self.view_mode = "feed"
        self.content_scroll_position = 0
        self.comments = []
        self.terminal_width = 80
        self.terminal_height = 24
        self.content_pages = []
        self.current_content_page = 0
        self.setup_ui()

    def setup_ui(self):
        self.kb = KeyBindings()

        @self.kb.add('up')
        def _(event):
            if self.view_mode == "feed":
                self.selected_index = max(0, self.selected_index - 1)
            elif self.view_mode == "content":
                self.content_scroll_position = max(0, self.content_scroll_position - 1)
            self.update_view()
            event.app.invalidate()

        @self.kb.add('down')
        def _(event):
            if self.view_mode == "feed":
                self.selected_index = min(len(self.contents) - 1, self.selected_index + 1)
            elif self.view_mode == "content":
                self.content_scroll_position += 1
            self.update_view()
            event.app.invalidate()

        @self.kb.add('left')
        def _(event):
            if self.view_mode == "feed" and self.current_page > 1:
                self.current_page -= 1
                self.selected_index = 0
                self.fetch_contents()
            self.update_view()
            event.app.invalidate()

        @self.kb.add('right')
        def _(event):
            if self.view_mode == "feed":
                self.current_page += 1
                self.selected_index = 0
                self.fetch_contents()
            self.update_view()
            event.app.invalidate()

        @self.kb.add('enter')
        def _(event):
            if self.view_mode == "feed" and self.contents:
                self.view_mode = "content"
                self.content_scroll_position = 0
                self.current_content = self.api.get_content(
                    self.contents[self.selected_index]["owner_username"],
                    self.contents[self.selected_index]["slug"]
                )
                self.comments = self.api.get_comments(
                    self.contents[self.selected_index]["owner_username"],
                    self.contents[self.selected_index]["slug"]
                )
            self.update_view()
            event.app.invalidate()

        @self.kb.add('escape')
        def _(event):
            if self.view_mode in ["content", "comments"]:
                self.view_mode = "feed"
            self.update_view()
            event.app.invalidate()

        @self.kb.add('q')
        def _(event):
            event.app.exit()

        @self.kb.add('c')
        def _(event):
            if self.view_mode == "content":
                self.view_mode = "comments"
            self.update_view()
            event.app.invalidate()

        self.text_area = TextArea(
            focusable=False,
            style="class:text-area"
        )

        self.layout = Layout(
            HSplit([
                Window(
                    height=1,
                    content=FormattedTextControl("TabNews CLI - ↑↓: Navigate | ←→: Pages | Enter: Select | Esc: Back | C: Comments | Q: Quit"),
                    style="class:header"
                ),
                self.text_area
            ])
        )

        self.style = Style.from_dict({
            'header': 'bg:ansiblue fg:white',
            'text-area': 'bg:ansiblack fg:white',
        })

        self.app = Application(
            layout=self.layout,
            key_bindings=self.kb,
            style=self.style,
            full_screen=True
        )

    def fetch_contents(self):
        self.contents = self.api.get_contents(self.current_page, 10, self.current_strategy)

    def update_view(self):
        with console.capture() as capture:
            if self.view_mode == "feed":
                self.display_feed(console)
            elif self.view_mode == "content":
                self.display_content(console)
            elif self.view_mode == "comments":
                self.display_comments(console)
        self.text_area.text = capture.get()

    def display_feed(self, console: Console):
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column()
        for i, content in enumerate(self.contents):
            prefix = "→" if i == self.selected_index else " "
            table.add_row(f"{prefix} {content['title']}")
        console.print(table)

    def display_content(self, console: Console):
        if self.current_content:
            markdown = Markdown(self.current_content["body"])
            console.print(Panel(markdown, title=self.current_content["title"]))

    def display_comments(self, console: Console):
        if self.comments:
            for comment in self.comments:
                markdown = Markdown(comment["body"])
                console.print(Panel(markdown, title=comment["owner_username"]))

    def run(self):
        self.fetch_contents()
        self.update_view()
        self.app.run()

if __name__ == "__main__":
    ui = TabNewsUI()
    ui.run() 