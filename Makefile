.PHONY: all

build:
	docker build -t enlighten . && \
	echo "Exporting..." && \
	docker save enlighten | gzip > enlighten.tar.gz && \
	echo "Saved enlighten.tar.gz"

load:
	gunzip -c enlighten.tar.gz | docker load