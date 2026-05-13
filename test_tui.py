"""Minimal Textual test"""
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Label, Input
from textual.containers import Vertical

class TestApp(App):
    CSS = """
    Screen { background: #1a1a2e; }
    Label { color: #e0e0e0; padding: 1; }
    Input { dock: bottom; margin: 1; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Label("Hello! 如果你看到这个，Textual 工作正常"),
            Label("底部应有输入框，键入后按 Enter"),
        )
        yield Input(placeholder="这里输入...")
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.query_one(Label).update(f"你输入了: {event.value}")

if __name__ == "__main__":
    TestApp().run()
