#!/bin/bash
REPEAT=10
#FILES='test1.c test2.c test3.c test4.c test5.c test6.c test7.c test8.c test9.c test10.c'
FILES='test11_10.c'

for fname in $FILES
do
	echo 'file: '$fname

	for with_main in 'false'
	do
		echo 'with main: '$with_main
                export WITH_MAIN=$with_main

		for max_level in 1 2 3 4
		do
			echo 'max level: '$max_level
			export MAX_LEVEL=$max_level

			out='results/'$fname'_'$with_main'_'$max_level
			echo 'output file: '$out

			for ((i = 0; i < $REPEAT; i++))
			do
				echo 'iteration: '$i
				./gcc-pyplugin plugin.py tests/$fname -lpthread  >> $out
			done
			echo 'Mean time('$fname','$with_main','$max_level'): '`less $out  | grep 'Elapsed' | cut -d\  -f3 | python -c "import sys;lines=[line for line in sys.stdin];print sum([float(line) for line in lines])/len(lines);"`
		done
	done
done

