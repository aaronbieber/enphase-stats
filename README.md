# Enphase API Stats Collector

This project provides a bridge between the [Enphase
API](https://developer-v4.enphase.com/) and a StatsD/Carbon/Graphite instance.
Its purpose is to periodically collect your solar telemetry and feed it into
your stats server. For now, we collect the "production" and "consumption" values
for each interval.

This project is written in Python and requires some Python 3 environment. It was
written in Python 3.10.6. It's recommended that you configure and test this
project in a local Python virtualenv, and deploy it somewhere using Docker. A
very simple Docker setup is provided and described below.

## Configuration

Clone the project and configure a virtualenv for it:

```.sh
$ git clone git@github.com:aaronbieber/enlighten.git
$ cd enlighten
$ python -m venv .venv
$ source .venv/bin/activate
$ pip install -r requirements.txt
```

Run the script:

```.sh
$ python monitor.py
```

The first time (or few times) you run it, it will prompt you to complete some
configuration actions, which will also be described here.

### API access

First, set up a developer account on the [Enphase
API](https://developer-v4.enphase.com/) website, and then under the
"applications" section, create a new application. It doesn't matter what it is
called, what the organization is, or who the owner is. It *does* matter that you
select all three access categories (system data, consumption, production).

Open the `whisper.py` file and populate your API key, client ID, and client
secret.

Run the script again. It will prompt you to visit an OAuth handshake URL in a
browser, which will redirect you to log into your **actual Enlighten account**
to authorize access to **your live system**. After granting access, you'll be
shown your "auth code."

**Copy the auth code** and place it in `whisper.py`. You are not shown this code
ever again, so don't miss this step!

Run the script again. Given the API key, client ID, client secret, and auth
code, it should be able to get a set of OAuth tokens and request the list of
available systems. If all of that worked, it will print out the system names and
IDs that it has access to.

Copy the *system ID* for the system you are monitoring, and place that in
`whisper.py` as well.

### Stats host

All of this data is pointless without somewhere to put it, so you must also
configure the *carbon host* to send the data to. Configure that in `config.py`.

`CARBON_HOST` is an IP or hostname for the machine that carbon is running on,
and the `CARBON_PICKLE_PORT` is the port that Carbon listens on (2004 by
default). Access to carbon is required because the Enphase API is not realtime,
and can also experience lag at times.

For that reason, it's necessary to populate *past data points*, and the StatsD
interface does not allow that (it is realtime only). Using the "pickle"
interface, we can send a large number of data points in one request to backfill
gaps in data.

## Deploying

You can run the script however you like. The simplest solution, if possible, is
to simply run it from a virtualenv from a cron job or similar.

If, like me, you run all of your batches and services on an old Ubuntu
installation that doesn't have any modern Python packages available, you can
also use Docker.

Assuming you have Docker configured in your cli environment (which is out of
scope for this README), you can simply `make build` to build and gzip a Docker
image that you can deploy wherever you need to.

Extract and load the image (`make load`) on the Docker host you'll be using.

Finally, you'll need your `tokens` and `request_cache` files from your local
copy. `tokens` contains the OAuth tokens, and `request_cache` stores the
last-seen interval timestamp so that old data is not re-loaded into carbon.

It's sufficient to place those two files in a directory alongside `start.sh`,
and then call `start.sh` however you'd like (I use cron). The start script will
determine its own path and run the Docker image with the other two files bind
mounted into it.

Using the "Watt" (free tier) API plan, you should not run this script more
frequently than every two hours or so, or you will exceed the plan request
limits.

## Support

There is no support. Feel free to open an issue, but I can't guarantee I'll even
look at it. PRs welcome, though!

## License

This software is provided under the WTFPL and its full text is provided in the
accompanying `LICENSE` file.