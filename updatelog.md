# Update Log

### v1.0.0

Initial Program

### v1.0.1 (2024/02/09)

- Click to leave help box
- Error is now using Textual app.notify
- added screenshot
- Info context is moved to separate file
- Getting real names is done in startup. Removed `get names` from the footer. (Key still works!)
- Switched O and P.
- Horizontal scrollbar bug fix

### v1.0.2
- action palette is now better
- keyboard support
- Far better refresh

### v1.0.3
- Removed Toggle Dark mode from the footer. 
- Put all the functions in the action palette
- How-to-screen adjust vertical size with scrollbar
- Tables are now all sorted. (user's table goes first)
- Add emoji next to Jihoon and user for distinction
- Now only fetch jobs from current partition. Not sure how much it saves, but it does save a bit.
- Memory usage and GPU usage of a node is coming from sinfo, not by adding up all the jobs. 
- Red if draining.
- fetching name works in both cluster.