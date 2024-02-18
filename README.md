# Slurm Viewer

This is a command-line tool visualizing node usage in Princeton Ionic and Neuronic.
This is a CLI-replica of `clusterstat/realtime`

<picture>
  <img src="./docs/screenshot.svg">
</picture>


## How to Use

This app needs supports both keyboard and mouse.  
Type `?` in the app to see the help menu. 

### A. Quick method (Recommended)

I have included binary in my personal folder. 
Add the following line at the end of your `~/.bashrc`

```bash
sv() {
    /n/fs/jc-project/slurmcmd/dist/slurmviewer
}
```

Restart the terminal, and type `sv`.

We recommend this method as you get to use the most recently updated tool, using all the new cool functionality,
without needing to download anything. 

Note that we do not have "Update available" notification functionality. 

### B. Download Binary

You can also download binary from [Releases](https://github.com/a6o/Slurm-Viewer/releases).
Note that uploaded binary might not be the same as the most recent updates. 

### C. Run using Python.

1. Clone this repository.
2. Install Textual, and run!
```
pip install textual
python ./app.py
```

> [!WARNING]  
> Do not run python code in Jihoon's directory. Jihoon might be in mid-way of adding a new feature, so the program could be bugged if you are trying to run from his python code. 

### D. Build Binary

1. First install pyinstaller
```bash
pip install pyinstaller
```

2. Then, run following
```bash
pyinstaller ./app.py --onefile --add-data="./style.tcss:." --add-data="./info.txt:." --exclude-module numpy --exclude-module matplotlib --exclude-module jedi --hidden-import textual.widgets._markdown_viewer -n slurmviewer
```

3. run `./dist/slurmviewer`

## How does it work?

### 1. Node information

The app calls 
```
sinfo -o '%100R %100n %100G %100C %100e %100m %100T %100E' -h --sort '+Rn'
```
to get all the needed information of partition name, node name, GPU type, CPU status, free memory, Total memory, current node state, and the reason for the node status. 

### 2. Job information

Since we cannot know the amount of remaining GPU right away from `sinfo`, as we do with CPU or RAM, we have to have a work around, which is to get all the jobs that are currently running on the node, and subtract the all the gpu being used from the total gpu count. 

For this tool, instead of getting jobs from each indivisual node, I fetch all the jobs that are running in the cluster to have least amount of slurm call as possible.
```
squeue -o '%100T %100b %100m %100a %100u %100C %100L %100i %100M %100N'
```

Everything else from there is fancy json structuring + [Textual](https://github.com/Textualize/textual)

### 3. How do you get the names of the people using NetID?

As in [CS guide](https://csguide.cs.princeton.edu/email/setup/ldap), you can use `ldapsearch` to get information of a person using NetID. Here, I use 

```
ldapsearch -x -h ldap.cs.princeton.edu uid=<NETID>
```

Note that this only works in Ionic, but not in Neuronic. 

## Future plans. 

1. Showing all the user's jobs. Good to see if it is in waitlist or not. Maybe show other peoples queue as well to see where in the priority queue you are in...?

2. Click individual jobs to see more details. Basically show everything that squeue can show. 

3. I don't have auto-reload on to make sure the slurm is not stressed by 100 students calling squeue every 1 second. But for Ionic, I can have the user get squeue information from my json that I save for my website...

## License
I claim no rights to this code. Do whatever you want with it. 