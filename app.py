import subprocess
from textwrap import wrap
from collections import defaultdict
import json
import os
from os.path import expanduser
from rich.text import Text
from rich.style import Style
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, ProgressBar, Static, Label
from textual.containers import ScrollableContainer, Container, HorizontalScroll, Horizontal, Vertical
from textual import messages
from textual.screen import ModalScreen, Screen
from textual.binding import Binding
from itertools import cycle
from collections import deque
import time
from textual.reactive import reactive
from asyncio import sleep
import asyncio
import base64
import datetime
from textual.widgets import MarkdownViewer
from textual.command import Hit, Hits, Provider
from functools import partial
import math
from textual import on
from textual.message import Message
from textual import events

def setnode():
    cmd = f"sinfo -O 'partitionname:.100,nodelist:.100,gres:.100,gresused:.100,cpusstate:.100,freemem:.100,memory:.100,allocmem:.100,statelong:.100,reason:.100' -h -N --sort '+Rn'"
    _, outputs = subprocess.getstatusoutput(cmd) # note that the last one can contain multipe whitespaces
    
    nodelist = defaultdict(list)
    all_set = {}
    for output in outputs.split("\n"):
        output = list(map(lambda x: x.strip(), wrap(output, 101,replace_whitespace=False, drop_whitespace=False)))

        partition_name, nodename, gres, gres_used, cpus, freemem, mem, mem_usage, state, error = output


        
        if 'down' in state.lower():
            avail_cpu = 0
            free_mem = 0
            total_mem = 0
        else:
            avail_cpu = int(cpus.split('/')[1])
            free_mem = int(freemem)// 1024 if freemem.isnumeric() else 0   
                # actual free memory on server given by OS (jobs might not use all the requested memory)
                # divide 1024 to convert MB to GB
            total_mem = int(mem)// 1024 if mem.isnumeric() else 0
                # size of memory in GB.
            mem_usage = int(mem_usage)//1024 if mem_usage.isnumeric() else 0
        if 'null' in gres:
            total_gpu = 0
            gpu_usage = 0
            gpu_type = 'NONE'
        else:
            # gres = 'gpu:gtx_1080:4(S:0-1)' is 4 GPUs in total per node. 
            total_gpu = int(gres.split('(')[0].split(':')[-1])
            gpu_type = gres.split(':')[1].upper().replace("_", " ")
            gpu_usage = int(gres_used.split("(")[0].split(":")[-1])

        cpu_total = int(cpus.split('/')[-1])

        data = {'nodename': nodename, 'cpu_total': cpu_total, 'cpu_free': avail_cpu, 
        'mem_total': total_mem, 'mem_free': free_mem, 'mem_usage': mem_usage, 'gpu_total': total_gpu, 'gpu_usage':gpu_usage, 'gpu_type': gpu_type, 'state':state, 'state_reason': error}
        nodelist[partition_name].append(data)
        
        all_set[nodename] = data
        
    nodelist['all'] = list(all_set.values())
    for p, l in nodelist.items():
        nodelist[p] = sorted(l, key=lambda x: x['nodename'])

    return nodelist

