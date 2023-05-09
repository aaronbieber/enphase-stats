.PHONY: all

build:
	docker build -t enlighten . && \
	echo "Exporting..." && \
	docker save enlighten | gzip > enlighten.tar.gz && \
	echo "Saved englihten.tar.gz"

load:
	gunzip -c enlighten.tar.gz | docker load