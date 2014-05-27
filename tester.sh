#!/bin/bash
REPEAT=5
#FILES='test1.c test2.c test3.c test4.c test5.c test6.c test7.c test8.c test9.c test10.c'
FILES='test11_2.c test11_4.c test11_6.c test11_8.c test11_10.c test11_12.c'

for fname in $FILES
do
	echo 'file: '$fname

	for with_main in 'false'
	do
		echo 'with main: '$with_main
                export WITH_MAIN=$with_main

		for max_level in 1 2 3
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
		done
	done
done

