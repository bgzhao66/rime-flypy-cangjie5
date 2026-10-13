export PYTHONHASHSEED=0

PRIMARY_NAME = flypy_cangjie5_simp

.SILENT:
all:
	python3 ./converter.py --name $(PRIMARY_NAME) --chinese-code  --phrase --short-code \
				--extra-table  \
				extra/essay.txt	    \
				extra/360wdict-0.txt
#				extra/360wdict-1.txt
#				extra/360wdict-2.txt
#				extra/words.txt

	echo "All tables converted"

install:
	python3 ../plugins/rime-install.py --ime-name $(PRIMARY_NAME) --plugins

.PHONY: userdb
userdb:
	cd ./userdb && python3 ./txt_parser.py ./*.userdb.txt

.PHONY: clean
clean:
	rm -f ../$(PRIMARY_NAME)*.dict.yaml
