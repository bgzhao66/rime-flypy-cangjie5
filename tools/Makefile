export PYTHONHASHSEED=0

PRIMARY_NAME = flypy_cangjie5

.SILENT:
all:
	python3 ./convert_to_flypy_quick5.py --name $(PRIMARY_NAME) --chinese_code  --phrase --abbreviate \
				--extra_table --difference 	\
				--no-strict-purging \
				extra/essay.txt       \
				extra/360wdict-0.txt
#				extra/360wdict-1.txt
#				extra/360wdict-2.txt
#				extra/12dicts.txt
#				extra/words.txt
#				extra/luna_classic.txt

	echo "All tables converted"

mapping:
	python3 ./mapping_bopomofo.py > mapping.txt

.PHONY: clean
clean:
	rm -f ../$(PRIMARY_NAME)*.dict.yaml
