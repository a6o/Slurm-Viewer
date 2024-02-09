

from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, ProgressBar, Static
from textual.containers import ScrollableContainer, Container, HorizontalScroll, Horizontal, Vertical
from textual.binding import Binding
from itertools import cycle
import time
from textual.reactive import reactive
from asyncio import sleep
import asyncio


class Slurm(App):
    """A Textual app to manage stopwatches."""
    CSS_PATH = "slurmcmd.tcss"

    BINDINGS = [
                ("q", "quit", "Quit"),
               ]


    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        # yield IndeterminateProgress()
        yield DataTable(id='nodes')


    def on_mount(self) -> None:

        data_table = self.query_one('DataTable#nodes')
        data_table.add_columns("Node", "Available CPU", "Available GPU", "Unrequested Memory", 'Free Memory')
        data_table.cursor_type = 'row'
        data_table.zebra_stripes = True

        asyncio.create_task(self.action_refresh())

    async def action_refresh(self) -> None:
        """An action to toggle dark mode."""

        table = self.query_one('DataTable#nodes')
        table.clear()

        for i in range(100):
            table.add_row(i
            )
            await sleep(0.001) # fake refresh UX :) you caught me

    



if __name__ == "__main__":
    app = Slurm()
    app.run()
    