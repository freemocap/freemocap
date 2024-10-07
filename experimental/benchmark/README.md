# Benchmarks

## Flame Graphs

[Py-Spy](https://github.com/benfred/py-spy) can be used to generate [speedscope](https://www.speedscope.app/) compatible flame graphs. 

Install py-spy through pip or your system package manager, and run with: 

```
sudo py-spy record -f speedscope -- python experimental/benchmark/{PATH TO BENCHMARK FILE}.py
```