def getjobs(partition='all'):
    jobs = []

    cmd = f"squeue -o '%100T %100b %100m %100a %100u %100C %100L %100i %100M %100N' " + (f'-p {partition}' if partition != 'all' else '')
    _, output = subprocess.getstatusoutput(cmd)

    for entry in output.split('\n')[1:]:
        output = list(map(lambda x: x.strip(), wrap(entry, 101,replace_whitespace=False, drop_whitespace=False)))
        state, gpu_usage, mem_usage, account, username, cpu_usage, remaining_time, job_id, running_time, nodename = output

        if state != 'RUNNING':
            continue # idk why but zeyu's code skipped non-RUNNING

        if gpu_usage == 'N/A':
                # possible format of gpu_usage= 
                #     'gres:gpu:rtx_3090:1'
                #     'gres:gpu:rtx_3090'
                #     'gres:gpu:1'
                #     'gres:gpu'
                #     'N/A'
            gpu_usage = 0
        else:
            gpu_usage = int(gpu_usage.split(':')[-1]) if gpu_usage.split(':')[-1].isnumeric() else 1
        
        if mem_usage[-1] == "G":
            mem_usage = int(float(mem_usage[:-1]))
        elif mem_usage[-1] == "M":
            mem_usage = int(mem_usage[:-1]) // 1024
        else:
            mem_usage = int(mem_usage[:-1])
        cpu_usage = int(cpu_usage)

        jobs.append({
            'job_id': job_id,
            'nodename': nodename,
            'gpu_usage': gpu_usage,
            'cpu_usage': cpu_usage,
            'mem_usage': mem_usage,
            'account': account,
            'username': username,
            'remaining_time': remaining_time,
            'running_time': running_time
        })
    return jobs

def get_data(node_list, partition='all'):
    
    jobs = getjobs(partition)

    data_of_partition = defaultdict(lambda : {'data_of_nodes':dict(), 'data_of_accounts': defaultdict(lambda:
            defaultdict(lambda: {'data_of_nodes': defaultdict(lambda: {'jobs':[],'cpu_usage':0, 'gpu_usage':0, 'mem_usage':0}), 'cpu_usage':0, 'gpu_usage':0, 'mem_usage':0, 'jobs': []}
            )
        )}
    )

    data_of_all_nodes = dict()

    for node in node_list['all']:
        data_of_all_nodes[node['nodename']] = {**node, **{'jobs': []}}

    for partition in node_list.keys():
        data_of_partition[partition]['data_of_nodes'] = {node['nodename']: data_of_all_nodes[node['nodename']] for node in node_list[partition]}


    for job in jobs:

        nodename = job['nodename']

        data_of_all_nodes[job['nodename']]['jobs'].append(job)



    for partition in data_of_partition.keys():
        data_of_nodes = data_of_partition[partition]['data_of_nodes']

        data_of_partition[partition]['cpu_total'] = sum([n['cpu_total'] for n in data_of_nodes.values()])
        data_of_partition[partition]['gpu_total'] = sum([n['gpu_total'] for n in data_of_nodes.values()])
        data_of_partition[partition]['mem_total'] = sum([n['mem_total'] for n in data_of_nodes.values()])


    for job in jobs:
        account = job['account']
        username = job['username']
        nodename = job['nodename']

        for partition in data_of_partition:

            if nodename in data_of_partition[partition]['data_of_nodes']:
                data_of_partition[partition]['data_of_accounts'][account][username]['data_of_nodes'][nodename]['cpu_usage'] += job['cpu_usage']
                data_of_partition[partition]['data_of_accounts'][account][username]['data_of_nodes'][nodename]['gpu_usage'] += job['gpu_usage']
                data_of_partition[partition]['data_of_accounts'][account][username]['data_of_nodes'][nodename]['mem_usage'] += job['mem_usage']
                data_of_partition[partition]['data_of_accounts'][account][username]['data_of_nodes'][nodename]['jobs'].append(job)
                
                data_of_partition[partition]['data_of_accounts'][account][username]['cpu_usage'] += job['cpu_usage']
                data_of_partition[partition]['data_of_accounts'][account][username]['gpu_usage'] += job['gpu_usage']
                data_of_partition[partition]['data_of_accounts'][account][username]['mem_usage'] += job['mem_usage']
                data_of_partition[partition]['data_of_accounts'][account][username]['jobs'].append(job)



    return data_of_partition

def get_peoplename(ids):

    out = {}

    for id in ids:
        cmd = "ldapsearch -x -h ldap.cs.princeton.edu uid="+id
        _, nameoutput = subprocess.getstatusoutput(cmd) 
        for l in nameoutput.split("\n"):
            if "displayName:" in l:
                
                if "::" in l:
                    thisname = base64.b64decode(l.split(":")[-1].strip()).decode()
                else:
                    thisname = l.split(":")[-1]
                out[id] = thisname.strip()

    return out


