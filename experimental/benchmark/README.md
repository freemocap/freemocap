# Benchmarks

## Run Benchmarks
The different benchmarks are in the `experimental/benchmark` folder.

You will need to change the path to the data you would like to benchmark on. You can download the data test data from within the Freemocap GUI.

The benchmark code is in the `if __name__ == "__main__":` block, so the benchmark can be run with `python experimental/benchmark/{PATH TO BENCHMARK FILE}.py`.

When making changes to the code you want to benchmark, be sure to do a comparison in the GUI as well to see if the change is significant within the context of Freemocap as a whole.

## Flame Graphs

[Py-Spy](https://github.com/benfred/py-spy) can be used to generate [speedscope](https://www.speedscope.app/) compatible flame graphs. 

Install py-spy through pip or your system package manager, and run with: 

```
sudo py-spy record -f speedscope -- python experimental/benchmark/{PATH TO BENCHMARK FILE}.py
```
