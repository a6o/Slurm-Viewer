 pyinstaller ./slurmcmd.py --onefile --add-data="./slurmcmd.tcss:." --exclude-module numpy --exclude-module matplotlib --exclude-module jedi


pip install textual

`python /n/fs/jc-project/slurmcmd/slurmcmd.py`

or 

add the following in the `~/.bashrc`

```bash

jihoon() {
    python /n/fs/jc-project/slurmcmd/slurmcmd.py
}

```

and type `jihoon` on your cmd after restarting the terminal