class MyDataTable(DataTable):

    def __init__(self, **kargs):
        super().__init__(**kargs)

    def on_focus(self):
        self.show_cursor = True

    def on_blur(self):
        self.show_cursor = False


class Account(Static):

    def __init__(self, account, data_of_partition):
        self.account = account
        self.data_of_partition = data_of_partition
        super().__init__()

    def compose(self) -> ComposeResult:
        """Create child widgets of a stopwatch."""
        yield Static('Slurm Account: '+self.account)
        yield MyDataTable(show_cursor=False, id=self.account)

    def on_mount(self) -> None:
        
        node_table = self.app.query_one('DataTable#nodes')

        account_table = self.query_one('DataTable')
        account_table.add_columns("User", "CPU", "GPU", "Memory")
        account_table.cursor_type = 'row'


        for username in sorted(self.data_of_partition['data_of_accounts'][self.account].keys(), key= lambda x: 'aaaaa' if x==self.app.me else x):

            account_table.add_row(("❤" if username=='jc5933' else ('🖤' if username==self.app.me else ' ')) + (username if username not in self.app.names else f'{username} ({self.app.names[username]})'), key=f"1{username}|{self.account}")
            cpu_usage_sum, gpu_usage_sum, mem_usage_sum = 0, 0, 0
            for nodename in sorted(self.data_of_partition['data_of_accounts'][self.account][username]['data_of_nodes'].keys()):
                data_of_node = self.data_of_partition['data_of_accounts'][self.account][username]['data_of_nodes'][nodename]
                account_table.add_row('  --'+nodename, 
                Text(f"{data_of_node['cpu_usage']} ({int(data_of_node['cpu_usage']*100/(self.data_of_partition['cpu_total']+1e-5)):3d}%)", justify='right'), 
                Text(f"{data_of_node['gpu_usage']} ({int(data_of_node['gpu_usage']*100/(self.data_of_partition['gpu_total']+1e-5)):3d}%)", justify='right'),
                Text(f"{data_of_node['mem_usage']}G ({int(data_of_node['mem_usage']*100/(self.data_of_partition['mem_total']+1e-5)):3d}%)", justify='right'), key=f"2{username}|{nodename}|{self.account}")
                cpu_usage_sum += data_of_node['cpu_usage']
                gpu_usage_sum += data_of_node['gpu_usage']
                mem_usage_sum += data_of_node['mem_usage']
                
            account_table.add_row('  Total', 
                                    Text(f"{cpu_usage_sum} ({int(cpu_usage_sum*100/(self.data_of_partition['cpu_total']+1e-5)):3d}%)",justify='right'), 
                                    Text(f"{gpu_usage_sum} ({int(gpu_usage_sum*100/(self.data_of_partition['gpu_total']+1e-5)):3d}%)",justify='right'),
                                    Text(f"{mem_usage_sum}G ({int(mem_usage_sum*100/(self.data_of_partition['mem_total']+1e-5)):3d}%)",justify='right')
                                    , key=f"1{username}|{self.account}|")

            account_table.add_row()


class InfoScreen(ModalScreen):
    """Screen with a dialog to quit."""

    def __init__(self, label, **kwargs):
        self.label = label
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield MarkdownViewer(self.label, show_table_of_contents=False)

    def on_key(self, event) -> None:

        if event.key == 'up' or event.key == 'down':
            return
        self.app.pop_screen()

    def on_click(self, event):
        self.app.pop_screen()


