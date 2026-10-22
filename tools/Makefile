export PYTHONHASHSEED=0

PRIMARY_NAME = flypy_cangjie5

.SILENT:
all:
	python3 ./converter.py --name $(PRIMARY_NAME) --chinese-code  --phrase --short-code \
				--extra-table \
				extra/essay.txt       \
				extra/360wdict-0.txt
#				extra/360wdict-1.txt
#				extra/360wdict-2.txt
#				extra/12dicts.txt
#				extra/words.txt
#				extra/luna_classic.txt

	echo "All tables converted"

install:
	python3 ../plugins/rime-install.py --ime-name $(PRIMARY_NAME) --plugins

.PHONY: txt_userdb
txt_userdb:
	$(eval TXT_USERDB_FILES := $(shell python3 ./find_files.py --dir "./userdb/$(PRIMARY_NAME)" --name '*.userdb.txt' --type f))
	python3 ./userdb_txt_parser.py $(TXT_USERDB_FILES) -o ./userdb/pinyin_userdb.dict.txt

.PHONY: clean
clean:
	rm -f ../$(PRIMARY_NAME)*.dict.yaml
	rm -f ./userdb/*.dict.txt
