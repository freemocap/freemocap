#%% Working from this youtube vid - https://www.youtube.com/watch?v=JrGFQp9njas
from rich import print
from rich import pretty
pretty.install() #makes all print statement output pretty

from rich import inspect

#%%
print('[red]hello[/red] :poop:')
# %%
locals()
#%%
print(locals())

# %%
inspect('asdf')
# %%

inspect('asfdf',methods=True)


# %%
from rich.console import Console
console = Console()  
console.print('[green]hello[/green] :poop:') 
console.log('hello :poop:', style='bold blue') 
console.info('hello :poop:', style='bold green') 
# inspect(console, methods=True)

# %%
from rich.table import Table 

table = Table(show_header=True, header_style="bold magenta")
table.add_column("Date", style="dim", width=12)
table.add_column("Title")
table.add_column("Production Budget", justify="right")
table.add_column("Box Office", justify="right")
table.add_row(
    "Dev 20, 2019", "Star Wars: The Rise of Skywalker", "$275,000,000", "$375,126,118"
)
table.add_row(
    "May 25, 2018",
    "[red]Solo[/red]: A Star Wars Story",
    "$275,000,000",
    "$393,151,347",
)
table.add_row(
    "Dec 15, 2017",
    "Star Wars Ep. VIII: The Last Jedi",
    "$262,000,000",
    "[bold]$1,332,539,889[/bold]",
)

console.print(table)
# %%
from time import sleep
from rich.progress import track 

for step in track(range(10)):
    sleep(0.5)
    step
# %%
from rich.traceback import install as rich_traceback_install
rich_traceback_install()
1/0
# %%