class Search(Provider):
    """A command provider to open a Python file in the current working directory."""


    async def startup(self) -> None:  


        """Called once when the command palette is opened, prior to searching."""
        self.partitions = self.app.partition_cycle


    async def search(self, query: str) -> Hits:  


        """Search for Python files."""
        matcher = self.matcher(query)  



        app = self.app
        assert isinstance(app, Slurm)

        items = []

        for partition in list(self.partitions):

            command = f"Change to partition {str(partition)}"
            fnc = partial(app.change_partition, partition)
            hlp = "Open this partition"
            
            items.append([command, fnc, hlp])
                
        items.append(['Quit the application', app.action_quit, "Quit the application as soon as possible"])
        items.append(['Toggle light/dark mode', app.action_toggle_dark, "Toggle the application between light and dark mode"])
        items.append(['Refresh', app.action_refresh, "Refresh the list."])
        items.append(['Screenshot', app.action_screens, "Take a Screenshot."])
        items.append(['Fetch names', app.action_getnames, "Fetch missing real names."])

        for command, fnc, hlp in items:
            score = matcher.match(command)

            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(command),
                    fnc,
                    help=hlp
                )


class Slurm(App):
    """A Textual app to manage stopwatches."""

    COMMANDS = {Search}
    CSS_PATH = "style.tcss"
    BINDINGS = [Binding("d", "toggle_dark", "Toggle dark mode", show=False),
                ("r", "refresh", "Refresh"),
                Binding("o", "cycle_partition_b", "", show=False),
                ("p", "cycle_partition", "Change Partition"),
                Binding("left", "cycle_partition_b", "", show=False),
                Binding("right", "cycle_partition", '', show=False),
                Binding("pageup", "scrollup", "Scroll Up", show=False, priority=True),
                Binding("pagedown", "scrolldown", "Scroll Down", show=False, priority=True),
                Binding("home", "home", "Scroll Up", show=False, priority=True),
                Binding("end", "end", "Scroll Down", show=False, priority=True),    
                Binding("s", "screens", "", show=False),    
                Binding('n', 'getnames', 'Show Names', show=False),
                ("q", "quit", "Quit"),
                ("?", 'help', 'Help'),
               ]

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Footer()
        yield Horizontal(Vertical(MyDataTable(id='nodes'), Vertical(id='accounts'), id='left'), 
                        Vertical(Static(), DataTable(show_cursor=False, id='details'), id='right'))

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark

    def on_mount(self) -> None:

        self.me = subprocess.getstatusoutput('echo $LOGNAME')[1]
        data_table = self.query_one('DataTable#nodes')
        data_table.add_columns("Node", "Available CPU", "Available GPU", "Unrequested Memory", 'Free Memory')
        data_table.cursor_type = 'row'
        data_table.zebra_stripes = True

        detail_table = self.query_one('DataTable#details')
        detail_table.add_columns("User", "Job ID", "GPU", "CPU", "Mem", "Running Time (DD-HH:MM:SS)", "Remaining Time (DD-HH:MM:SS)")
        detail_table.zebra_stripes = True
        detail_table.can_focus=False

        home = expanduser("~")
        if os.path.exists(os.path.join(home, '.jihoon', 'settings.json')):

            try:
                init_setting = json.load(open(os.path.join(home, '.jihoon', 'settings.json')))
            except:
                init_setting = {}
        else:
            init_setting = {}

        if os.path.exists(os.path.join(home, '.jihoon', 'names.json')):
            try:
                self.names = json.load(open(os.path.join(home, '.jihoon', 'names.json')))
            except:
                self.names = {}
        else:
            self.names = {}

        self.dark= init_setting['dark'] if 'dark' in init_setting else False
        self.sub_title = ''
        self.partition= init_setting['partition'] if 'partition' in init_setting else 'all'
        self.title = self.partition
        self.partition_cycle = None
        self.vl = self.query_one('Vertical#left')
        self.row_key = ''

        

        asyncio.create_task(self.action_refresh(getname=True))

        
        self.updated_time = time.time()
        self.update_render = self.set_interval(
            1, self.update_subtitle
        )  

    async def action_refresh(self, getname=False, changed=False) -> None:
        """An action to toggle dark mode."""

        if self.screen.focus_chain and self.focused:
            current_index = self.focused.id
            current_cursor = self.focused.cursor_row
        else:
            current_index = 'nodes'
            current_cursor = 0 

        self.screen.set_focus(None, scroll_visible=False)


        dtable = self.query_one('DataTable#details')
        dtable.clear()

        table = self.query_one('DataTable#nodes')
        table.clear()

        nodelist = setnode()

        data_of_partition = get_data(nodelist, self.partition)
        self.data_of_partition = data_of_partition
        
        if getname:
            self.action_getnames(refresh=False)

        if not self.partition_cycle:
            self.partition_cycle = deque(list(data_of_partition.keys())[1:] + ['all'])

        
        for nodename, node in sorted(data_of_partition[self.partition]['data_of_nodes'].items(), key=lambda x: x[0]):
            

            if 'mixed' in node['state'] or  'allocated' in node['state'] or  'idle' in node['state']:
                nametext = Text(nodename + f" ({node['gpu_total']} × {node['gpu_type'].upper()})")
                drain= False
            else:
                nametext = Text(f"{nodename} ({node['gpu_total']} × {node['gpu_type'].upper()}) ({node['state']})", 
                style=Style(strike=True,color='red'))
                drain=True
            table.add_row(
            nametext,
            Text(f"{node['cpu_free']} / {node['cpu_total']}", justify="right", style=Style(color='red') if drain else None),
            Text(f"{node['gpu_total']-node['gpu_usage']} / {node['gpu_total']}", justify="right", style=Style(color='red') if drain else None),
            Text(f"{node['mem_total'] - node['mem_usage']}G", justify="right", style=Style(color='red') if drain else None),
            Text(f"{node['mem_free']}G", justify="right", style=Style(color='red') if drain else None), key=f"0{nodename}"
            )
            # await sleep(0.001) # fake refresh UX :) you caught me

        self.query_one("#accounts").remove_children()
        self.list_of_tables = ['nodes']
        self.cursor_offset = {}

        for accountname in sorted(data_of_partition[self.partition]['data_of_accounts'].keys()):

            self.list_of_tables.append(accountname)
            accountdiv = Account(accountname, data_of_partition[self.partition])

            with accountdiv.prevent(DataTable.RowHighlighted):
                self.query_one("#accounts").mount(accountdiv)


        # after refreshing, focus to the previously focused account datatable. 
        # if doesnt exist, focus to the main one. 
        # this is not for partition change
        if not changed:
            self.app.call_after_refresh(lambda: 
                ((self.app.set_focus([i for i in self.screen.focus_chain if i.id==current_index][0], scroll_visible=False), \
                    self.focused.move_cursor(row=current_cursor))\
                    ) if len([i for i in self.screen.focus_chain if i.id==current_index]) > 0 else self.app.set_focus(self.screen.focus_chain[0],scroll_visible=False)
            
            
            )
        else:
            self.app.call_after_refresh(lambda: self.app.set_focus(self.screen.focus_chain[0], scroll_visible=False))

        if not changed:
            self.app.call_after_refresh(lambda: self.on_data_table_row_selected(self.row_key))

        self.updated_time = time.time()
        self.update_subtitle()

    def update_subtitle(self):

        def whenago(seconds):
            if seconds < 60:
                return f'{int(seconds)} seconds'
            else:
                return f'{int(seconds)//60} minutes'
            
        self.sub_title = f'Last refreshed {whenago(time.time()-self.updated_time)} ago'

    def action_cycle_partition(self):
        self.partition_cycle.rotate(-1)
        self.partition = self.partition_cycle[0]
        self.title = self.partition
        asyncio.create_task(self.action_refresh(changed=True))

    def action_cycle_partition_b(self):
        
        self.partition_cycle.rotate(1)
        self.partition = self.partition_cycle[0]


        self.title = self.partition
        asyncio.create_task(self.action_refresh(changed=True))

    def action_scrollup(self):
        self.vl.scroll_up(animate=False)

    def action_scrolldown(self):
        self.vl.scroll_down(animate=False)

    def action_home(self):
        data_table = self.query_one('Vertical#left')
        data_table.scroll_home()
        pass

    def action_end(self):
        data_table = self.query_one('Vertical#left')
        data_table.scroll_end()

    def action_help(self):

        data_table = self.query_one('Vertical#left')
        data_table = self.query_one('Vertical#right')

        if os.path.exists("./info.txt"): # if binary
            info = open("./info.txt").read()
        else:
            __location__ = os.path.realpath( # if running from python
        os.path.join(os.getcwd(), os.path.dirname(__file__)))
            info = open(os.path.join(__location__, 'info.txt')).read()
        self.push_screen(InfoScreen(info))

    def action_quit(self):
        home = expanduser("~")
        
        os.makedirs(os.path.join(home, '.jihoon'), exist_ok=True)
        json.dump({'version':0, 'dark':self.dark, 'partition':self.partition}, open(os.path.join(home, '.jihoon', 'settings.json'), 'w'))
        json.dump(self.names, open(os.path.join(home, '.jihoon', 'names.json'), 'w'))
        
        self.exit()

    def change_partition(self, partition):
        self.partition = partition
        self.title = self.partition
        asyncio.create_task(self.action_refresh())


    def on_data_table_row_selected(self, message):


        if isinstance(message, str):
            row_key = message
        else:
            row_key = message.row_key.value

        if row_key and len(row_key) > 0:

            self.row_key = row_key
            typ = row_key[0]

            table = self.query_one('DataTable#details')
            table.clear()
            static = self.query_one('Vertical#right Static')
            static.update('')

            try:
                if typ == '0':
                    nodename = row_key[1:]

                    node = self.data_of_partition[self.partition]['data_of_nodes'][nodename]
                    if 'mixed' in node['state'] or  'allocated' in node['state'] or  'idle' in node['state']:
                        pass
                    else:
                        static.update(Text("Node Issue:"+node['state_reason'], style=Style(bgcolor='black', color='white')))


                    for job in sorted(node['jobs'], key=lambda x: x['job_id']):
                        table.add_row(
                            Text(f"{job['username']}", justify="right"),
                            Text(f"{job['job_id']}", justify="right"),
                            Text(f"{job['gpu_usage']}", justify="right"),
                            Text(f"{job['cpu_usage']}", justify="right"),
                            Text(f"{job['mem_usage']}", justify="right"),
                            Text(f"{job['running_time']}", justify="right"),
                            Text(f"{job['remaining_time']}", justify="right"),

                        )

                if typ == '1':
                    username, account = row_key[1:].split("|")[:2]

                    for job in sorted(self.data_of_partition[self.partition]['data_of_accounts'][account][username]['jobs'], key=lambda x: x['job_id']):
                        table.add_row(
                            Text(f"{job['username']}", justify="right"),
                            Text(f"{job['job_id']}", justify="right"),
                            Text(f"{job['gpu_usage']}", justify="right"),
                            Text(f"{job['cpu_usage']}", justify="right"),
                            Text(f"{job['mem_usage']}", justify="right"),
                            Text(f"{job['running_time']}", justify="right"),
                            Text(f"{job['remaining_time']}", justify="right"),

                        )

                if typ == '2':
                    username, nodename, account  = row_key[1:].split("|")[:3]

                    for job in sorted(self.data_of_partition[self.partition]['data_of_accounts'][account][username]['data_of_nodes'][nodename]['jobs'], key=lambda x: x['job_id']):
                        table.add_row(
                            Text(f"{job['username']}", justify="right"),
                            Text(f"{job['job_id']}", justify="right"),
                            Text(f"{job['gpu_usage']}", justify="right"),
                            Text(f"{job['cpu_usage']}", justify="right"),
                            Text(f"{job['mem_usage']}", justify="right"),
                            Text(f"{job['running_time']}", justify="right"),
                            Text(f"{job['remaining_time']}", justify="right"),

                        )
            except:
                self.row_key = None

    def action_getnames(self, refresh=True):

        allthename = set([job['username'] for node in self.data_of_partition['all']['data_of_nodes'].values() for job in node['jobs']])
        

        missingname = allthename - set(self.names.keys())

        try:
            got_names = get_peoplename(list(missingname))
        except:
            self.notify('Cannot load new names!\nsome issue with getting the name from CS mail server!')

            return

        if refresh:
            self.notify(f'Got {len(got_names)} new names:\n{",".join(list(got_names.keys()))}')

        self.names = {**self.names, **got_names}

        if refresh:
            asyncio.create_task(self.action_refresh())

    def action_screens(self, **kwargs):

        home = expanduser("~")
        filename = 'screenshot_{date:%Y-%m-%d_%H-%M-%S}.svg'.format( date=datetime.datetime.now() )
        self.action_screenshot(filename=filename, path=home)
        self.notify(f'Screenshot added to your home directory.\n{os.path.join(home,filename)}')

    def on_key(self, event):

        if isinstance(self.focused, MyDataTable):

            try:

                # get the canonical y-location of the cursor. 
                # we need to know the y-loc of the first row of each datatable
                if len(self.cursor_offset) == 0:
                    offset = 1 # do not count the title bar
                    for datatable in self.screen.focus_chain:

                        self.cursor_offset[datatable.id] = offset
                        offset += datatable.row_count + 3

                if event.key == 'down':
                    event.prevent_default()
                    if self.focused.cursor_row == self.focused.row_count-1:

                        self.screen.focus_next()
                        self.focused.move_cursor(row=0)
                    else:
                        self.focused.move_cursor(row=self.focused.cursor_row+1)

                elif event.key == 'up':
                    event.prevent_default()
                    if self.focused.cursor_row == 0:
                        # this will lead to scrolling all the way to the top of the table
                        # self.screen.focus_previous(scroll_visible=False) 
                        current_index = self.screen.focus_chain.index(self.focused)

                        prev_table = self.screen.focus_chain[(current_index-1+len(self.screen.focus_chain))%len(self.screen.focus_chain)]
                        self.screen.set_focus(prev_table, scroll_visible=False)
                        self.focused.move_cursor(row=self.focused.row_count-1)
                    else:
                        self.focused.move_cursor(row=self.focused.cursor_row-1)
                        
                elif event.key == 'tab':
                    event.prevent_default()
                    self.screen.focus_next()
                    self.focused.move_cursor(row=0)
                elif event.key == 'shift+tab':
                    event.prevent_default()
                    self.screen.focus_previous()
                    self.focused.move_cursor(row=0)

                else:
                    return


                # we need to scroll so that the cursor is visible

                canonical_location_of_the_cursor = self.cursor_offset[self.focused.id] + self.focused.cursor_row
                where_should_cursor_be_relative_to_window = canonical_location_of_the_cursor - self.vl.scroll_y

                if where_should_cursor_be_relative_to_window < 0:
                    self.vl.scroll_to(y=int(self.vl.scroll_y + where_should_cursor_be_relative_to_window),speed=150)

                elif math.ceil(where_should_cursor_be_relative_to_window) >= self.vl.size[1]:
                    self.vl.scroll_to(y=math.ceil(self.vl.scroll_y + where_should_cursor_be_relative_to_window - self.vl.size[1] + 1),speed=150)
                    

                
                
            except Exception as e:
                self.notify('Some error happened but I put try-except, so its okay. \n'+str(e))

if __name__ == "__main__":
    app = Slurm()
    app.run()
    