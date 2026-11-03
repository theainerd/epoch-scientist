"""Print the goal section of a task.md, wrapped for the screen. Usage: python demo/goal.py tasks/revisit/task.md"""
import sys, textwrap
t = open(sys.argv[1]).read().split('\n\n')[0].replace('# Goal', '').split()
print(textwrap.fill(' '.join(t), 104))
